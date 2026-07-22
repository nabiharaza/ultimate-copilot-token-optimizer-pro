#!/bin/bash
# Wrapper that launches TrimP_mcp_server.py as a clean MCP stdio server.
# Resolves its own directory so this works from any checkout, not just the
# machine it was originally written on.
#
# Two responsibilities beyond just running the script:
#   1. Pick a Python that actually has `fastmcp` installed (it's an optional
#      dependency — `pip install -e ".[mcp]"` — so a bare `python3` on a
#      machine that never installed the mcp extra will fail with a silent
#      ModuleNotFoundError if stderr is discarded).
#   2. Send stderr to a log file instead of swallowing it. MCP stdio needs
#      stdout to carry ONLY JSON-RPC, but discarding stderr entirely made
#      every startup failure invisible — the server would just look "dead"
#      to Claude Code with no clue why. Logging it instead makes failures
#      diagnosable without polluting the protocol channel.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${TRIMP_MCP_LOG:-$HOME/.trimp/mcp_server.log}"
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null

# Prefer a project-local virtualenv if one exists and actually has fastmcp;
# otherwise fall back to whatever `python3` resolves to on PATH.
PYTHON_BIN=""
for candidate in "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/venv/bin/python3"; do
  if [ -x "$candidate" ] && "$candidate" -c "import fastmcp" >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1 && python3 -c "import fastmcp" >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  fi
fi

if [ -z "$PYTHON_BIN" ]; then
  {
    echo "[TrimP MCP] fastmcp is not installed for any available Python interpreter."
    echo "[TrimP MCP] Run: pip install -e \"$SCRIPT_DIR\"[mcp]  (or pip install fastmcp>=0.2)"
    echo "[TrimP MCP] Checked: .venv, venv, and \$(command -v python3)."
  } >>"$LOG_FILE" 2>&1
  echo "TrimP MCP server: fastmcp not installed. See $LOG_FILE for setup instructions." >&2
  exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/TrimP_mcp_server.py" 2>>"$LOG_FILE"
