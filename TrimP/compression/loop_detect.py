"""
Loop detector — detects tool-repeat, content-repeat, and pattern-repeat loops.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from TrimP.db import db, now_iso


@dataclass
class LoopEvent:
    loop_type: str
    pattern: str
    repeat_count: int


class LoopDetector:
    """Track assistant actions and detect unproductive loops."""

    def __init__(self, session_id: str, window: int = 10) -> None:
        self.session_id = session_id
        self.window = window
        self._tool_history: list[str] = []
        self._content_hashes: list[str] = []
        self._pattern_history: list[str] = []

    def record_tool_call(self, tool_name: str, params: dict | None = None) -> LoopEvent | None:
        sig = _tool_sig(tool_name, params or {})
        self._tool_history.append(sig)
        if len(self._tool_history) > self.window:
            self._tool_history.pop(0)

        event = _detect_repeat(self._tool_history, sig, threshold=2)
        if event:
            self._persist(event)
            return LoopEvent("tool_repeat", sig, event)
        return None

    def record_content(self, content: str) -> LoopEvent | None:
        h = _hash(content[:500])
        self._content_hashes.append(h)
        if len(self._content_hashes) > self.window:
            self._content_hashes.pop(0)

        count = self._content_hashes.count(h)
        if count >= 2:
            self._persist_event("content_repeat", h[:16], count)
            return LoopEvent("content_repeat", f"content_hash={h[:16]}", count)
        return None

    def record_pattern(self, pattern: str) -> LoopEvent | None:
        self._pattern_history.append(pattern)
        if len(self._pattern_history) > self.window:
            self._pattern_history.pop(0)
        event = _detect_repeat(self._pattern_history, pattern, threshold=3)
        if event:
            self._persist_event("pattern_repeat", pattern, event)
            return LoopEvent("pattern_repeat", pattern, event)
        return None

    def summary(self) -> dict[str, int]:
        with db() as conn:
            rows = conn.execute(
                "SELECT loop_type, COUNT(*) as c FROM loop_detections WHERE session_id=? GROUP BY loop_type",
                (self.session_id,),
            ).fetchall()
        return {r["loop_type"]: r["c"] for r in rows}

    def _persist(self, event: Any) -> None:
        pass  # Called by record_tool_call, see _persist_event

    def _persist_event(self, loop_type: str, pattern: str, count: int) -> None:
        with db() as conn:
            conn.execute(
                """INSERT INTO loop_detections
                   (session_id, loop_type, pattern, repeat_count, detected_at)
                   VALUES (?,?,?,?,?)""",
                (self.session_id, loop_type, pattern, count, now_iso()),
            )


def _detect_repeat(history: list[str], item: str, threshold: int) -> int | None:
    count = history.count(item)
    if count >= threshold:
        return count
    return None


def _tool_sig(tool: str, params: dict) -> str:
    # Normalize params to a stable signature
    key_params = {k: str(v)[:50] for k, v in params.items() if k not in ("content", "file_text")}
    return f"{tool}:{sorted(key_params.items())}"


def _hash(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()
