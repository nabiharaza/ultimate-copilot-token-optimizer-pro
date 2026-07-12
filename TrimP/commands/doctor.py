"""doctor — installation check."""
from __future__ import annotations
import importlib
import sys
from pathlib import Path
from rich.console import Console
from TrimP.db import DB_PATH, get_config

console = Console()

REQUIRED_PACKAGES = [
    "typer", "rich", "textual", "fastapi", "uvicorn",
    "aiosqlite", "pydantic", "httpx", "psutil",
]

def run(fix: bool = False) -> None:
    console.print("[bold]🔧 TrimP Doctor — Installation Check[/bold]\n")
    all_ok = True

    # Python version
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 10
    _check(f"Python {v.major}.{v.minor}.{v.micro}", ok, "Python 3.10+ required")
    all_ok = all_ok and ok

    # Packages
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
            _check(f"Package: {pkg}", True)
        except ImportError:
            _check(f"Package: {pkg}", False, f"pip install {pkg}")
            all_ok = False
            if fix:
                import subprocess
                subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=False)

    # DB directory
    db_ok = DB_PATH.parent.exists()
    _check(f"Data dir: {DB_PATH.parent}", db_ok, "Run TrimP init")
    if not db_ok and fix:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _check(f"Created: {DB_PATH.parent}", True)

    # DB file
    _check(f"Database: {DB_PATH}", DB_PATH.exists(), "Run TrimP init")

    # Compression features
    console.print("\n[bold]Compression Features[/bold]")
    features = [
        "compression.bash.enabled", "compression.search.enabled",
        "compression.json.enabled", "compression.delta.enabled",
        "compression.skeleton.enabled", "compression.archive.enabled",
        "compression.verbosity.enabled", "compression.structural.enabled",
        "compression.loop_detect.enabled",
    ]
    for f in features:
        val = get_config(f, "true")
        enabled = val.lower() == "true"
        name = f.split(".")[1]
        _check(f"  {name}", enabled, f"TrimP config set {f} true")

    console.print()
    if all_ok:
        console.print("[bright_green]✓ All checks passed![/bright_green]")
    else:
        console.print("[yellow]⚠ Some issues found. Run `TrimP doctor --fix` to auto-repair.[/yellow]")


def _check(label: str, ok: bool, fix_hint: str = "") -> None:
    icon = "[bright_green]✓[/bright_green]" if ok else "[red]✗[/red]"
    msg = f"  {icon} {label}"
    if not ok and fix_hint:
        msg += f"  [dim]→ {fix_hint}[/dim]"
    console.print(msg)
