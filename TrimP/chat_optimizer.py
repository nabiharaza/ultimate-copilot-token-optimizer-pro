"""Shared request-body optimization and measurement for chat APIs.

This module is deliberately conservative about structured payloads: it rewrites
only text fields it understands, keeps message shapes intact, and returns a
machine-readable stats object for dashboards, headers, and tests.
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from typing import Any

from TrimP.compress_api import compress_text
from TrimP.compression.context_codec import apply_anchor_aliases
from TrimP.compression.bash import BashCompressor
from TrimP.compression.advanced.conversation_compressor import ConversationCompressor
from TrimP.compression.json_table import JsonTableCompressor
from TrimP.compression.prompt_compression import PromptCompressor
from TrimP.compression.search import SearchCompressor


def optimization_enabled() -> bool:
    """Read the shared runtime switch used by every proxy surface."""
    try:
        from TrimP.db import get_config
        return str(get_config("compression.enabled", "true")).lower() in {"1", "true", "yes", "on"}
    except Exception:
        return True


def estimate_tokens(value: Any) -> int:
    """Cheap, stable estimate used consistently across TrimP surfaces."""
    if not isinstance(value, str):
        value = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return max(1, len(value) // 4)


@dataclass
class CompressionChange:
    path: str
    method: str
    tokens_before: int
    tokens_after: int

    @property
    def tokens_saved(self) -> int:
        return max(0, self.tokens_before - self.tokens_after)


@dataclass
class ChatOptimizationStats:
    tokens_before: int
    tokens_after: int
    changes: list[CompressionChange] = field(default_factory=list)

    @property
    def tokens_saved(self) -> int:
        return max(0, self.tokens_before - self.tokens_after)

    @property
    def savings_pct(self) -> float:
        if self.tokens_before <= 0:
            return 0.0
        return round(self.tokens_saved / self.tokens_before * 100.0, 2)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tokens_before": self.tokens_before,
            "tokens_after": self.tokens_after,
            "tokens_saved": self.tokens_saved,
            "savings_pct": self.savings_pct,
            "changes": [
                {
                    "path": c.path,
                    "method": c.method,
                    "tokens_before": c.tokens_before,
                    "tokens_after": c.tokens_after,
                    "tokens_saved": c.tokens_saved,
                }
                for c in self.changes
            ],
        }


class ChatPayloadOptimizer:
    """Optimize OpenAI/Anthropic-like chat request bodies."""

    def __init__(self, *, min_chars: int = 160, min_savings_pct: float = 8.0):
        self.min_chars = min_chars
        self.min_savings_pct = min_savings_pct
        self.compress_system = os.environ.get("TRIMP_COMPRESS_SYSTEM", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.prompt = PromptCompressor()
        self.bash = BashCompressor()
        self.search = SearchCompressor()
        self.json_table = JsonTableCompressor()
        self.conversation = ConversationCompressor(
            verbatim_tail=int(os.environ.get("TRIMP_CHAT_VERBATIM_TAIL", "3")),
            summary_head=int(os.environ.get("TRIMP_CHAT_SUMMARY_HEAD", "6")),
        )

    def optimize_body(self, body: dict[str, Any], *, enabled: bool | None = None) -> tuple[dict[str, Any], ChatOptimizationStats]:
        optimized = copy.deepcopy(body)
        before = estimate_tokens(optimized)
        if enabled is None:
            enabled = optimization_enabled()
        if not enabled:
            return optimized, ChatOptimizationStats(tokens_before=before, tokens_after=before)
        changes: list[CompressionChange] = []

        if isinstance(optimized.get("instructions"), str):
            optimized["instructions"] = self._rewrite_text(
                optimized["instructions"],
                path="instructions",
                role="system",
                changes=changes,
            )

        if isinstance(optimized.get("system"), str):
            optimized["system"] = self._rewrite_text(
                optimized["system"], path="system", role="system", changes=changes
            )
        elif isinstance(optimized.get("system"), list):
            optimized["system"] = self._rewrite_content_parts(
                optimized["system"], path="system", role="system", changes=changes
            )

        messages = optimized.get("messages")
        if isinstance(messages, list):
            optimized["messages"], sequence_rewritten = self._rewrite_message_sequence(messages, changes=changes)
            if not sequence_rewritten:
                for idx, msg in enumerate(optimized["messages"]):
                    if not isinstance(msg, dict):
                        continue
                    role = str(msg.get("role", "user"))
                    path = f"messages[{idx}].content"
                    content = msg.get("content")
                    if isinstance(content, str):
                        msg["content"] = self._rewrite_text(content, path=path, role=role, changes=changes)
                    elif isinstance(content, list):
                        msg["content"] = self._rewrite_content_parts(content, path=path, role=role, changes=changes)

        input_value = optimized.get("input")
        if isinstance(input_value, str):
            optimized["input"] = self._rewrite_text(
                input_value, path="input", role="user", changes=changes
            )
        elif isinstance(input_value, list):
            self._rewrite_responses_input(input_value, changes=changes)

        after = estimate_tokens(optimized)
        return optimized, ChatOptimizationStats(tokens_before=before, tokens_after=after, changes=changes)

    def _rewrite_message_sequence(
        self,
        messages: list[Any],
        *,
        changes: list[CompressionChange],
    ) -> tuple[list[Any], bool]:
        """Compact old/middle user-assistant turns while preserving the recent tail.

        This is the Headroom/TokenSplit-style path: preserve protocol-bearing
        messages, keep the latest turns verbatim, summarize old turns, and
        extract high-signal middle content. We only run it for plain text chat
        histories because tool-call chains and structured content can be order
        sensitive.
        """
        prefix: list[Any] = []
        conversation: list[dict[str, str]] = []

        for msg in messages:
            if not isinstance(msg, dict):
                return messages, False
            role = str(msg.get("role", "user"))
            content = msg.get("content")

            if not conversation and role in {"system", "developer"}:
                prefix.append(msg)
                continue

            if role not in {"user", "assistant"} or not isinstance(content, str):
                return messages, False
            if role == "assistant" and ("tool_calls" in msg or "function_call" in msg):
                return messages, False
            conversation.append({"role": role, "content": content})

        if len(conversation) <= self.conversation.verbatim_tail + 2:
            return messages, False

        before = estimate_tokens(conversation)
        compressed_conversation, metadata = self.conversation.compress(conversation)
        if not isinstance(compressed_conversation, list):
            return messages, False

        after = estimate_tokens(compressed_conversation)
        if after >= before:
            return messages, False
        saved_pct = (before - after) / before * 100.0
        if saved_pct < self.min_savings_pct:
            return messages, False

        changes.append(
            CompressionChange(
                path="messages",
                method=f"conversation-sequence:{metadata.get('method', 'ConversationCompressor')}",
                tokens_before=before,
                tokens_after=after,
            )
        )
        compacted = [*prefix, *compressed_conversation]
        encoded, codec_stats = apply_anchor_aliases(
            compacted,
            protected_tail=self.conversation.verbatim_tail,
        )
        if codec_stats.estimated_saved_tokens > 0:
            changes.append(
                CompressionChange(
                    path="messages.aliases",
                    method="context-codec:anchor-aliases",
                    tokens_before=after,
                    tokens_after=max(1, after - codec_stats.estimated_saved_tokens),
                )
            )
            return encoded, True
        return compacted, True

    def _rewrite_responses_input(
        self,
        items: list[Any],
        *,
        changes: list[CompressionChange],
    ) -> None:
        """Rewrite safe text fields in an OpenAI Responses API input list."""
        for idx, item in enumerate(items):
            path = f"input[{idx}]"
            if isinstance(item, str):
                items[idx] = self._rewrite_text(
                    item, path=path, role="user", changes=changes
                )
                continue
            if not isinstance(item, dict):
                continue

            item_type = str(item.get("type", "message"))
            if item_type == "function_call_output":
                output = item.get("output")
                if isinstance(output, str):
                    item["output"] = self._rewrite_text(
                        output,
                        path=f"{path}.output",
                        role="tool",
                        changes=changes,
                    )
                elif isinstance(output, list):
                    item["output"] = self._rewrite_content_parts(
                        output,
                        path=f"{path}.output",
                        role="tool",
                        changes=changes,
                    )
                continue

            # These items are protocol state. Rewriting them can invalidate a
            # tool-call chain or encrypted reasoning state.
            if item_type in {
                "function_call",
                "computer_call",
                "reasoning",
                "item_reference",
            }:
                continue

            role = str(item.get("role", "user"))
            content = item.get("content")
            if isinstance(content, str):
                item["content"] = self._rewrite_text(
                    content,
                    path=f"{path}.content",
                    role=role,
                    changes=changes,
                )
            elif isinstance(content, list):
                item["content"] = self._rewrite_content_parts(
                    content,
                    path=f"{path}.content",
                    role=role,
                    changes=changes,
                )
            elif isinstance(item.get("text"), str):
                item["text"] = self._rewrite_text(
                    item["text"],
                    path=f"{path}.text",
                    role=role,
                    changes=changes,
                )

    def _rewrite_content_parts(
        self,
        parts: list[Any],
        *,
        path: str,
        role: str,
        changes: list[CompressionChange],
    ) -> list[Any]:
        for idx, part in enumerate(parts):
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type", "text"))
            if isinstance(part.get("text"), str):
                part["text"] = self._rewrite_text(
                    part["text"], path=f"{path}[{idx}].text", role=role, changes=changes
                )
            elif isinstance(part.get("content"), str):
                hint_role = "tool" if "tool" in part_type else role
                part["content"] = self._rewrite_text(
                    part["content"], path=f"{path}[{idx}].content", role=hint_role, changes=changes
                )
        return parts

    def _rewrite_text(
        self,
        text: str,
        *,
        path: str,
        role: str,
        changes: list[CompressionChange],
    ) -> str:
        if len(text) < self.min_chars:
            return text

        before = estimate_tokens(text)
        compressed = text
        method = ""

        if role == "system":
            if not self.compress_system:
                return text
            compressed, _ = self.prompt.compress(text)
            method = "prompt"
        elif role in {"tool", "function"} or self._looks_like_command_output(text):
            compressed, _ = self._compress_toolish_text(text)
            method = "tool-output"
        elif role == "assistant":
            result = compress_text(text, hint="chat")
            compressed = result["compressed"]
            method = result.get("routed_to") or result.get("method") or "assistant"
        else:
            result = compress_text(text, hint="doc")
            compressed = result["compressed"]
            method = result.get("routed_to") or result.get("method") or "user"

        after = estimate_tokens(compressed)
        if after >= before:
            return text
        saved_pct = (before - after) / before * 100.0
        if saved_pct < self.min_savings_pct:
            return text

        changes.append(
            CompressionChange(path=path, method=method, tokens_before=before, tokens_after=after)
        )
        return compressed

    def _compress_toolish_text(self, text: str) -> tuple[str, int]:
        stripped = text.strip()
        if stripped.startswith(("{", "[")):
            return self.json_table.compress_json(text)
        if text.count("\n") > 30 and (":" in text or "match" in text.lower()):
            return self.search.compress(text)
        return self.bash.compress(text, use_algo=False)

    @staticmethod
    def _looks_like_command_output(text: str) -> bool:
        needles = (
            "Traceback",
            "FAILED",
            "PASSED",
            "npm ",
            "pytest",
            "ERROR",
            "WARN",
            "git ",
            "docker",
            "BUILD SUCCESS",
            "BUILD FAILURE",
        )
        return any(n in text for n in needles)
