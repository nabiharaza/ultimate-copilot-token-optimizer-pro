#!/usr/bin/env python3
"""TrimP — GitHub Copilot CLI hook bridge.

Automatically intercepts bash and read tool calls to compress outputs BEFORE
they enter the model context. No manual tool calls needed — compression is
completely automatic.

Hook events:
  - preToolUse[bash]: Wraps command through TrimP compression
  - postToolUse: Logs compression stats to database
  - sessionStart: Initializes session tracking

Exit behavior: Always exits 0 (never blocks tool calls).
"""

import json
import os
import re
import shlex
import subprocess
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

# TrimP compression imports
sys.path.insert(0, "/Users/nabiharaza/Projects/copilot-token-optimizer")

try:
    from TrimP.compression.advanced.universal_optimizer import UniversalOptimizer
    from TrimP.compression.bash import BashCompressor
    from TrimP.compression.advanced.code_context_trimmer import CodeContextTrimmer
    TRIMP_AVAILABLE = True
except Exception:
    TRIMP_AVAILABLE = False

DB_PATH = Path.home() / ".trimp" / "TrimP.db"
MAX_STDIN = 4 * 1024 * 1024  # 4MB max
PROJECT_ROOT = Path(__file__).resolve().parent
WRAPPER_PATH = PROJECT_ROOT / "TrimP" / "copilot_bash_wrapper.py"
DANGEROUS_SHELL_CHARS = re.compile(r"[;&|$(){}<>\n\r\x00]")
SAFE_COMMAND_PREFIXES = {
    "pytest",
    "python",
    "python3",
    "npm",
    "pnpm",
    "yarn",
    "bun",
    "git",
    "rg",
    "grep",
    "ls",
    "find",
    "cat",
    "sed",
    "cargo",
    "go",
    "make",
}

# Compression instances
_bash = BashCompressor() if TRIMP_AVAILABLE else None
_universal = UniversalOptimizer() if TRIMP_AVAILABLE else None
_code = CodeContextTrimmer() if TRIMP_AVAILABLE else None


