#!/usr/bin/env python3
"""Execute a simple command and print compressed output for Copilot CLI hooks."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
sys.path = [p for p in sys.path if p not in {"", _SCRIPT_DIR}]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from TrimP.compression.bash import BashCompressor


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return 0

    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_safe_env(),
        check=False,
    )
    output = proc.stdout
    if proc.stderr:
        output += ("\nSTDERR:\n" if output else "STDERR:\n") + proc.stderr

    if output:
        compressed, saved = BashCompressor().compress(output, use_algo=False)
        before = max(1, len(output) // 4)
        after = max(1, len(compressed) // 4)
        if saved > 0 and after < before:
            print(
                f"[TrimP compressed command output: ~{before} -> ~{after} tokens, saved ~{before - after}]"
            )
            print(compressed)
        else:
            print(output, end="" if output.endswith("\n") else "\n")

    return proc.returncode


def _safe_env() -> dict[str, str]:
    allowed = {
        "HOME",
        "PATH",
        "LANG",
        "LC_ALL",
        "TERM",
        "USER",
        "SHELL",
        "TMPDIR",
        "VIRTUAL_ENV",
        "PYTHONPATH",
        "NODE_ENV",
    }
    return {k: v for k, v in os.environ.items() if k in allowed}


if __name__ == "__main__":
    raise SystemExit(main())
