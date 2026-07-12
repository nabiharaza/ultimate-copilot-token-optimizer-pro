"""Real-time monitoring — Watch TrimP activity live."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table

from TrimP.db import db

console = Console()


def monitor_realtime():
    """Monitor TrimP activity in real-time."""
    console.print("🔍 [bold cyan]TrimP Real-Time Monitor[/bold cyan]")
    console.print("   Watching for compression events...\n")
    console.print("   Press Ctrl+C to stop\n")

    last_count = 0
    last_check = datetime.now()

    try:
        with Live(generate_table([], 0, 0, 0), refresh_per_second=2) as live:
            while True:
                # Get recent compression events
                with db() as conn:
                    rows = conn.execute(
                        """SELECT 
                            compressor,
                            tokens_before,
                            tokens_after,
                            tokens_before - tokens_after as saved,
                            compressed_at
                           FROM compressions
                           ORDER BY compressed_at DESC
                           LIMIT 20"""
                    ).fetchall()

                    # Get total stats
                    stats = conn.execute(
                        """SELECT 
                            COUNT(*) as total_compressions,
                            SUM(tokens_before - tokens_after) as total_saved,
                            AVG(CAST(tokens_before - tokens_after AS FLOAT) / 
                                NULLIF(tokens_before, 0) * 100) as avg_reduction
                           FROM compressions"""
                    ).fetchone()

                events = [dict(r) for r in rows]
                current_count = len(events)

                # Check if new events
                if current_count != last_count:
                    # Beep on new event
                    if current_count > last_count:
                        console.bell()
                    last_count = current_count
                    last_check = datetime.now()

                # Update display
                live.update(
                    generate_table(
                        events,
                        stats["total_compressions"] or 0,
                        stats["total_saved"] or 0,
                        stats["avg_reduction"] or 0,
                    )
                )

                time.sleep(0.5)  # Check every 0.5 seconds

    except KeyboardInterrupt:
        console.print("\n✓ Monitoring stopped")
        sys.exit(0)


def generate_table(events, total_compressions, total_saved, avg_reduction):
    """Generate the live monitoring table."""
    table = Table(title="🔍 Real-Time Compression Monitor", title_style="bold cyan")

    table.add_column("Time", style="dim", width=10)
    table.add_column("Compressor", style="cyan", width=15)
    table.add_column("Before", justify="right", style="yellow", width=10)
    table.add_column("After", justify="right", style="green", width=10)
    table.add_column("Saved", justify="right", style="bold green", width=10)
    table.add_column("%", justify="right", style="magenta", width=8)

    for event in events:
        time_str = event["compressed_at"].split("T")[1][:8] if event["compressed_at"] else "?"
        before = event["tokens_before"] or 0
        after = event["tokens_after"] or 0
        saved = event["saved"] or 0
        percent = (saved / before * 100) if before > 0 else 0

        table.add_row(
            time_str,
            event["compressor"][:15],
            f"{before:,}",
            f"{after:,}",
            f"{saved:,}",
            f"{percent:.1f}%",
        )

    # Add summary row
    if events:
        table.add_section()
        table.add_row(
            "[bold]TOTAL",
            f"[bold]{total_compressions:,} events",
            "",
            "",
            f"[bold]{total_saved:,}",
            f"[bold]{avg_reduction:.1f}%",
        )

    return table


def monitor_logs():
    """Tail the auto-runner log file."""
    log_file = Path.home() / ".trimp" / "auto-runner.log"

    if not log_file.exists():
        console.print("❌ Auto-runner log not found")
        console.print(f"   Expected: {log_file}")
        console.print("\n   Is the auto-runner running?")
        console.print("   Start it with: TrimP auto start")
        return

    console.print(f"📝 [bold cyan]Tailing auto-runner log[/bold cyan]")
    console.print(f"   {log_file}\n")
    console.print("   Press Ctrl+C to stop\n")

    try:
        # Use tail -f to follow the log
        import subprocess

        proc = subprocess.Popen(
            ["tail", "-f", str(log_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        for line in proc.stdout:
            console.print(line.rstrip())

    except KeyboardInterrupt:
        console.print("\n✓ Log monitoring stopped")
        if proc:
            proc.terminate()
        sys.exit(0)


if __name__ == "__main__":
    monitor_realtime()