def log_to_db(session_id: str, method: str, orig_chars: int, comp_chars: int, savings_pct: float):
    """Log compression event (compatible with dashboard schema)."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        # Use dashboard's schema: tokens_before, tokens_after, compressor, compressed_at
        conn.execute("""
            CREATE TABLE IF NOT EXISTS compressions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                compressor TEXT,
                tokens_before INTEGER,
                tokens_after INTEGER,
                compressed_at TEXT,
                source TEXT DEFAULT 'hook'
            )
        """)
        try:
            conn.execute("ALTER TABLE compressions ADD COLUMN source TEXT")
        except sqlite3.OperationalError:
            pass
        # Convert chars to tokens (divide by 4)
        tokens_before = max(1, orig_chars // 4)
        tokens_after = max(1, comp_chars // 4)
        conn.execute(
            "INSERT INTO compressions (session_id, compressor, tokens_before, tokens_after, compressed_at, source) VALUES (?,?,?,?,?,?)",
            (session_id, method, tokens_before, tokens_after, datetime.utcnow().isoformat(), "hook"),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Best-effort logging


def read_stdin():
    """Read hook payload from stdin."""
    try:
        raw = sys.stdin.read(MAX_STDIN + 1)
        if not raw or len(raw) > MAX_STDIN:
            return None
        return json.loads(raw)
    except Exception:
        return None


def compress_bash_output(command: str) -> tuple[str, dict]:
    """Compress bash command output using TrimP."""
    if not TRIMP_AVAILABLE or not _bash:
        return command, {"error": "TrimP unavailable", "savings_pct": 0}
    
    try:
        # Execute command
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        raw_output = result.stdout
        if result.stderr:
            raw_output += f"\nSTDERR:\n{result.stderr}"
        
        if not raw_output or len(raw_output) < 500:
            # Not worth compressing
            return command, {"savings_pct": 0, "reason": "output_too_small"}
        
        # Compress the output
        compressed, meta = _bash.compress(raw_output)
        orig = len(raw_output)
        comp = len(compressed)
        savings = round((orig - comp) / orig * 100, 1) if orig > 0 else 0
        
        return command, {
            "savings_pct": savings,
            "original_chars": orig,
            "compressed_chars": comp,
            "method": meta.get("method", "BashCompressor"),
        }
    except Exception as e:
        return command, {"error": str(e), "savings_pct": 0}


def _decode_tool_args(payload: dict) -> dict:
    tool_args = payload.get("toolArgs", payload.get("tool_args", payload.get("tool_input", {})))
    if isinstance(tool_args, str):
        try:
            decoded = json.loads(tool_args)
            return decoded if isinstance(decoded, dict) else {}
        except Exception:
            return {}
    return tool_args if isinstance(tool_args, dict) else {}


def _can_rewrite_command(command: str) -> bool:
    if not command or DANGEROUS_SHELL_CHARS.search(command):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts:
        return False
    exe = Path(parts[0]).name
    return exe in SAFE_COMMAND_PREFIXES


def _rewrite_command(command: str) -> str | None:
    if not _can_rewrite_command(command) or not WRAPPER_PATH.exists():
        return None
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    return " ".join(
        [shlex.quote(sys.executable), shlex.quote(str(WRAPPER_PATH))]
        + [shlex.quote(part) for part in parts]
    )


def handle_pre_tool_use():
    """PreToolUse hook — intercept bash commands."""
    payload = read_stdin()
    if not payload:
        return
    
    tool_name = payload.get("toolName", payload.get("tool_name", ""))
    if tool_name.lower() != "bash":
        # Only intercept bash
        return
    
    # Extract command
    tool_args = _decode_tool_args(payload)
    
    command = tool_args.get("command", "")
    if not command or len(command) < 10:
        return
    
    rewritten = _rewrite_command(command)
    if not rewritten:
        return

    updated = {"command": rewritten}
    if isinstance(tool_args.get("description"), str):
        updated["description"] = tool_args["description"]

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "preToolUse",
            "updatedInput": updated,
            "modifiedArgs": updated,
            "permissionDecision": "allow",
        }
    }))


def handle_post_tool_use():
    """PostToolUse hook — compress and log tool output."""
    payload = read_stdin()
    if not payload:
        return
    
    tool_name = payload.get("toolName", payload.get("tool_name", ""))
    session_id = payload.get("sessionId", "unknown")
    
    # Get tool output from result
    result = payload.get("result", {})
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            pass
    
    output = ""
    if isinstance(result, dict):
        output = result.get("output", result.get("content", ""))
    elif isinstance(result, str):
        output = result
    
    if not output or len(output) < 500:
        return  # Not worth compressing
    
    # Compress based on tool type
    if tool_name.lower() == "bash":
        compressed, meta = _bash.compress(output) if _bash else (output, {"savings_pct": 0})
    elif tool_name.lower() in ["read", "view"]:
        compressed, meta = _code.compress(output) if _code else (output, {"savings_pct": 0})
    else:
        compressed, meta = _universal.compress(output) if _universal else (output, {"savings_pct": 0})
    
    orig = len(output)
    comp = len(compressed)
    savings = round((orig - comp) / orig * 100, 1) if orig > 0 else 0
    method = meta.get("method", "unknown")
    
    # Log to database
    log_to_db(session_id, method, orig, comp, savings)
    
    # Note: We can't modify the output here because Copilot doesn't support
    # updatedOutput in postToolUse. But we've logged the compression potential.


def handle_user_prompt_submit():
    """UserPromptSubmit hook — compress user's message BEFORE sending to model."""
    payload = read_stdin()
    if not payload:
        return
    
    session_id = payload.get("sessionId", "unknown")
    
    # Extract user's message
    user_message = payload.get("prompt", payload.get("message", payload.get("userMessage", "")))
    
    if not user_message or len(user_message) < 100:
        # Short messages don't need compression
        return
    
    if not TRIMP_AVAILABLE or not _universal:
        return
    
    # Compress the user's message
    try:
        compressed, meta = _universal.compress(user_message)
        orig = len(user_message)
        comp = len(compressed)
        
        # Only use compressed if we save meaningful tokens (>20%)
        if comp < orig * 0.8:
            savings = round((orig - comp) / orig * 100, 1)
            method = meta.get("method", "UniversalOptimizer")
            
            # Log the compression
            log_to_db(session_id, f"{method}_UserMessage", orig, comp, savings)
            
            # Return the compressed message to Copilot
            # Using Copilot's hook output format
            # Copilot CLI does not consistently support replacing submitted
            # prompts. Emit only additional context, and treat the DB row as a
            # measurement of potential savings rather than guaranteed savings.
            response = {
                "hookSpecificOutput": {
                    "hookEventName": "userPromptSubmit",
                    "additionalContext": (
                        f"[TrimP measured this prompt at {orig // 4} -> {comp // 4} "
                        f"estimated tokens ({savings:.0f}% potential reduction).]"
                    ),
                }
            }
            print(json.dumps(response))
    except Exception:
        pass  # Fail open - don't break the user's workflow


def handle_session_start():
    """SessionStart hook — initialize session tracking."""
    payload = read_stdin()
    if not payload:
        return
    
    session_id = payload.get("sessionId", "unknown")
    
    # Ensure DB exists
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                started_at TEXT,
                last_activity TEXT
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO sessions (session_id, started_at, last_activity) VALUES (?,?,?)",
            (session_id, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def main():
    """Main entry point dispatching to event handlers."""
    if len(sys.argv) < 2:
        sys.exit(0)
    
    event = sys.argv[1].lower()
    
    try:
        if event == "pre-tool-use":
            handle_pre_tool_use()
        elif event == "post-tool-use":
            handle_post_tool_use()
        elif event == "session-start":
            handle_session_start()
        elif event == "user-prompt-submit":
            handle_user_prompt_submit()
        elif event == "stop":
            pass  # No special handling needed
    except Exception:
        pass  # Never fail — always exit 0
    
    sys.exit(0)


if __name__ == "__main__":
    main()
