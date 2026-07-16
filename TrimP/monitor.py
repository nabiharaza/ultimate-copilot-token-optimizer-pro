"""Real-time monitoring — Watch TrimP activity live."""

from __future__ import annotations

import os
import sys
import time
import signal
import subprocess
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table

from TrimP.db import db

console = Console()
EDITOR_MONITOR_PID = Path.home() / ".trimp" / "editor-monitor.pid"
EDITOR_MONITOR_LOG = Path.home() / ".trimp" / "editor-monitor.log"


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


def _service_status() -> dict:
    status = {
        "byok": "down",
        "ide_proxy": "down",
        "ide_detail": "",
        "configured_ides": [],
        "editor_probes": [],
        "spooled_traces": 0,
    }
    try:
        import httpx

        response = httpx.get("http://127.0.0.1:8766/v1/health", timeout=1.0, trust_env=False)
        status["byok"] = "up" if response.status_code == 200 else "degraded"
    except Exception:
        pass
    try:
        from TrimP.intellij_proxy import probe_proxy, proxy_status

        proxy = proxy_status()
        status["ide_proxy"] = "up" if proxy.get("running") else "down"
        status["ide_detail"] = f"{proxy.get('host', '127.0.0.1')}:{proxy.get('port', 8767)}"
        configured = list(proxy.get("configured_ides") or [])
        if proxy.get("vscode_configured"):
            configured.append({
                "product": "VS Code",
                "path": proxy.get("vscode_settings", ""),
                "host": "127.0.0.1",
                "port": int(proxy.get("vscode_port") or proxy.get("port") or 8767),
            })
        status["configured_ides"] = configured
        status["spooled_traces"] = int(proxy.get("spooled_traces") or 0)
        probes = []
        seen_editors = set()
        for item in configured:
            product = str(item.get("product") or "editor")
            editor = "vscode" if "code" in product.lower() else "rider" if "rider" in product.lower() else "pycharm"
            if editor in seen_editors:
                continue
            seen_editors.add(editor)
            probes.append(probe_proxy(editor=editor, port=int(item.get("port") or proxy.get("port") or 8767)))
        status["editor_probes"] = probes
    except Exception as exc:
        status["ide_detail"] = str(exc)[:80]
    return status


def _sync_editor_sources() -> tuple[int, int]:
    # The dashboard module owns the canonical DB upsert logic for these sources.
    from TrimP.dashboard import server as dashboard_server

    return dashboard_server._sync_debug_logs(limit=400), dashboard_server._sync_agent_logs(limit=400)


