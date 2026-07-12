#!/bin/bash
# Start TrimP BYOK real-time compression

PROJECT_DIR="/Users/nabiharaza/Projects/copilot-token-optimizer"
cd "$PROJECT_DIR"

echo "🚀 Starting TrimP BYOK proxy..."
echo ""

# Check if BYOK proxy is running
if curl -s http://localhost:8766/v1/health >/dev/null 2>&1; then
    echo "✅ BYOK proxy already running on port 8766"
else
    echo "Starting BYOK proxy..."
    python3 byok_server.py --port 8766 > /tmp/byok_server.log 2>&1 &
    sleep 3
    
    if curl -s http://localhost:8766/v1/health >/dev/null 2>&1; then
        echo "✅ BYOK proxy started on port 8766"
    else
        echo "❌ Failed to start. Check /tmp/byok_server.log"
        exit 1
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ TrimP BYOK proxy is running!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Configure your terminal:"
echo "  export COPILOT_PROVIDER_URL=http://localhost:8766/v1"
echo ""
echo "Then use Copilot:"
echo "  copilot --provider openai --model gpt-5.4 -p \"Your prompt\""
echo ""
