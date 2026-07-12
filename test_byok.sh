#!/bin/bash
# Quick test of TrimP BYOK compression

echo "🧪 Testing TrimP BYOK compression..."
echo ""

# Check if proxy is running
if ! curl -s http://localhost:8766/v1/health >/dev/null 2>&1; then
    echo "❌ BYOK proxy not running. Starting it..."
    cd /Users/nabiharaza/Projects/copilot-token-optimizer
    python3 byok_server.py --port 8766 > /tmp/byok_server.log 2>&1 &
    sleep 3
fi

# Set the environment variable
export COPILOT_PROVIDER_URL=http://localhost:8766/v1

echo "✅ Proxy is running"
echo "✅ COPILOT_PROVIDER_URL=$COPILOT_PROVIDER_URL"
echo ""
echo "Now running a test Copilot command with compression..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run a simple copilot command
copilot --provider openai --model gpt-5.4 -p "Say 'Hello from TrimP compression!'"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Check the proxy logs to see compression stats:"
echo "  tail -f /tmp/byok_server.log"
echo ""
