#!/bin/bash
# Wrapper to suppress stderr noise from fastmcp for clean MCP protocol
# Resolves its own directory so this works from any checkout, not just the
# machine it was originally written on.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/TrimP_mcp_server.py" 2>/dev/null
