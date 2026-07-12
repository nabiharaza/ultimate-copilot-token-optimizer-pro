"""
TrimP — Copilot Token Optimizer CLI
Usage: TrimP <command> [options]
"""

from __future__ import annotations

import typer
import os
import json
from rich.console import Console

app = typer.Typer(
    name="TrimP",
    help="🔧 Copilot Token Optimizer — compression, quality scoring, and analytics",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


# ──────────────────────── init ───────────────────────────────────────────

@app.command()
def init():
    """Initialize TrimP data directory and default config."""
    from TrimP.db import get_connection, insert_config_defaults, DB_PATH
    get_connection()
    insert_config_defaults()
    console.print(f"[green]✓ TrimP initialized.[/green]  DB: {DB_PATH}")
    console.print("  Run [bold]TrimP doctor[/bold] to verify installation.")


# ──────────────────────── core analysis commands ─────────────────────────

@app.command(name="token-optimizer")
def token_optimizer_cmd(
    session: str = typer.Option(None, "--session", "-s", help="Session ID (default: current)"),
):
    """[bold cyan]🔍 Full audit with guided fixes.[/bold cyan]"""
    from TrimP.commands import token_optimizer
    token_optimizer.run(session_id=session)


@app.command(name="token-coach")
def token_coach_cmd(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
):
    """[bold cyan]📈 30-day trend analysis with specific fixes.[/bold cyan]"""
    from TrimP.commands import token_coach
    token_coach.run(days=days)


@app.command()
def quick():
    """[bold]⚡ 10-second health check.[/bold]"""
    from TrimP.commands import quick as q
    q.run()


@app.command()
def doctor(
    fix: bool = typer.Option(False, "--fix", help="Auto-repair found issues"),
):
    """[bold]🔧 Installation check (use --fix to auto-repair).[/bold]"""
    from TrimP.commands import doctor as d
    d.run(fix=fix)


@app.command()
def savings(
    all_: bool = typer.Option(False, "--all", help="Show all-time savings across all sessions"),
    session: str = typer.Option(None, "--session", "-s"),
):
    """[bold]💰 Dollar savings report across four pricing tiers.[/bold]"""
    from TrimP.commands import savings as sv
    sv.run(session_id=session, all_sessions=all_)


@app.command()
def report(
    session: str = typer.Option(None, "--session", "-s"),
):
    """[bold]📋 Per-component token breakdown.[/bold]"""
    from TrimP.commands import report_cmd as rc
    rc.run(session_id=session)


@app.command(name="memory-review")
def memory_review_cmd(
    path: str = typer.Option(None, "--path", "-p", help="Path to MEMORY.md"),
):
    """[bold]📝 MEMORY.md structural audit.[/bold]"""
    from TrimP.commands import memory_review as mr
    mr.run(path=path)


@app.command()
def expand(
    key: str = typer.Argument(..., help="Archive key (e.g. arc-a1b2c3d4)"),
):
    """[bold]📂 Retrieve an archived tool result by key.[/bold]"""
    from TrimP.commands import expand as exp
    exp.run(key=key)


@app.command(name="resume-lean")
def resume_lean_cmd(
    session: str = typer.Option(None, "--session", "-s"),
):
    """[bold]🔙 Cold session resume — restore checkpoint context.[/bold]"""
    from TrimP.commands import resume_lean as rl
    rl.run(session_id=session)


# ──────────────────────── dashboard ──────────────────────────────────────

@app.command()
def dashboard(
    mode: str = typer.Option("terminal", "--mode", "-m", help="terminal | web | both"),
    port: int = typer.Option(7432, "--port", "-p"),
    no_browser: bool = typer.Option(False, "--no-browser"),
    build: bool = typer.Option(False, "--build", help="Build React frontend"),
    session: str = typer.Option(None, "--session", "-s"),
):
    """[bold]🌐 Open the full dashboard (terminal TUI or web).[/bold]"""
    if build:
        _build_frontend()
        return

    if mode == "terminal":
        from TrimP.dashboard.terminal import launch
        launch(session_id=session)
    elif mode == "web":
        from TrimP.dashboard.server import launch as web_launch
        web_launch(port=port, open_browser=not no_browser)
    elif mode == "both":
        import threading
        from TrimP.dashboard.server import launch as web_launch
        t = threading.Thread(target=web_launch, kwargs={"port": port, "open_browser": not no_browser}, daemon=True)
        t.start()
        from TrimP.dashboard.terminal import launch
        launch(session_id=session)
    else:
        console.print(f"[red]Unknown mode: {mode}. Use terminal, web, or both.[/red]")
        raise typer.Exit(1)


def _build_frontend() -> None:
    import subprocess
    import sys
    from pathlib import Path

    frontend = Path(__file__).parent / "dashboard" / "frontend"
    if not frontend.exists():
        console.print("[red]Frontend directory not found.[/red]")
        raise typer.Exit(1)

    console.print("[cyan]Installing npm dependencies…[/cyan]")
    subprocess.run(["npm", "install"], cwd=str(frontend), check=True)
    console.print("[cyan]Building React frontend…[/cyan]")
    subprocess.run(["npm", "run", "build"], cwd=str(frontend), check=True)
    console.print("[green]✓ Frontend built. Run `TrimP dashboard --mode web` to launch.[/green]")


# ──────────────────────── session management ─────────────────────────────

@app.command(name="session")
def session_cmd(
    action: str = typer.Argument("show", help="show | new | end | list"),
):
    """Manage sessions (show | new | end | list)."""
    from TrimP.session import get_or_create_session, create_session, end_session, get_recent_sessions
    from TrimP.db import db

    if action == "show":
        sid = get_or_create_session()
        with db() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        if row:
            for k, v in dict(row).items():
                console.print(f"  [cyan]{k}:[/cyan] {v}")
    elif action == "new":
        sid = create_session()
        console.print(f"[green]New session: {sid}[/green]")
    elif action == "end":
        sid = get_or_create_session()
        if sid:
            end_session(sid)
            console.print(f"[yellow]Session ended: {sid}[/yellow]")
    elif action == "list":
        sessions = get_recent_sessions(20)
        for s in sessions:
            console.print(f"  {s['id'][:16]}…  {s['started_at'][:16]}  {s.get('quality_grade','?')}  {s.get('tokens_saved',0):,} saved")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")


# ──────────────────────── checkpoint ─────────────────────────────────────

checkpoint_app = typer.Typer(help="Checkpoint management.")
app.add_typer(checkpoint_app, name="checkpoint")


@checkpoint_app.command("save")
def checkpoint_save(
    title: str = typer.Option("Auto checkpoint", "--title", "-t"),
    overview: str = typer.Option("", "--overview"),
    work_done: str = typer.Option("", "--work-done"),
    technical: str = typer.Option("", "--technical"),
    next_steps: str = typer.Option("", "--next-steps"),
):
    """Save a checkpoint for the current session."""
    from TrimP.compaction import CompactionManager
    from TrimP.session import get_or_create_session
    sid = get_or_create_session()
    mgr = CompactionManager(sid)
    cid = mgr.save_checkpoint(
        title=title, overview=overview, work_done=work_done,
        technical_details=technical, important_files=[], next_steps=next_steps,
    )
    console.print(f"[green]✓ Checkpoint saved (id={cid})[/green]")


@checkpoint_app.command("list")
def checkpoint_list():
    """List checkpoints for the current session."""
    from TrimP.compaction import CompactionManager
    from TrimP.session import get_or_create_session
    sid = get_or_create_session()
    mgr = CompactionManager(sid)
    for cp in mgr.list_checkpoints():
        console.print(f"  #{cp['checkpoint_num']}  {cp.get('title','?')}  {cp['created_at'][:16]}")


# ──────────────────────── config ─────────────────────────────────────────

config_app = typer.Typer(help="Configuration management.")
app.add_typer(config_app, name="config")


@config_app.command("get")
def config_get(key: str):
    """Get a config value."""
    from TrimP.db import get_config
    val = get_config(key)
    console.print(f"{key} = {val or '(not set)'}")


@config_app.command("set")
def config_set(key: str, value: str):
    """Set a config value."""
    from TrimP.db import set_config
    set_config(key, value)
    console.print(f"[green]✓ {key} = {value}[/green]")


@config_app.command("list")
def config_list():
    """List all config values."""
    from TrimP.db import db
    with db() as conn:
        rows = conn.execute("SELECT key, value FROM config ORDER BY key").fetchall()
    for r in rows:
        console.print(f"  {r['key']} = {r['value']}")


# ──────────────────────── compress (standalone) ──────────────────────────

@app.command()
def compress(
    text: str = typer.Argument(None, help="Text to compress (or pipe stdin)"),
    mode: str = typer.Option("bash", "--mode", "-m", help="bash|search|json|skeleton|stopword|prompt|code|conversation|log|image|architecture|semantic|lingua|mcp|universal"),
    show_timing: bool = typer.Option(False, "--timing", "-t", help="Show performance timing"),
):
    """Compress text using a specific compressor (for testing)."""
    import sys
    from TrimP.session import get_or_create_session
    from TrimP.db import db, now_iso
    from TrimP.compression.timer import CompressionTimer
    
    timer = CompressionTimer()
    timer.start()
    
    # Receive input
    with timer.stage('receive'):
        if text is None:
            text = sys.stdin.read()

    # Get or create session for logging
    session_id = get_or_create_session()
    
    # Count tokens (rough estimate: 4 chars per token)
    def estimate_tokens(t: str) -> int:
        return max(1, len(t) // 4)
    
    tokens_before = estimate_tokens(text)
    
    # Compress
    with timer.stage('compress'):
        if mode == "bash":
            from TrimP.compression.bash import BashCompressor
            with timer.stage('algorithm'):
                out, saved = BashCompressor().compress(text)
        elif mode == "search":
            from TrimP.compression.search import SearchCompressor
            with timer.stage('algorithm'):
                out, saved = SearchCompressor().compress(text)
        elif mode == "json":
            from TrimP.compression.json_table import JsonTableCompressor
            with timer.stage('algorithm'):
                out, saved = JsonTableCompressor().compress_json(text)
        elif mode == "skeleton":
            from TrimP.compression.skeleton import SkeletonCompressor
            with timer.stage('algorithm'):
                out, saved = SkeletonCompressor().compress(text)
        elif mode == "stopword":
            from TrimP.compression.stopword_removal import StopWordRemover
            with timer.stage('algorithm'):
                out, saved = StopWordRemover().compress(text)
        elif mode == "prompt":
            from TrimP.compression.prompt_compression import PromptCompressor
            with timer.stage('algorithm'):
                out, saved = PromptCompressor().compress(text)
        elif mode == "code":
            from TrimP.compression.advanced import compress_code_context
            with timer.stage('algorithm'):
                out, metadata = compress_code_context(text, target_ratio=0.4)
                saved = metadata['savings_pct']
        elif mode == "conversation":
            # Conversation needs structured input - for CLI, use universal
            from TrimP.compression.advanced import compress_universal
            with timer.stage('algorithm'):
                out, metadata = compress_universal(text, hint='chat')
                saved = metadata.get('savings_pct', 0)
        elif mode == "log":
            from TrimP.compression.advanced import compress_log
            with timer.stage('algorithm'):
                out, metadata = compress_log(text, target_ratio=0.3)
                saved = metadata['savings_pct']
        elif mode == "image":
            from TrimP.compression.advanced import compress_image_description
            with timer.stage('algorithm'):
                out, metadata = compress_image_description(text, image_type="screenshot")
                saved = metadata['savings_pct']
        elif mode == "architecture":
            from TrimP.compression.advanced import compress_architecture
            with timer.stage('algorithm'):
                out, metadata = compress_architecture(text, interfaces_only=True)
                saved = metadata['savings_pct']
        elif mode == "semantic":
            from TrimP.compression.advanced import compress_semantic
            with timer.stage('algorithm'):
                out, metadata = compress_semantic(text, query="", top_k=10)
                saved = metadata['savings_pct']
        elif mode == "lingua":
            from TrimP.compression.advanced import compress_llm_lingua
            with timer.stage('algorithm'):
                out, metadata = compress_llm_lingua(text, target_ratio=0.5)
                saved = metadata['savings_pct']
        elif mode == "mcp":
            from TrimP.compression.advanced import compress_mcp_tools
            with timer.stage('algorithm'):
                out, metadata = compress_mcp_tools(text, query="", top_k=5)
                saved = metadata['savings_pct']
        elif mode == "universal":
            from TrimP.compression.advanced import compress_universal
            with timer.stage('algorithm'):
                out, metadata = compress_universal(text, hint=None)
                saved = metadata.get('savings_pct', 0)
        else:
            console.print(f"[red]Unknown mode: {mode}[/red]")
            console.print("[yellow]Available modes: bash, search, json, skeleton, stopword, prompt[/yellow]")
            raise typer.Exit(1)

    # Log compression event to database AND update session totals
    tokens_after = estimate_tokens(out)  # Calculate from actual output
    tokens_saved = max(0, tokens_before - tokens_after)
    
    # Detect model (from environment or default)
    model_used = os.environ.get('COPILOT_MODEL', 'Claude Sonnet 4.5')
    
    # Prepare text previews (first 500 chars)
    original_preview = text[:500] if len(text) > 500 else text
    compressed_preview = out[:500] if len(out) > 500 else out
    
    # Get algorithm details from metadata if available
    algorithm_details = None
    if 'metadata' in locals():
        import json
        algorithm_details = json.dumps(metadata)
    
    try:
        with db() as conn:
            # Insert compression event with enhanced metadata
            conn.execute(
                """INSERT INTO compressions 
                   (session_id, compressor, tokens_before, tokens_after, compressed_at,
                    model_used, original_text, compressed_text, compression_method, algorithm_details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, mode, tokens_before, tokens_after, now_iso(),
                 model_used, original_preview, compressed_preview, mode, algorithm_details)
            )
            
            # Update session totals
            conn.execute(
                """UPDATE sessions 
                   SET tokens_saved = tokens_saved + ?,
                       total_tokens_in = total_tokens_in + ?,
                       total_tokens_out = total_tokens_out + ?
                   WHERE id = ?""",
                (tokens_saved, tokens_before, tokens_after, session_id)
            )
    except Exception as e:
        # Don't fail if logging fails
        pass

    # Respond
    with timer.stage('respond'):
        print(out)
    
    timer.stop()
    
    # Show timing if requested
    if show_timing:
        timer.print_report()
    
    # Always show savings
    import sys
    print(f"\nTokens saved: ~{tokens_saved:,}", file=sys.stderr)
    if show_timing:
        print(f"Total time: {timer.get_report()['total_ms']:.2f}ms", file=sys.stderr)


# ──────────────────────── auto (background service) ─────────────────────

auto_app = typer.Typer(help="Auto-running background service.")
app.add_typer(auto_app, name="auto")


@auto_app.command("start")
def auto_start():
    """[bold]🚀 Start auto-runner daemon.[/bold]
    
    Runs compression automatically in the background.
    Dashboard updates in real-time.
    """
    from TrimP.auto_runner import start_auto_runner
    start_auto_runner()


@auto_app.command("stop")
def auto_stop():
    """Stop auto-runner daemon."""
    from TrimP.auto_runner import stop_auto_runner
    stop_auto_runner()


@auto_app.command("status")
def auto_status():
    """Check auto-runner status."""
    from TrimP.auto_runner import status_auto_runner
    status_auto_runner()


# ──────────────────────── monitor (real-time) ───────────────────────────

@app.command("monitor")
def monitor_cmd(
    mode: str = typer.Option("events", help="What to monitor: events, logs")
):
    """[bold]🔍 Real-time monitoring.[/bold]
    
    Watch compression events or auto-runner logs in real-time.
    """
    from TrimP.monitor import monitor_realtime, monitor_logs
    
    if mode == "events":
        monitor_realtime()
    elif mode == "logs":
        monitor_logs()
    else:
        console.print(f"❌ Unknown mode: {mode}")
        console.print("   Use: events or logs")


# ──────────────────────── proxy (integration) ───────────────────────────

proxy_app = typer.Typer(help="Compression proxy integration.")
app.add_typer(proxy_app, name="proxy")


@proxy_app.command("start")
def proxy_start(
    upstream: str = typer.Option("anthropic", "--upstream", "-u", help="anthropic | openai | azure | <custom-url>"),
    port: int = typer.Option(8765, "--port", "-p"),
):
    """[bold]🔌 Start compression proxy server.[/bold]
    
    Intercepts API calls, applies compression, forwards to upstream.
    
    Usage:
        1. TrimP proxy start
        2. export ANTHROPIC_BASE_URL=http://localhost:8765
        3. Use Copilot CLI normally — compression happens automatically
    """
    from TrimP.proxy import start_proxy
    start_proxy(upstream=upstream, port=port)


@proxy_app.command("test")
def proxy_test(
    port: int = typer.Option(8765, "--port", "-p"),
):
    """Test if proxy is running."""
    import requests
    try:
        r = requests.get(f"http://localhost:{port}/TrimP/status", timeout=2)
        if r.status_code == 200:
            data = r.json()
            console.print("[green]✓ Proxy is running[/green]")
            console.print(f"  Session: {data.get('session_id', '?')[:16]}...")
            console.print(f"  Upstream: {data.get('upstream', '?')}")
            console.print(f"  Enabled: {', '.join(data.get('compressions_enabled', []))}")
        else:
            console.print(f"[red]Proxy returned status {r.status_code}[/red]")
    except Exception as e:
        console.print(f"[red]✗ Proxy not running: {e}[/red]")
        console.print("Start with: [bold]TrimP proxy start[/bold]")


# ──────────────────────── copilot hooks ──────────────────────────────────

copilot_app = typer.Typer(help="GitHub Copilot CLI hook integration.")
app.add_typer(copilot_app, name="copilot")


@copilot_app.command("install")
def copilot_install():
    """Install user-level Copilot CLI hooks for bash output reduction."""
    from TrimP.copilot_hooks import install_hooks

    path = install_hooks()
    console.print("[green]✓ Copilot hooks installed[/green]")
    console.print(f"  Hook file: [bold]{path}[/bold]")
    console.print("  Restart Copilot CLI so it reloads hooks.")


@copilot_app.command("uninstall")
def copilot_uninstall():
    """Remove TrimP's user-level Copilot CLI hooks."""
    from TrimP.copilot_hooks import hook_file, uninstall_hooks

    removed = uninstall_hooks()
    if removed:
        console.print(f"[yellow]Removed {hook_file()}[/yellow]")
    else:
        console.print("[dim]No TrimP Copilot hook file was installed.[/dim]")


@copilot_app.command("measure")
def copilot_measure(
    file: str = typer.Option(None, "--file", "-f", help="JSON request body file. Reads stdin when omitted."),
):
    """Dry-run chat request optimization and print before/after tokens."""
    import json
    import sys
    from pathlib import Path

    from TrimP.chat_optimizer import ChatPayloadOptimizer

    raw = Path(file).read_text(encoding="utf-8") if file else sys.stdin.read()
    body = json.loads(raw)
    optimized, stats = ChatPayloadOptimizer().optimize_body(body)
    console.print(f"[bold]Tokens:[/bold] {stats.tokens_before:,} → {stats.tokens_after:,}")
    console.print(f"[bold green]Saved:[/bold green] {stats.tokens_saved:,} ({stats.savings_pct:.2f}%)")
    for change in stats.changes:
        console.print(
            f"  • {change.path}: {change.tokens_before:,} → {change.tokens_after:,} "
            f"via {change.method}"
        )
    print(json.dumps({"TrimP": stats.as_dict(), "optimized": optimized}, indent=2))


# ──────────────────────── intellij (PyCharm/IntelliJ) ──────────────────────

intellij_app = typer.Typer(help="IntelliJ/PyCharm Copilot Chat proxy integration.")
app.add_typer(intellij_app, name="intellij")


@intellij_app.command("proxy")
def intellij_proxy(
    port: int = typer.Option(8765, "--port", "-p", help="Proxy port"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Proxy host"),
    integration_id: str = typer.Option("intellij-chat", "--integration-id", help="Copilot integration ID"),
):
    """[bold]🔌 Start IntelliJ/PyCharm Copilot Chat compression proxy.[/bold]

    1. Run this command
    2. In PyCharm: Settings -> HTTP Proxy -> Manual -> localhost:8765
    3. Restart PyCharm
    4. Use Copilot Chat normally - context is auto-compressed!
    """
    console.print(f"[bold cyan]🔧 TrimP IntelliJ Proxy[/bold cyan]")
    console.print(f"   Listening: [bold]http://{host}:{port}[/bold]")
    console.print(f"   Integration: [bold]{integration_id}[/bold]")
    console.print()
    console.print("[yellow]Configure PyCharm/IntelliJ:[/yellow]")
    console.print("  Settings → Appearance & Behavior → System Settings → HTTP Proxy")
    console.print("  Manual proxy configuration: HTTP, Host: localhost, Port: 8765")
    console.print("  ✅ Use this proxy server for all protocols")
    console.print()
    console.print("[yellow]Or via environment (launch PyCharm from same terminal):[/yellow]")
    console.print(f"  export HTTP_PROXY=http://{host}:{port}")
    console.print(f"  export HTTPS_PROXY=http://{host}:{port}")
    console.print(f"  pycharm")
    console.print()
    console.print("Press Ctrl+C to stop")
    console.print()

    os.environ["COPILOT_INTEGRATION_ID"] = integration_id
    from TrimP.intellij_proxy import main as proxy_main
    proxy_main(host=host, port=port)


@intellij_app.command("config")
def intellij_config():
    """Show PyCharm/IntelliJ proxy configuration instructions."""
    console.print("[bold]📋 IntelliJ/PyCharm Proxy Setup[/bold]")
    console.print()
    console.print("[bold cyan]Method 1: IDE Settings (Recommended)[/bold cyan]")
    console.print("  1. Start proxy: [bold]TrimP intellij proxy[/bold]")
    console.print("  2. Open PyCharm Settings (⌘, / Ctrl+Alt+S)")
    console.print("  3. Go to: Appearance & Behavior → System Settings → HTTP Proxy")
    console.print("  4. Select: Manual proxy configuration")
    console.print("  5. HTTP: Host=localhost, Port=8765")
    console.print("  6. ✅ Check: 'Use this proxy server for all protocols'")
    console.print("  7. Apply → OK → Restart PyCharm")
    console.print()
    console.print("[bold cyan]Method 2: Environment Variables[/bold cyan]")
    console.print("  export HTTP_PROXY=http://localhost:8765")
    console.print("  export HTTPS_PROXY=http://localhost:8765")
    console.print("  pycharm  # Launch from this terminal")
    console.print()
    console.print("[bold cyan]Method 3: Proxy Auto-Config (PAC)[/bold cyan]")
    console.print("  Create proxy.pac:")
    console.print('    function FindProxyForURL(url, host) {')
    console.print('      if (shExpMatch(host, "*githubcopilot.com*")) return "PROXY localhost:8765";')
    console.print('      return "DIRECT";')
    console.print('    }')
    console.print("  In PyCharm: HTTP Proxy → Automatic proxy configuration URL → file:///path/proxy.pac")
    console.print()
    console.print("[bold]Verify:[/bold] curl http://localhost:8765/health")


@intellij_app.command("configure")
def intellij_configure(
    port: int = typer.Option(8767, "--port", "-p"),
    config_path: str = typer.Option("", "--config", help="Specific JetBrains github-copilot.xml path"),
):
    """Configure PyCharm, Rider, or another JetBrains Copilot installation."""
    from TrimP.intellij_proxy import configure_ide
    result = configure_ide(port=port, config_path=config_path or None)
    console.print_json(json.dumps(result))


vscode_app = typer.Typer(help="VS Code Copilot Chat proxy integration.")
app.add_typer(vscode_app, name="vscode")


@vscode_app.command("configure")
def vscode_configure(port: int = typer.Option(8767, "--port", "-p")):
    """Configure VS Code to use the local TrimP HTTPS proxy."""
    from TrimP.intellij_proxy import configure_vscode
    console.print_json(json.dumps(configure_vscode(port=port)))


@vscode_app.command("unconfigure")
def vscode_unconfigure():
    """Restore VS Code settings from the TrimP backup."""
    from TrimP.intellij_proxy import unconfigure_vscode
    console.print_json(json.dumps(unconfigure_vscode()))


@intellij_app.command("test")
def intellij_test(
    port: int = typer.Option(8765, "--port", "-p"),
):
    """Test if IntelliJ proxy is running and compressing."""
    import requests
    try:
        r = requests.get(f"http://localhost:{port}/health", timeout=2)
        if r.status_code == 200:
            data = r.json()
            console.print(f"[green]✓ Proxy running[/green] (session: {data.get('session_id', '?')})")
            console.print(f"  Requests: {data.get('requests_processed', 0)}")
            console.print(f"  Tokens saved: {data.get('total_tokens_saved', 0):,}")
        else:
            console.print(f"[red]Proxy returned {r.status_code}[/red]")
    except Exception as e:
        console.print(f"[red]✗ Proxy not reachable: {e}[/red]")
        console.print("Start with: [bold]TrimP intellij proxy[/bold]")


# ──────────────────────── version ────────────────────────────────────────

@app.command()
def version():
    """Show TrimP version."""
    from TrimP import __version__
    console.print(f"TrimP {__version__}")


if __name__ == "__main__":
    app()
