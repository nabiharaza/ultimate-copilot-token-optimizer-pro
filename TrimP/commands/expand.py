"""expand — retrieve an archived tool result."""
from __future__ import annotations
from rich.console import Console
from TrimP.compression.archive import ArchiveManager
from TrimP.session import get_or_create_session

console = Console()

def run(key: str) -> None:
    sid = get_or_create_session()
    mgr = ArchiveManager(sid)
    content = mgr.expand(key)
    if content is None:
        console.print(f"[red]Archive key not found: {key}[/red]")
        console.print("Use `TrimP report` to list available archive keys.")
        return
    console.print(f"[bold]📂 Expanded: {key}[/bold]\n")
    console.print(content)
