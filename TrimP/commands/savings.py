"""savings — dollar savings report across four pricing tiers."""
from __future__ import annotations
from rich.console import Console
from rich.table import Table
from TrimP.db import db, get_config
from TrimP.session import get_or_create_session

console = Console()

PRICING = {
    "Claude Haiku": ("pricing.haiku_per_1m", 0.80),
    "Claude Sonnet": ("pricing.sonnet_per_1m", 3.00),
    "Claude Opus": ("pricing.opus_per_1m", 15.00),
    "GPT-4": ("pricing.gpt4_per_1m", 10.00),
}

def run(session_id: str | None = None, all_sessions: bool = False) -> None:
    console.print("[bold]💰 Token Savings Report[/bold]\n")

    if all_sessions:
        _global_savings()
    else:
        sid = session_id or get_or_create_session()
        _session_savings(sid)


def _session_savings(session_id: str) -> None:
    with db() as conn:
        sess = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not sess:
        console.print("[dim]No session data.[/dim]")
        return

    saved = sess["tokens_saved"] or 0
    console.print(f"  Session: [bold]{session_id[:24]}...[/bold]")
    console.print(f"  Tokens saved: [bold green]{saved:,}[/bold green]\n")
    _savings_table(saved)


def _global_savings() -> None:
    with db() as conn:
        row = conn.execute("SELECT SUM(tokens_saved) as total FROM sessions").fetchone()
    saved = row["total"] or 0
    console.print(f"  [bold]All-time tokens saved: [green]{saved:,}[/green][/bold]\n")
    _savings_table(saved)


def _savings_table(tokens_saved: int) -> None:
    t = Table(show_header=True, header_style="bold green")
    t.add_column("Model Tier", style="cyan", width=18)
    t.add_column("$/1M tokens", justify="right", width=12)
    t.add_column("$ Saved", justify="right", width=12)
    t.add_column("Annualized*", justify="right", width=14)

    for model, (config_key, default_rate) in PRICING.items():
        rate = float(get_config(config_key, str(default_rate)))
        saved_dollars = (tokens_saved / 1_000_000) * rate
        annual = saved_dollars * 52  # approximate 52 sessions/year
        t.add_row(model, f"${rate:.2f}", f"${saved_dollars:.4f}", f"~${annual:.2f}")

    console.print(t)
    console.print("[dim]* Annualized = 52 sessions/year estimate[/dim]")