def _recent_editor_rows(limit: int = 12) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """SELECT c.compressed_at, c.request_source, c.model_used,
                      c.tokens_before, c.tokens_after, s.repository, s.cwd
               FROM compressions c
               LEFT JOIN sessions s ON s.id = c.session_id
               WHERE c.source='byok'
               ORDER BY c.compressed_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _latest_debug_import() -> dict:
    with db() as conn:
        row = conn.execute(
            """SELECT imported_at, occurred_at, ide, model, repository, cwd
               FROM copilot_debug_turns
               ORDER BY imported_at DESC LIMIT 1"""
        ).fetchone()
    return dict(row) if row else {}


def _editor_table(status: dict, debug_imports: int, agent_imports: int, rows: list[dict], latest_debug: dict) -> Table:
    table = Table(title="TrimPy Editor Capture Monitor", title_style="bold cyan")
    table.add_column("Signal", style="cyan", width=18)
    table.add_column("Status", style="bold", width=14)
    table.add_column("Detail", overflow="fold")

    table.add_row("BYOK trace", status["byok"], "http://127.0.0.1:8766/v1/health")
    table.add_row("IDE HTTPS proxy", status["ide_proxy"], status.get("ide_detail") or "127.0.0.1:8767")
    configured = ", ".join(sorted({str(item.get("product") or "IDE") for item in status.get("configured_ides", [])}))
    table.add_row("Configured editors", str(len(status.get("configured_ides", []))), configured or "none")
    table.add_row("Spooled traces", str(status.get("spooled_traces", 0)), "should stay at 0 while BYOK trace is up")
    for probe in status.get("editor_probes", []):
        detail = probe.get("request_source") or probe.get("error") or "no response"
        table.add_row(f"{probe.get('editor', 'editor')} probe", "intercepted" if probe.get("intercepted") else "down", str(detail))
    table.add_row("VS Code imports", str(debug_imports), latest_debug.get("imported_at") or "no debug turns imported yet")
    table.add_row("Agent log imports", str(agent_imports), "Copilot session-state snapshots")

    if rows:
        table.add_section()
        table.add_row("Recent source", "Model", "Repository / time")
        for row in rows[:8]:
            before = int(row.get("tokens_before") or 0)
            after = int(row.get("tokens_after") or 0)
            saved = before - after
            repo = str(row.get("repository") or Path(str(row.get("cwd") or "")).name or "unknown")
            detail = f"{repo} · {row.get('compressed_at') or '?'} · saved {saved:,}"
            table.add_row(str(row.get("request_source") or "unknown")[:18], str(row.get("model_used") or "unknown")[:14], detail)
    return table


def monitor_editors(interval: float = 1.0):
    """Continuously import editor history and show capture health."""
    console.print("[bold cyan]TrimPy Editor Monitor[/bold cyan]")
    console.print("Watching VS Code debug logs, Copilot agent logs, BYOK trace, and IDE proxy health.")
    console.print("Press Ctrl+C to stop.\n")
    try:
        with Live(_editor_table(_service_status(), 0, 0, [], {}), refresh_per_second=2) as live:
            while True:
                debug_imports, agent_imports = _sync_editor_sources()
                status = _service_status()
                live.update(_editor_table(status, debug_imports, agent_imports, _recent_editor_rows(), _latest_debug_import()))
                time.sleep(max(0.25, interval))
    except KeyboardInterrupt:
        console.print("\n✓ Editor monitoring stopped")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start_editor_monitor(interval: float = 1.0):
    """Start near-real-time editor capture in the background."""
    EDITOR_MONITOR_PID.parent.mkdir(parents=True, exist_ok=True)
    if EDITOR_MONITOR_PID.exists():
        try:
            pid = int(EDITOR_MONITOR_PID.read_text(encoding="utf-8").strip())
            if _pid_alive(pid):
                console.print(f"[yellow]Editor monitor already running[/yellow] (PID: {pid})")
                return
        except Exception:
            pass
        EDITOR_MONITOR_PID.unlink(missing_ok=True)
    command = [
        sys.executable,
        "-m",
        "TrimP.cli",
        "monitor",
        "--mode",
        "editors",
        "--interval",
        str(interval),
    ]
    log = EDITOR_MONITOR_LOG.open("ab")
    process = subprocess.Popen(
        command,
        cwd=str(Path(__file__).resolve().parent.parent),
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    log.close()
    EDITOR_MONITOR_PID.write_text(str(process.pid), encoding="utf-8")
    console.print(f"[green]✓ Editor monitor started[/green] (PID: {process.pid})")
    console.print(f"  Log: {EDITOR_MONITOR_LOG}")


def stop_editor_monitor():
    if not EDITOR_MONITOR_PID.exists():
        console.print("Editor monitor is not running")
        return
    try:
        pid = int(EDITOR_MONITOR_PID.read_text(encoding="utf-8").strip())
    except Exception:
        EDITOR_MONITOR_PID.unlink(missing_ok=True)
        console.print("Editor monitor PID file was invalid; cleaned up")
        return
    if not _pid_alive(pid):
        EDITOR_MONITOR_PID.unlink(missing_ok=True)
        console.print("Editor monitor process was not running; cleaned up")
        return
    os.kill(pid, signal.SIGTERM)
    EDITOR_MONITOR_PID.unlink(missing_ok=True)
    console.print(f"[green]✓ Editor monitor stopped[/green] (PID: {pid})")


def status_editor_monitor():
    if not EDITOR_MONITOR_PID.exists():
        console.print("Editor monitor is not running")
        return
    try:
        pid = int(EDITOR_MONITOR_PID.read_text(encoding="utf-8").strip())
    except Exception:
        console.print("Editor monitor PID file is invalid")
        return
    if _pid_alive(pid):
        console.print(f"[green]✓ Editor monitor is running[/green] (PID: {pid})")
        console.print(f"  Log: {EDITOR_MONITOR_LOG}")
        if EDITOR_MONITOR_LOG.exists():
            lines = EDITOR_MONITOR_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines[-8:]:
                console.print(f"  {line}")
    else:
        EDITOR_MONITOR_PID.unlink(missing_ok=True)
        console.print("Editor monitor was not running; cleaned up")


if __name__ == "__main__":
    monitor_realtime()
