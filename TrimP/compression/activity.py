"""
Activity mode detector + decision extractor.
Detects task type and extracts key decisions from long outputs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from TrimP.db import db, now_iso

import json

MODES = ("exploration", "implementation", "debug", "review", "test", "planning")

# Keywords that signal each mode
_MODE_SIGNALS: dict[str, list[str]] = {
    "exploration": ["explore", "understand", "how does", "what is", "show me", "find", "search", "look"],
    "implementation": ["implement", "create", "build", "write", "add", "make", "generate", "develop"],
    "debug": ["bug", "error", "fail", "crash", "issue", "broken", "fix", "debug", "trace", "exception"],
    "review": ["review", "check", "audit", "inspect", "analyze", "assess", "evaluate", "score"],
    "test": ["test", "spec", "coverage", "passing", "failing", "assert", "pytest", "jest"],
    "planning": ["plan", "design", "architecture", "approach", "strategy", "roadmap", "sketch"],
}

_DECISION_MARKERS = re.compile(
    r"(?i)(?:^|\n)\s*(?:•|\*|-|→|>|[0-9]+\.)\s*(.{20,200})(?=\n|$)",
    re.MULTILINE,
)

_DECISION_PHRASES = re.compile(
    r"(?i)\b(?:decided|chose|will use|going with|approach is|strategy:|conclusion:|key insight:|"
    r"recommendation:|using|selected|opted for)\b.{10,150}"
)


class ActivityMode:
    """Detect activity mode and extract key decisions."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.current_mode: str = "exploration"
        self.confidence: float = 0.0

    def detect(self, text: str) -> ModeResult:
        text_lower = text.lower()
        scores: dict[str, float] = {}

        for mode, keywords in _MODE_SIGNALS.items():
            hits = sum(text_lower.count(kw) for kw in keywords)
            scores[mode] = hits

        total = max(1, sum(scores.values()))
        normed = {m: s / total for m, s in scores.items()}
        best_mode = max(normed, key=lambda m: normed[m])
        confidence = normed[best_mode]

        if confidence > 0.25 and best_mode != self.current_mode:
            self.current_mode = best_mode
            self.confidence = confidence
            self._persist(best_mode, confidence, [])

        decisions = self.extract_decisions(text)
        if decisions:
            self._persist(best_mode, confidence, decisions)

        return ModeResult(mode=best_mode, confidence=confidence, decisions=decisions)

    def extract_decisions(self, text: str) -> list[str]:
        """Extract key decisions from output."""
        found: list[str] = []

        # Explicit decision phrases
        for m in _DECISION_PHRASES.finditer(text):
            s = m.group(0).strip()
            if s and s not in found:
                found.append(s[:150])

        # Bullet/list items in planning context
        if self.current_mode in ("planning", "implementation"):
            for m in _DECISION_MARKERS.finditer(text):
                s = m.group(1).strip()
                if len(s) > 20 and s not in found:
                    found.append(s[:150])

        return found[:10]  # cap at 10 decisions

    def nudge_for_mode(self) -> str | None:
        """Return a model routing nudge for the current activity mode."""
        routing = {
            "exploration": "Use Haiku for fast lookup tasks",
            "implementation": "Sonnet recommended for implementation",
            "debug": "Sonnet/Opus for complex debugging",
            "review": "Haiku sufficient for most reviews",
            "test": "Haiku for test generation",
            "planning": "Sonnet for architecture/planning",
        }
        return routing.get(self.current_mode)

    def _persist(self, mode: str, confidence: float, decisions: list[str]) -> None:
        with db() as conn:
            conn.execute(
                """INSERT INTO activity_modes
                   (session_id, mode, confidence, decisions, switched_at)
                   VALUES (?,?,?,?,?)""",
                (self.session_id, mode, confidence, json.dumps(decisions), now_iso()),
            )


@dataclass
class ModeResult:
    mode: str
    confidence: float
    decisions: list[str]
