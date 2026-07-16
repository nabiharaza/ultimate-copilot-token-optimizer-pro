#!/usr/local/bin/python3
"""
TrimP MCP Server — Token Optimizer for GitHub Copilot Enterprise

Exposes TrimP compression as MCP tools so Copilot uses compressed
outputs, reducing tokens sent to the model by 50-65%.

No API keys needed. Works with GitHub Copilot Enterprise OAuth.

Usage:
  Add to ~/.copilot/mcp-config.json:
  {
    "servers": {
      "TrimP": {
        "command": "python3",
        "args": ["/path/to/copilot-token-optimizer/TrimP_mcp_server.py"]
      }
    }
  }
"""

import sys
import os
import subprocess
import sqlite3
import time
import json
import logging
from datetime import datetime
from pathlib import Path

# Silence all logging for MCP stdio protocol
logging.basicConfig(level=logging.CRITICAL)
os.environ["LOGURU_LEVEL"] = "CRITICAL"

# Add TrimP to path (derived from this file's location, not hardcoded, so
# the MCP server works from any checkout on any machine)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastmcp import FastMCP

# Load TrimP compressors
try:
    from TrimP.compression.advanced.universal_optimizer import UniversalOptimizer
    from TrimP.compression.advanced.code_context_trimmer import CodeContextTrimmer
    from TrimP.compression.advanced.conversation_compressor import ConversationCompressor
    from TrimP.compression.advanced.log_extractor import LogExtractor
    from TrimP.compression.advanced.json_minimizer import JSONMinimizer
    from TrimP.compression.bash import BashCompressor
    from TrimP.compression.search import SearchCompressor
    _universal = UniversalOptimizer()
    _code = CodeContextTrimmer()
    _convo = ConversationCompressor()
    _log = LogExtractor()
    _json_min = JSONMinimizer()
    _bash = BashCompressor()
    _search = SearchCompressor()
    TRIMP_AVAILABLE = True
except Exception as e:
    TRIMP_AVAILABLE = False
    _err = str(e)

DB_PATH = Path.home() / ".trimp" / "TrimP.db"


def _secure_db_permissions() -> None:
    """Best-effort: keep ~/.trimp and TrimP.db user-only (0700/0600).

    The MCP server can be the first process to create the DB on a fresh
    machine, so it can't assume the CLI/dashboard already locked it down.
    POSIX-only, silently a no-op elsewhere.
    """
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        DB_PATH.parent.chmod(0o700)
        if DB_PATH.exists():
            DB_PATH.chmod(0o600)
    except OSError:
        pass

mcp = FastMCP(
    name="TrimP-token-optimizer",
    instructions=(
        "Use these tools to compress large outputs before processing. "
        "When you read files, run commands, or get large text, compress it first "
        "to save tokens. Always prefer TrimP_bash over bash for long outputs, "
        "and TrimP_read_file for large files."
    ),
)


