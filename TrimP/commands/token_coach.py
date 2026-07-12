"""
/token-coach — 30-day trend analysis with specific fixes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.table import Table

from TrimP.db import db
from TrimP.quality import score_to_bar

console = Console()


def run(days: int = 30) -> None:
    console.rule(f"[bold cyan]📈 Token Coach — {days}-Day Trend Analysis[/bold cyan]")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    with db() as conn:
        sessions = conn.execute(
            """SELECT s.id, s.started_at, s.quality_grade, s.tokens_saved,
                      s.total_tokens_in + s.total_tokens_out as total_tokens
               FROM sessions s
               WHERE s.started_at >= ?
               ORDER BY s.started_at ASC""",
            (cutoff,),
        ).fetchall()

        daily = conn.execute(
            """SELECT date(started_at) as day,
                      COUNT(*) as sessions,
                      SUM(tokens_saved) as saved,
                      SUM(total_tokens_in + total_tokens_out) as total,
                      AVG(CASE quality_grade
                          WHEN 'S' THEN 1.0 WHEN 'A' THEN 0.85 WHEN 'B' THEN 0.70
                          WHEN 'C' THEN 0.55 WHEN 'D' THEN 0.35 ELSE 0.0 END) as avg_score
               FROM sessions
               WHERE started_at >= ?
               GROUP BY day ORDER BY day""",
            (cutoff,),
        ).fetchall()

        compression_trends = conn.execute(
            """SELECT c.compressor,
                      SUM(c.tokens_before - c.tokens_after) as saved,
                      COUNT(*) as events
               FROM compressions c
               JOIN sessions s ON c.session_id = s.id
               WHERE s.started_at >= ?
               GROUP BY c.compressor
               ORDER BY saved DESC""",
            (cutoff,),
        ).fetchall()

    if not sessions:
        console.print(f"[dim]No sessions in the last {days} days.[/dim]")
        return

    # Daily trend table
    console.print(f"\n[bold]Daily Breakdown ({len(list(daily))} days with activity)[/bold]")
    t = Table(show_header=True, header_style="bold blue")
    t.add_column("Date", width=12)
    t.add_column("Sessions", justify="right", width=9)
    t.add_column("Tokens Saved", justify="right", width=14)
    t.add_column("Quality Trend", width=22)
    for row in daily:
        bar = score_to_bar(row["avg_score"] or 0.0, 15)
        t.add_row(row["day"], str(row["sessions"]), f"{row['saved']:,}", bar)
    console.print(t)

    # Compression breakdown
    console.print("\n[bold]Top Compression Sources[/bold]")
    t2 = Table(show_header=True, header_style="bold magenta")
    t2.add_column("Compressor", style="cyan", width=22)
    t2.add_column("Events", justify="right", width=8)
    t2.add_column("Tokens Saved", justify="right", width=14)
    for row in compression_trends:
        t2.add_row(row["compressor"], str(row["events"]), f"{row['saved'] or 0:,}")
    console.print(t2)

    # Totals + advice
    total_sessions = len(sessions)
    total_saved = sum(s["tokens_saved"] or 0 for s in sessions)
    grades = [s["quality_grade"] for s in sessions if s["quality_grade"]]
    avg_grade = _avg_grade(grades)

    console.rule("[bold]Summary[/bold]")
    console.print(f"  Sessions analyzed: [bold]{total_sessions}[/bold]")
    console.print(f"  Total tokens saved: [bold green]{total_saved:,}[/bold green]")
    console.print(f"  Average quality grade: [bold]{avg_grade}[/bold]")

    _trend_advice(grades)


def _avg_grade(grades: list[str]) -> str:
    grade_map = {"S": 1.0, "A": 0.85, "B": 0.70, "C": 0.55, "D": 0.35, "F": 0.0}
    if not grades:
        return "?"
    avg = sum(grade_map.get(g, 0) for g in grades) / len(grades)
    for g, threshold in [("S", 0.95), ("A", 0.82), ("B", 0.67), ("C", 0.52), ("D", 0.35)]:
        if avg >= threshold:
            return g
    return "F"


def _trend_advice(grades: list[str]) -> None:
    if not grades:
        return
    recent = grades[-5:] if len(grades) >= 5 else grades
    grade_map = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
    trend = [grade_map.get(g, 0) for g in recent]

    console.rule("[bold]Trend Advice[/bold]")
    if len(trend) >= 2 and trend[-1] > trend[0]:
        console.print("  [green]↑ Quality improving[/green] — keep current compression settings")
    elif len(trend) >= 2 and trend[-1] < trend[0]:
        console.print("  [red]↓ Quality declining[/red] — run `TrimP token-optimizer` for a full audit")
    else:
        console.print("  [yellow]→ Quality stable[/yellow] — consider enabling additional compressors")

    if grade_map.get(recent[-1] if recent else "C", 0) <= 2:
        console.print("  [bold red]⚠ Recent sessions rated C or below.[/bold red]")
        console.print("    Fix: Enable verbosity nudges, run `/token-optimizer`, prune MEMORY.md")
