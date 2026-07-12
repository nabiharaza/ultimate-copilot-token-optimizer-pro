#!/bin/bash
# Wrapper to suppress stderr noise from fastmcp for clean MCP protocol
exec python3 /Users/nabiharaza/Projects/copilot-token-optimizer/TrimP_mcp_server.py 2>/dev/null