def _log_to_db(method: str, original_chars: int, compressed_chars: int, savings_pct: float):
    """Log compression event to TrimP SQLite database."""
    try:
        _secure_db_permissions()
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS compressions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                method TEXT,
                original_chars INTEGER,
                compressed_chars INTEGER,
                savings_pct REAL,
                source TEXT
            )
        """)
        conn.execute(
            "INSERT INTO compressions (timestamp, method, original_chars, compressed_chars, savings_pct, source) VALUES (?,?,?,?,?,?)",
            (datetime.utcnow().isoformat(), method, original_chars, compressed_chars, savings_pct, "mcp-server"),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # DB logging is best-effort


def _compress(text: str, mode: str = "universal") -> tuple[str, dict]:
    """Run compression and return (compressed_text, metadata)."""
    if not TRIMP_AVAILABLE:
        return text, {"error": "TrimP not available", "savings_pct": 0}

    try:
        if mode == "code":
            result, meta = _code.compress(text)
        elif mode == "conversation":
            result, meta = _convo.compress(text)
        elif mode == "log":
            result, meta = _log.compress(text)
        elif mode == "json":
            result, meta = _json_min.compress(text)
        elif mode == "bash":
            # BashCompressor.compress() returns (text, tokens_saved_estimate:
            # int), not (text, metadata dict) like the other compressors —
            # normalize it so the shared savings/logging code below works.
            result, tokens_saved_est = _bash.compress(text)
            meta = {"method": "BashCompressor", "tokens_saved_est": tokens_saved_est}
        elif mode == "search":
            # Same int-vs-dict mismatch as BashCompressor above.
            result, tokens_saved_est = _search.compress(text)
            meta = {"method": "SearchCompressor", "tokens_saved_est": tokens_saved_est}
        else:
            result, meta = _universal.compress(text)

        orig = len(text)
        comp = len(result)
        savings = round((orig - comp) / orig * 100, 1) if orig > 0 else 0
        meta["savings_pct"] = savings
        _log_to_db(meta.get("method", mode), orig, comp, savings)
        return result, meta
    except Exception as e:
        return text, {"error": str(e), "savings_pct": 0}


@mcp.tool()
def TrimP_compress(text: str, mode: str = "universal") -> str:
    """
    Compress any text to reduce token usage.

    Args:
        text: Text to compress (file contents, command output, logs, etc.)
        mode: Compression mode — one of:
              universal (default), code, conversation, log, json, bash, search

    Returns:
        Compressed text with a savings summary appended.
    """
    if not text or len(text) < 200:
        return text  # Not worth compressing tiny inputs

    compressed, meta = _compress(text, mode)
    savings = meta.get("savings_pct", 0)
    method = meta.get("method", mode)
    return f"{compressed}\n\n[TrimP: {savings:.1f}% saved via {method}]"


@mcp.tool()
def TrimP_bash(command: str, working_dir: str = "") -> str:
    """
    Run a bash command and return compressed output.
    Use this instead of plain bash when output could be large
    (test runs, builds, grep results, logs, etc.)

    Args:
        command: Shell command to run
        working_dir: Optional working directory

    Returns:
        Compressed command output.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=working_dir if working_dir else None,
        )
        raw = result.stdout
        if result.stderr:
            raw += "\nSTDERR:\n" + result.stderr
        exit_info = f"\n[exit code: {result.returncode}]"
    except subprocess.TimeoutExpired:
        return "Command timed out after 120 seconds."
    except Exception as e:
        return f"Error running command: {e}"

    if not raw.strip():
        return f"(no output){exit_info}"

    # Auto-detect mode from command
    mode = "bash"
    cmd_lower = command.lower()
    if any(k in cmd_lower for k in ["grep", "rg", "find", "ag"]):
        mode = "search"
    elif any(k in cmd_lower for k in ["cat ", "less ", "head ", "tail "]):
        mode = "universal"
    elif "log" in cmd_lower or "journal" in cmd_lower:
        mode = "log"

    if len(raw) < 500:
        return raw + exit_info

    compressed, meta = _compress(raw, mode)
    savings = meta.get("savings_pct", 0)
    return f"{compressed}{exit_info}\n[TrimP: {savings:.1f}% saved]"


