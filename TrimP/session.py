"""
Session management — create, update, track active session.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from TrimP.db import db, get_config, now_iso

_SESSION_FILE = Path.home() / ".trimp" / "active_session"


def create_session() -> str:
    """Create a new session and persist its ID."""
    session_id = str(uuid.uuid4())
    cwd = os.getcwd()
    repo = _detect_repo(cwd)
    branch = _detect_branch(cwd)
    model = os.environ.get("COPILOT_MODEL", "claude-sonnet-4.6")

    with db() as conn:
        conn.execute(
            """INSERT INTO sessions(id, started_at, cwd, repository, branch, model)
               VALUES (?,?,?,?,?,?)""",
            (session_id, now_iso(), cwd, repo, branch, model),
        )

    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSION_FILE.write_text(session_id)
    return session_id


def get_active_session() -> str | None:
    """Return the current active session ID, or None."""
    if not _SESSION_FILE.exists():
        return None
    sid = _SESSION_FILE.read_text().strip()
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE id=? AND status='active'", (sid,)
        ).fetchone()
    return row["id"] if row else None


def get_or_create_session() -> str:
    sid = get_active_session()
    if not sid:
        sid = create_session()
    return sid


def end_session(session_id: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE sessions SET ended_at=?, status='compacted' WHERE id=?",
            (now_iso(), session_id),
        )
    if _SESSION_FILE.exists():
        _SESSION_FILE.unlink()


def record_turn(
    session_id: str,
    turn_index: int,
    user_message: str,
    assistant_response: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    tokens_saved: int = 0,
    model: str | None = None,
) -> int:
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO turns
               (session_id, turn_index, user_message, assistant_response,
                tokens_in, tokens_out, tokens_saved, model, timestamp)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                session_id,
                turn_index,
                user_message,
                assistant_response,
                tokens_in,
                tokens_out,
                tokens_saved,
                model or os.environ.get("COPILOT_MODEL", ""),
                now_iso(),
            ),
        )
        conn.execute(
            """UPDATE sessions
               SET total_tokens_in  = total_tokens_in  + ?,
                   total_tokens_out = total_tokens_out + ?,
                   tokens_saved     = tokens_saved     + ?
               WHERE id=?""",
            (tokens_in, tokens_out, tokens_saved, session_id),
        )
        return cur.lastrowid


def record_token_budget(session_id: str, tokens_used: int, tokens_saved: int, context_window: int = 200_000) -> None:
    with db() as conn:
        conn.execute(
            """INSERT INTO token_budgets(session_id, context_window, tokens_used, tokens_saved, snapshot_at)
               VALUES (?,?,?,?,?)""",
            (session_id, context_window, tokens_used, tokens_saved, now_iso()),
        )


def get_recent_sessions(limit: int = 30) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """SELECT DISTINCT s.*,
                  (SELECT grade FROM quality_scores WHERE session_id = s.id ORDER BY scored_at DESC LIMIT 1) AS last_grade,
                  (SELECT cost_saved_sonnet FROM savings WHERE session_id = s.id ORDER BY period_end DESC LIMIT 1) AS cost_saved
               FROM sessions s
               ORDER BY s.started_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def _detect_repo(cwd: str) -> str:
    try:
        import subprocess

        out = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], cwd=cwd, stderr=subprocess.DEVNULL, text=True
        )
        return out.strip().split("/")[-1].replace(".git", "")
    except Exception:
        return Path(cwd).name


def _detect_branch(cwd: str) -> str:
    try:
        import subprocess

        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd, stderr=subprocess.DEVNULL, text=True
        )
        return out.strip()
    except Exception:
        return "main"
