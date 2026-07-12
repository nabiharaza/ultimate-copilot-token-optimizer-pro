"""
Archive manager — large tool results (>4K chars) archived to disk, expandable on demand.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from TrimP.db import db, get_config, now_iso

ARCHIVE_DIR = Path.home() / ".trimp" / "archives"


class ArchiveManager:
    """Archive large tool results, replace with summary + key."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.threshold = int(get_config("archive.threshold_chars", "4096"))
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    def maybe_archive(self, content: str, tool_name: str = "") -> tuple[str, int]:
        """
        If content exceeds threshold, archive it and return a placeholder.
        Returns (output, tokens_saved).
        """
        if len(content) <= self.threshold:
            return content, 0

        before = _est(content)
        key = _make_key(content)
        summary = _summarize(content)

        self._write_archive(key, content, summary, tool_name)

        placeholder = (
            f"[ARCHIVED: {key}]\n"
            f"Tool: {tool_name or 'unknown'}\n"
            f"Size: {len(content):,} chars ({before:,} tokens)\n"
            f"Summary: {summary}\n"
            f"Use `TrimP expand {key}` to retrieve full content."
        )
        return placeholder, max(0, before - _est(placeholder))

    def expand(self, key: str) -> str | None:
        """Retrieve archived content by key."""
        with db() as conn:
            row = conn.execute(
                "SELECT content FROM archives WHERE archive_key=?", (key,)
            ).fetchone()
        if row:
            with db() as conn:
                conn.execute(
                    "UPDATE archives SET expanded_at=? WHERE archive_key=?",
                    (now_iso(), key),
                )
            return row["content"]

        # Fall back to disk
        path = ARCHIVE_DIR / f"{key}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def list_archives(self) -> list[dict]:
        with db() as conn:
            rows = conn.execute(
                """SELECT archive_key, tool_name, char_count, summary, archived_at, expanded_at
                   FROM archives WHERE session_id=? ORDER BY archived_at DESC""",
                (self.session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _write_archive(self, key: str, content: str, summary: str, tool_name: str) -> None:
        # Write to disk
        path = ARCHIVE_DIR / f"{key}.txt"
        path.write_text(content, encoding="utf-8")

        # Write to DB
        with db() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO archives
                   (session_id, archive_key, content, summary, char_count, tool_name, archived_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (self.session_id, key, content, summary, len(content), tool_name, now_iso()),
            )


def _make_key(content: str) -> str:
    h = hashlib.sha256(content.encode()).hexdigest()[:8]
    return f"arc-{h}"


def _summarize(content: str) -> str:
    """Extract first meaningful line + char count."""
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    first = lines[0][:120] if lines else ""
    return f"{first} [{len(content):,} chars, {len(lines)} lines]"


def _est(t: str) -> int:
    return max(1, len(t) // 4)
