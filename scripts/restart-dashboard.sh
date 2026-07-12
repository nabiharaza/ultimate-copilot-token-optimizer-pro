#!/bin/bash
# Dashboard restart script (works around kill restrictions)

echo "🔄 Restarting TrimP dashboard..."
echo ""

# Find dashboard process
echo "Finding dashboard process..."
PID=$(ps aux | grep "TrimP dashboard" | grep -v grep | awk '{print $2}' | head -1)

if [ -n "$PID" ]; then
    echo "Found dashboard at PID: $PID"
    echo "To stop it, run: kill $PID"
    echo ""
    echo "⚠️  Please run this command manually:"
    echo "   kill $PID"
    echo ""
    echo "Then run this script again to start fresh dashboard."
    exit 1
else
    echo "✓ No existing dashboard found"
    echo ""
    
    # Start fresh dashboard
    echo "Starting new dashboard..."
    cd /Users/nabiharaza/Projects/copilot-token-optimizer
    nohup TrimP dashboard --mode web --no-browser --port 7432 > ~/.trimp/dashboard.log 2>&1 &
    NEW_PID=$!
    
    sleep 3
    
    # Verify it started
    if ps -p $NEW_PID > /dev/null 2>&1; then
        echo "✅ Dashboard started successfully (PID: $NEW_PID)"
        echo ""
        echo "📊 Open: http://localhost:7432"
        echo "📝 Logs: tail -f ~/.trimp/dashboard.log"
    else
        echo "❌ Failed to start dashboard"
        echo "Check logs: cat ~/.trimp/dashboard.log"
        exit 1
    fi
fi
