"""
Delta compressor — file re-read diff mode.
2,000-token re-read → ~50 tokens when file unchanged.
"""

from __future__ import annotations

import difflib
import hashlib
from pathlib import Path

from TrimP.db import db, now_iso


class DeltaCompressor:
    """Track file contents and emit diffs instead of full re-reads."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._cache: dict[str, tuple[str, str]] = {}  # path → (hash, content)

    def compress_file_read(self, path: str, content: str) -> tuple[str, int]:
        """
        Given a file path + current content, return compressed representation.
        If unchanged → token count summary only.
        If changed → unified diff.
        """
        before = _est(content)
        norm_path = str(Path(path).resolve())
        current_hash = _hash(content)

        if norm_path in self._cache:
            prev_hash, prev_content = self._cache[norm_path]
            if prev_hash == current_hash:
                summary = f"[FILE UNCHANGED: {norm_path}] ({_lines(content)} lines, {before} tokens)"
                self._cache[norm_path] = (current_hash, content)
                return summary, max(0, before - _est(summary))

            diff = _unified_diff(prev_content, content, norm_path)
            self._cache[norm_path] = (current_hash, content)
            diff_tokens = _est(diff)
            return diff, max(0, before - diff_tokens)

        self._cache[norm_path] = (current_hash, content)
        self._persist_hash(norm_path, current_hash)
        return content, 0

    def load_from_db(self) -> None:
        """Load previously seen file hashes from this session."""
        with db() as conn:
            rows = conn.execute(
                "SELECT file_path, last_hash FROM session_files WHERE session_id=?",
                (self.session_id,),
            ).fetchall()
        for row in rows:
            if row["last_hash"]:
                self._cache[row["file_path"]] = (row["last_hash"], "")

    def _persist_hash(self, path: str, file_hash: str) -> None:
        with db() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO session_files
                   (session_id, file_path, last_hash, last_seen_at)
                   VALUES (?,?,?,?)""",
                (self.session_id, path, file_hash, now_iso()),
            )


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _lines(content: str) -> int:
    return content.count("\n") + 1


def _est(t: str) -> int:
    return max(1, len(t) // 4)


def _unified_diff(old: str, new: str, fname: str) -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{fname}", tofile=f"b/{fname}", n=2))
    if not diff:
        return f"[NO DIFF: {fname}]"
    return "".join(diff)