@mcp.tool()
def TrimP_read_file(path: str) -> str:
    """
    Read a file and return compressed content to save tokens.
    Use for large source files, logs, configs, or data files.

    Args:
        path: Absolute or relative path to file

    Returns:
        Compressed file content.
    """
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"File not found: {path}"
        if not p.is_file():
            return f"Not a file: {path}"

        size = p.stat().st_size
        if size > 5_000_000:
            return f"File too large ({size // 1024}KB). Use TrimP_bash with 'head -500 {path}' instead."

        content = p.read_text(errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"

    if len(content) < 500:
        return content

    # Detect mode from extension
    ext = p.suffix.lower()
    if ext in {".py", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".c", ".h"}:
        mode = "code"
    elif ext in {".json", ".jsonl"}:
        mode = "json"
    elif ext in {".log", ".out"}:
        mode = "log"
    else:
        mode = "universal"

    compressed, meta = _compress(content, mode)
    savings = meta.get("savings_pct", 0)
    return f"{compressed}\n\n[TrimP: {savings:.1f}% saved from {p.name} ({len(content)} chars → {len(compressed)} chars)]"


@mcp.tool()
def TrimP_stats() -> str:
    """
    Show compression statistics: total savings, sessions, token reduction.
    Use to check how many tokens TrimP has saved in this session.

    Returns:
        JSON-formatted stats summary.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("""
            SELECT
                COUNT(*) as total_compressions,
                SUM(original_chars) as total_original,
                SUM(compressed_chars) as total_compressed,
                AVG(savings_pct) as avg_savings,
                MAX(timestamp) as last_compression
            FROM compressions
            WHERE source = 'mcp-server'
        """).fetchone()
        conn.close()

        if rows and rows[0]:
            orig_tokens = (rows[1] or 0) // 4
            saved_tokens = ((rows[1] or 0) - (rows[2] or 0)) // 4
            return json.dumps({
                "mcp_compressions": rows[0],
                "tokens_processed": f"{orig_tokens:,}",
                "tokens_saved": f"{saved_tokens:,}",
                "avg_savings_pct": f"{rows[3]:.1f}%",
                "last_compression": rows[4],
                "dashboard": "http://localhost:7432",
                "status": "✅ TrimP MCP server active",
            }, indent=2)
        else:
            return json.dumps({
                "mcp_compressions": 0,
                "status": "✅ TrimP MCP server active — no compressions yet this session",
                "dashboard": "http://localhost:7432",
            }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "status": "TrimP DB not accessible"})


@mcp.tool()
def TrimP_grep(pattern: str, path: str = ".", file_glob: str = "") -> str:
    """
    Run a search (grep/ripgrep) and return compressed results.
    Use for searching codebases — compresses duplicate/noisy matches.

    Args:
        pattern: Regex or literal pattern to search for
        path: Directory or file to search in
        file_glob: Optional glob to filter files (e.g. "*.py")

    Returns:
        Compressed search results.
    """
    # Built as argument lists (no shell=True) so pattern/path/file_glob can
    # never break out into shell metacharacters/command substitution. The
    # previous version interpolated repr(pattern) into a shell string, which
    # is NOT shell-escaping and allowed injection via inputs containing a
    # single quote (Python's repr() then switches to double quotes, which
    # the shell happily expands $(...) and `...` inside).
    rg_cmd = ["rg", "--no-heading", "-n", pattern, path]
    if file_glob:
        rg_cmd += ["-g", file_glob]
    grep_cmd = ["grep", "-rn", pattern, path]

    try:
        result = subprocess.run(rg_cmd, capture_output=True, text=True, timeout=30)
        raw = result.stdout
        if result.returncode != 0 and not raw:
            result = subprocess.run(grep_cmd, capture_output=True, text=True, timeout=30)
            raw = result.stdout
        raw = raw or "(no matches)"
    except FileNotFoundError:
        try:
            result = subprocess.run(grep_cmd, capture_output=True, text=True, timeout=30)
            raw = result.stdout or "(no matches)"
        except Exception as e:
            return f"Search error: {e}"
    except Exception as e:
        return f"Search error: {e}"

    if len(raw) < 300:
        return raw

    compressed, meta = _compress(raw, "search")
    savings = meta.get("savings_pct", 0)
    return f"{compressed}\n[TrimP: {savings:.1f}% saved]"


if __name__ == "__main__":
    if not TRIMP_AVAILABLE:
        print(f"WARNING: TrimP compression unavailable: {_err}", file=sys.stderr)

    mcp.run(transport="stdio", show_banner=False)
