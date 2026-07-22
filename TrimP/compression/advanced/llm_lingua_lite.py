"""Compatibility wrapper for the former word-frequency compressor.

The original implementation deleted individual words using within-document
frequency, which could remove punctuation, negations, and syntax. Existing
imports keep working, but this module now performs complete-sentence,
query-aware extractive compression. Real LLMLingua-2 is available through the
optional adapter in :mod:`TrimP.compression.advanced.llmlingua2`.
"""

from __future__ import annotations

import re
from typing import Any

from TrimP.compression.verification import extract_protected_anchors
from TrimP.tokenization import count_tokens


class LLMLinguaLite:
    """Deprecated name for safe query-aware extractive compression."""

    def __init__(self, target_ratio: float = 0.5, preserve_questions: bool = True):
        self.target_ratio = max(0.2, min(target_ratio, 1.0))
        self.preserve_questions = preserve_questions

    def compress(self, text: str, *, query: str = "") -> tuple[str, dict[str, Any]]:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n{2,}", text) if part.strip()]
        if len(sentences) <= 1 or len(text) < 120:
            return text, self._metadata(text, text, len(sentences), len(sentences), query)
        query_terms = set(re.findall(r"[A-Za-z_][A-Za-z0-9_.:/-]{2,}", query.lower()))
        anchors = extract_protected_anchors(text)
        anchor_values = {value for values in anchors.values() for value in values}
        scored: list[tuple[float, int, str]] = []
        for index, sentence in enumerate(sentences):
            terms = set(re.findall(r"[A-Za-z_][A-Za-z0-9_.:/-]{2,}", sentence.lower()))
            score = len(query_terms & terms) * 4.0
            score += sum(6.0 for value in anchor_values if value in sentence)
            score += 1.0 if index == 0 else 0.0
            score += 0.75 if index == len(sentences) - 1 else 0.0
            score += 2.0 if self.preserve_questions and "?" in sentence else 0.0
            scored.append((score, index, sentence))
        keep = max(1, int(round(len(sentences) * self.target_ratio)))
        chosen = sorted(sorted(scored, reverse=True)[:keep], key=lambda item: item[1])
        omitted = len(sentences) - len(chosen)
        compressed = " ".join(item[2] for item in chosen)
        if omitted:
            compressed += f" […{omitted}]"
        if count_tokens(compressed).tokens >= count_tokens(text).tokens:
            compressed = text
            omitted = 0
        return compressed, self._metadata(text, compressed, len(sentences), len(chosen), query)

    @staticmethod
    def _metadata(text: str, compressed: str, total: int, kept: int, query: str) -> dict[str, Any]:
        before = count_tokens(text).tokens
        after = count_tokens(compressed).tokens
        return {
            "method": "QueryAwareExtractive",
            "deprecated_alias": "LLMLinguaLite",
            "sentences_total": total,
            "sentences_kept": kept,
            "query_aware": bool(query.strip()),
            "savings_pct": round(max(0, before - after) / before * 100, 2) if before else 0.0,
        }


def compress_llm_lingua(
    text: str,
    target_ratio: float = 0.5,
    preserve_questions: bool = True,
    query: str = "",
) -> tuple[str, dict[str, Any]]:
    return LLMLinguaLite(target_ratio=target_ratio, preserve_questions=preserve_questions).compress(text, query=query)
