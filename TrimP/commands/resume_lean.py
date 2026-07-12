"""resume-lean — guided cold session resume."""
from __future__ import annotations
from rich.console import Console
from rich.panel import Panel
from TrimP.compaction import CompactionManager
from TrimP.session import get_or_create_session

console = Console()

def run(session_id: str | None = None) -> None:
    console.print("[bold]🔙 Resume-Lean — Cold Session Restore[/bold]\n")
    sid = session_id or get_or_create_session()
    mgr = CompactionManager(sid)

    checkpoints = mgr.list_checkpoints()
    if not checkpoints:
        console.print("[dim]No checkpoints found for this session.[/dim]")
        console.print("Tip: Save checkpoints with `TrimP checkpoint save`")
        return

    latest = checkpoints[0]
    console.print(f"  Found [bold]{len(checkpoints)}[/bold] checkpoint(s). Latest:")
    console.print(f"  #{latest['checkpoint_num']}: [bold]{latest.get('title','(untitled)')}[/bold]")
    console.print(f"  Quality: {latest.get('quality_score', 0):.0%}  Saved: {latest['created_at'][:19]}\n")

    digest = mgr.restore_checkpoint()
    console.print(Panel(digest, title="[bold cyan]Context Intel Digest[/bold cyan]", border_style="cyan"))
    console.print("\n[green]✓ Context restored. Paste the digest above into your session to resume.[/green]")
