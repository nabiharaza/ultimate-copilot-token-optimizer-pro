"""quick — 10-second health check."""
from __future__ import annotations
from rich.console import Console
from TrimP.db import db
from TrimP.quality import score_session, score_to_bar
from TrimP.session import get_or_create_session

console = Console()

def run() -> None:
    sid = get_or_create_session()
    report = score_session(sid)
    grade_colors = {"S": "bright_green","A":"green","B":"yellow","C":"orange3","D":"red","F":"bright_red"}
    c = grade_colors.get(report.grade, "white")

    with db() as conn:
        sess = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        loop_count = conn.execute(
            "SELECT COUNT(*) as c FROM loop_detections WHERE session_id=?", (sid,)
        ).fetchone()["c"]
        arc_count = conn.execute(
            "SELECT COUNT(*) as c FROM archives WHERE session_id=?", (sid,)
        ).fetchone()["c"]

    console.print(f"⚡ [bold]Quick Health[/bold]  [{c}]{report.grade}[/{c}] ({report.overall:.0%})")
    console.print(f"   {score_to_bar(report.overall, 20)}")
    saved = sess["tokens_saved"] if sess else 0
    console.print(f"   Tokens saved: [green]{saved:,}[/green]  Loops: {'🔴 '+str(loop_count) if loop_count else '🟢 0'}  Archives: {arc_count}")
    if report.overall < 0.5:
        console.print("   [yellow]Run `TrimP token-optimizer` for full audit[/yellow]")
