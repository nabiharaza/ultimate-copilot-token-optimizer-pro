"""Install user-level GitHub Copilot CLI hooks for TrimP."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path


def copilot_home() -> Path:
    return Path.home() / ".copilot"


def hook_file() -> Path:
    return copilot_home() / "hooks" / "TrimP.json"


def legacy_hook_file() -> Path:
    return copilot_home() / "hooks" / "ctopt.json"


def build_hook_config(bridge_path: Path | None = None) -> dict:
    bridge = bridge_path or Path(__file__).resolve().parents[1] / "TrimP_hook_bridge.py"
    py = shlex.quote(sys.executable or "python3")
    bridge_q = shlex.quote(str(bridge))

    def cmd(event: str) -> dict:
        return {
            "type": "command",
            "bash": f"{py} {bridge_q} {event}",
            "timeoutSec": 10,
        }

    pre = cmd("pre-tool-use")
    pre["matcher"] = {"toolName": "bash"}

    return {
        "version": 1,
        "hooks": {
            "sessionStart": [cmd("session-start")],
            "preToolUse": [pre],
            "postToolUse": [cmd("post-tool-use")],
            "stop": [cmd("stop")],
        },
    }


def install_hooks() -> Path:
    target = hook_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_hook_config(), indent=2) + "\n", encoding="utf-8")
    # Prevent the retired ctopt hook from running alongside the TrimP hook.
    legacy_hook_file().unlink(missing_ok=True)
    return target


def uninstall_hooks() -> bool:
    target = hook_file()
    if not target.exists():
        return False
    target.unlink()
    return True
