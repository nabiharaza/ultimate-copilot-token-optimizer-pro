"""
/token-optimizer — full audit with guided fixes.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from TrimP.compression.structural import StructuralAuditor
from TrimP.compression.verbosity import VerbosityNudger
from TrimP.db import get_config
from TrimP.quality import score_session, score_to_bar
from TrimP.session import get_or_create_session, get_recent_sessions

console = Console()


def run(session_id: str | None = None) -> None:
    sid = session_id or get_or_create_session()
    console.print(Panel.fit("[bold cyan]🔍 Token Optimizer — Full Audit[/bold cyan]", border_style="cyan"))

    # 1. Quality Score
    _section("📊 Quality Score")
    report = score_session(sid)
    _quality_table(report)

    # 2. Compression summary
    _section("📦 Compression Summary")
    _compression_summary(sid)

    # 3. Structural audit
    _section("🗃️ Structural Context Audit")
    auditor = StructuralAuditor()
    audits = auditor.audit_all()
    if not audits:
        console.print("[dim]No structural context files found.[/dim]")
    else:
        for a in audits:
            icon = "🟢" if a.grade in ("S", "A") else "🟡" if a.grade == "B" else "🔴"
            console.print(f"  {icon} [bold]{a.name}[/bold] [{a.grade}]  ~{a.token_est:,} tokens  {a.path}")
            for issue in a.issues:
                console.print(f"       ⚠ {issue}")

    # 4. Session summary
    _section("🗄️ Session Summary")
    _session_summary(sid)

    # 5. Guided fixes
    _section("🔧 Guided Fixes")
    _guided_fixes(report, audits)


def _section(title: str) -> None:
    console.rule(f"[bold]{title}[/bold]")


def _quality_table(report) -> None:
    t = Table(show_header=True, header_style="bold magenta")
    t.add_column("Signal", style="cyan", width=28)
    t.add_column("Score", width=22)
    t.add_column("Grade", width=6)

    signals = [
        ("Conciseness", report.conciseness),
        ("Compression Effectiveness", report.compression),
        ("Context Utilization", report.context_utilization),
        ("Model Routing Accuracy", report.model_routing),
        ("Loop-free Rate", report.loop_rate),
        ("Cache Hit Rate", report.cache_hit_rate),
    ]
    for name, score in signals:
        bar = score_to_bar(score, 15)
        t.add_row(name, bar, _grade_style(round(score * 100)))
    console.print(t)
    grade_color = {"S": "bright_green", "A": "green", "B": "yellow", "C": "orange3", "D": "red", "F": "bright_red"}
    color = grade_color.get(report.grade, "white")
    console.print(f"\n  Overall: [{color}][bold]{report.grade}[/bold] ({report.overall:.0%})[/{color}]\n")


def _grade_style(pct: int) -> str:
    if pct >= 90:
        return "[bright_green]S[/bright_green]"
    if pct >= 80:
        return "[green]A[/green]"
    if pct >= 65:
        return "[yellow]B[/yellow]"
    if pct >= 50:
        return "[orange3]C[/orange3]"
    if pct >= 35:
        return "[red]D[/red]"
    return "[bright_red]F[/bright_red]"


def _compression_summary(session_id: str) -> None:
    from TrimP.db import db
    with db() as conn:
        rows = conn.execute(
            """SELECT compressor, COUNT(*) as events,
                      SUM(tokens_before) as t_before, SUM(tokens_after) as t_after
               FROM compressions WHERE session_id=?
               GROUP BY compressor ORDER BY (SUM(tokens_before)-SUM(tokens_after)) DESC""",
            (session_id,),
        ).fetchall()

    if not rows:
        console.print("[dim]No compression events recorded yet.[/dim]")
        return

    t = Table(show_header=True, header_style="bold blue")
    t.add_column("Compressor", style="cyan", width=22)
    t.add_column("Events", justify="right", width=8)
    t.add_column("Saved (tokens)", justify="right", width=16)
    t.add_column("Ratio", width=14)

    for row in rows:
        before = row["t_before"] or 1
        after = row["t_after"] or 0
        saved = before - after
        ratio = f"{saved/before:.0%}"
        t.add_row(row["compressor"], str(row["events"]), f"{saved:,}", ratio)
    console.print(t)


def _session_summary(session_id: str) -> None:
    from TrimP.db import db
    with db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        console.print("[dim]Session not found.[/dim]")
        return
    s = dict(row)
    console.print(f"  [bold]ID:[/bold] {s['id'][:24]}...")
    console.print(f"  [bold]Repo:[/bold] {s.get('repository','?')}  [bold]Branch:[/bold] {s.get('branch','?')}")
    console.print(f"  [bold]Tokens in:[/bold] {s.get('total_tokens_in',0):,}  "
                  f"[bold]out:[/bold] {s.get('total_tokens_out',0):,}  "
                  f"[bold]saved:[/bold] [green]{s.get('tokens_saved',0):,}[/green]")


def _guided_fixes(report, audits) -> None:
    fixes: list[str] = []

    if report.compression < 0.2:
        fixes.append("Enable all compression features: `TrimP doctor --fix`")
    if report.conciseness < 0.5:
        fixes.append("High verbosity detected. Verbosity nudges are active but model output is verbose.")
    if report.context_utilization < 0.4:
        fixes.append("Context usage low — compaction may have fired. Run `TrimP resume-lean`.")
    if report.loop_rate < 0.7:
        fixes.append("Loops detected. Check `TrimP report` for loop breakdown.")
    if report.model_routing < 0.6:
        fixes.append("Sub-optimal model routing. Use Haiku for exploration, Sonnet for implementation.")
    if report.cache_hit_rate < 0.5:
        fixes.append("Low cache hit rate — files re-read without delta compression.")

    for a in audits:
        if a.grade in ("D", "F"):
            fixes.append(f"Fix {a.name} [{a.grade}]: {a.issues[0] if a.issues else 'large file'}")

    if not fixes:
        console.print("  [bright_green]✓ No critical issues found.[/bright_green]")
    else:
        for i, fix in enumerate(fixes, 1):
            console.print(f"  [bold yellow]{i}.[/bold yellow] {fix}")
