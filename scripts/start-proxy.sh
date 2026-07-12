#!/bin/bash
# Start TrimP proxy and configure shell to use it

PORT=${1:-8765}
UPSTREAM=${2:-anthropic}

echo "🔧 Starting TrimP compression proxy on port $PORT..."
echo "   Upstream: $UPSTREAM"
echo ""

# Start proxy in background
TrimP proxy start --port "$PORT" --upstream "$UPSTREAM" &
PROXY_PID=$!

# Wait for proxy to start
sleep 2

# Check if running
if TrimP proxy test --port "$PORT" 2>/dev/null; then
    echo ""
    echo "✅ Proxy is running (PID: $PROXY_PID)"
    echo ""
    echo "Add to your shell profile (~/.zshrc or ~/.bashrc):"
    echo ""
    if [ "$UPSTREAM" = "anthropic" ]; then
        echo "  export ANTHROPIC_BASE_URL=http://localhost:$PORT"
    elif [ "$UPSTREAM" = "openai" ]; then
        echo "  export OPENAI_BASE_URL=http://localhost:$PORT"
    fi
    echo ""
    echo "Or run now:"
    if [ "$UPSTREAM" = "anthropic" ]; then
        echo "  export ANTHROPIC_BASE_URL=http://localhost:$PORT"
    elif [ "$UPSTREAM" = "openai" ]; then
        echo "  export OPENAI_BASE_URL=http://localhost:$PORT"
    fi
    echo ""
    echo "Then use GitHub Copilot CLI as normal."
    echo "All requests will be compressed automatically."
    echo ""
    echo "View metrics: TrimP quick | TrimP token-optimizer | TrimP dashboard"
    echo "Stop proxy: kill $PROXY_PID"
else
    echo "❌ Failed to start proxy"
    kill "$PROXY_PID" 2>/dev/null
    exit 1
fi
