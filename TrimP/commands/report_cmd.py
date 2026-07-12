"""report — per-component token breakdown."""
from __future__ import annotations
from rich.console import Console
from rich.table import Table
from TrimP.db import db
from TrimP.session import get_or_create_session

console = Console()

def run(session_id: str | None = None) -> None:
    sid = session_id or get_or_create_session()
    console.print("[bold]📋 Per-Component Token Report[/bold]\n")

    with db() as conn:
        comp_rows = conn.execute(
            """SELECT compressor,
                      COUNT(*) as events,
                      SUM(tokens_before) as t_before,
                      SUM(tokens_after) as t_after,
                      SUM(tokens_before - tokens_after) as saved
               FROM compressions WHERE session_id=?
               GROUP BY compressor ORDER BY saved DESC""",
            (sid,),
        ).fetchall()

        loop_rows = conn.execute(
            "SELECT loop_type, COUNT(*) as c FROM loop_detections WHERE session_id=? GROUP BY loop_type",
            (sid,),
        ).fetchall()

        arc_rows = conn.execute(
            "SELECT tool_name, COUNT(*) as c, SUM(char_count) as total_chars FROM archives WHERE session_id=? GROUP BY tool_name",
            (sid,),
        ).fetchall()

        mode_rows = conn.execute(
            "SELECT mode, COUNT(*) as c FROM activity_modes WHERE session_id=? GROUP BY mode ORDER BY c DESC",
            (sid,),
        ).fetchall()

    # Compression breakdown
    console.rule("[bold]Compression by Component[/bold]")
    if comp_rows:
        t = Table(show_header=True, header_style="bold blue")
        t.add_column("Compressor", style="cyan", width=22)
        t.add_column("Events", justify="right", width=8)
        t.add_column("Before", justify="right", width=10)
        t.add_column("After", justify="right", width=10)
        t.add_column("Saved", justify="right", width=10)
        t.add_column("Ratio", justify="right", width=8)
        for row in comp_rows:
            before = row["t_before"] or 1
            saved = row["saved"] or 0
            t.add_row(
                row["compressor"], str(row["events"]),
                f"{before:,}", f"{row['t_after'] or 0:,}",
                f"[green]{saved:,}[/green]", f"{saved/before:.0%}",
            )
        console.print(t)
    else:
        console.print("[dim]No compression events.[/dim]")

    # Loop detections
    console.rule("[bold]Loop Detections[/bold]")
    if loop_rows:
        for row in loop_rows:
            console.print(f"  {row['loop_type']}: [red]{row['c']}[/red] events")
    else:
        console.print("  [green]✓ No loops detected[/green]")

    # Archives
    console.rule("[bold]Progressive Disclosure Archives[/bold]")
    if arc_rows:
        for row in arc_rows:
            console.print(f"  {row['tool_name'] or 'unknown'}: {row['c']} archived  ({row['total_chars']:,} chars)")
    else:
        console.print("  [dim]No archives.[/dim]")

    # Activity modes
    console.rule("[bold]Activity Modes[/bold]")
    if mode_rows:
        for row in mode_rows:
            console.print(f"  {row['mode']}: {row['c']} detections")
    else:
        console.print("  [dim]No activity data.[/dim]")
