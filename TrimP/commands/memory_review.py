"""memory-review — MEMORY.md structural audit."""
from __future__ import annotations
from pathlib import Path
from rich.console import Console
from TrimP.compression.structural import StructuralAuditor
from TrimP.db import db, now_iso
from TrimP.session import get_or_create_session

console = Console()

def run(path: str | None = None) -> None:
    console.print("[bold]📝 MEMORY.md Structural Audit[/bold]\n")
    auditor = StructuralAuditor()
    audits = auditor.audit_all()

    memory_audits = [a for a in audits if "MEMORY" in a.name.upper() or "memory" in a.path.lower()]

    if path:
        p = Path(path)
        if p.exists():
            content = p.read_text(encoding="utf-8", errors="replace")
            audit = auditor._audit_memory(content, str(p))
            memory_audits = [audit]

    if not memory_audits:
        console.print("[dim]No MEMORY.md found. Create one at ~/.copilot/MEMORY.md or ./MEMORY.md[/dim]")
        return

    for a in memory_audits:
        grade_colors = {"S": "bright_green","A":"green","B":"yellow","C":"orange3","D":"red","F":"bright_red"}
        c = grade_colors.get(a.grade, "white")
        console.print(f"  File: [bold]{a.path}[/bold]")
        console.print(f"  Size: {a.char_count:,} chars  (~{a.token_est:,} tokens)")
        console.print(f"  Grade: [{c}][bold]{a.grade}[/bold][/{c}]  Score: {a.score:.0%}\n")

        if a.issues:
            console.print("  [bold yellow]Issues:[/bold yellow]")
            for issue in a.issues:
                console.print(f"    ⚠ {issue}")
        else:
            console.print("  [green]✓ No issues found[/green]")

        console.print()
        _recommendations(a)

        # Persist audit
        sid = get_or_create_session()
        with db() as conn:
            conn.execute(
                """INSERT INTO memory_audits
                   (session_id, file_path, char_count, token_est, issues, score, grade, audited_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (sid, a.path, a.char_count, a.token_est,
                 str(a.issues), a.score, a.grade, now_iso()),
            )


def _recommendations(a) -> None:
    console.print("  [bold]Recommendations:[/bold]")
    if a.token_est > 2000:
        console.print(f"    → Prune to under 2,000 tokens (currently ~{a.token_est:,})")
        console.print("      Remove resolved items, stale context, repeated facts")
    if a.score >= 0.8:
        console.print("    → MEMORY.md looks healthy")
    console.print()
