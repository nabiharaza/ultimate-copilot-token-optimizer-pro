"""
Compaction hooks — checkpoint before auto-compact, restore/re-orient after.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from TrimP.db import db, now_iso

CHECKPOINT_DIR = Path.home() / ".trimp" / "checkpoints"


class CompactionManager:
    """Manage checkpoints around Copilot auto-compaction events."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(
        self,
        title: str,
        overview: str,
        work_done: str,
        technical_details: str,
        important_files: list[str],
        next_steps: str,
        token_count: int = 0,
        quality_score: float = 0.0,
    ) -> int:
        with db() as conn:
            # Get next checkpoint number
            row = conn.execute(
                "SELECT COALESCE(MAX(checkpoint_num), 0) + 1 as n FROM checkpoints WHERE session_id=?",
                (self.session_id,),
            ).fetchone()
            num = row["n"]

            cur = conn.execute(
                """INSERT INTO checkpoints
                   (session_id, checkpoint_num, title, overview, work_done,
                    technical_details, important_files, next_steps,
                    token_count, quality_score, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    self.session_id, num, title, overview, work_done,
                    technical_details, json.dumps(important_files), next_steps,
                    token_count, quality_score, now_iso(),
                ),
            )
            checkpoint_id = cur.lastrowid

        # Write to disk (survives DB corruption)
        self._write_to_disk(num, {
            "session_id": self.session_id,
            "checkpoint_num": num,
            "title": title,
            "overview": overview,
            "work_done": work_done,
            "technical_details": technical_details,
            "important_files": important_files,
            "next_steps": next_steps,
            "created_at": now_iso(),
        })

        return checkpoint_id

    def get_latest_checkpoint(self) -> dict | None:
        with db() as conn:
            row = conn.execute(
                """SELECT * FROM checkpoints
                   WHERE session_id=? ORDER BY checkpoint_num DESC LIMIT 1""",
                (self.session_id,),
            ).fetchone()
        return dict(row) if row else None

    def restore_checkpoint(self, checkpoint_id: int | None = None) -> str:
        """
        Generate a Context Intel Digest for post-compaction re-orientation.
        Returns a compact summary to inject back into context.
        """
        with db() as conn:
            if checkpoint_id:
                row = conn.execute(
                    "SELECT * FROM checkpoints WHERE id=?", (checkpoint_id,)
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT * FROM checkpoints WHERE session_id=?
                       ORDER BY checkpoint_num DESC LIMIT 1""",
                    (self.session_id,),
                ).fetchone()

        if not row:
            return self._cold_resume_digest()

        cp = dict(row)
        files = json.loads(cp.get("important_files") or "[]")

        with db() as conn:
            conn.execute(
                "UPDATE checkpoints SET restored_at=? WHERE id=?",
                (now_iso(), cp["id"]),
            )

        return self._format_digest(cp, files)

    def _format_digest(self, cp: dict, files: list[str]) -> str:
        return f"""╔══ CONTEXT INTEL DIGEST (post-compaction) ══╗
│ Session: {cp['session_id'][:16]}...
│ Checkpoint #{cp['checkpoint_num']}: {cp.get('title', '')}
│ Saved: {cp.get('created_at', '')[:19]}
╠══ OVERVIEW ══╗
{cp.get('overview', '')}
╠══ WORK DONE ══╗
{cp.get('work_done', '')}
╠══ TECHNICAL ══╗
{cp.get('technical_details', '')}
╠══ KEY FILES ({len(files)}) ══╗
{chr(10).join('  • ' + f for f in files)}
╠══ NEXT STEPS ══╗
{cp.get('next_steps', '')}
╚══════════════════════════════╝"""

    def _cold_resume_digest(self) -> str:
        return (
            "No checkpoint found for this session. "
            "Run `TrimP resume-lean` for guided cold resume."
        )

    def list_checkpoints(self) -> list[dict]:
        with db() as conn:
            rows = conn.execute(
                """SELECT checkpoint_num, title, overview, token_count, quality_score, created_at
                   FROM checkpoints WHERE session_id=? ORDER BY checkpoint_num DESC""",
                (self.session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _write_to_disk(self, num: int, data: dict) -> None:
        path = CHECKPOINT_DIR / f"{self.session_id[:8]}-cp{num:04d}.json"
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass
