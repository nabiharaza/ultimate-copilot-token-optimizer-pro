#!/bin/bash
# Start the auto-importer daemon

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_FILE="$HOME/.trimp/auto-import.pid"
LOG_FILE="$HOME/.trimp/auto-import.log"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✓ Auto-importer already running (PID: $PID)"
        exit 0
    fi
fi

# Start daemon
echo "Starting auto-importer daemon..."
cd "$PROJECT_ROOT"
nohup python3 auto_import_daemon.py > "$LOG_FILE" 2>&1 &
PID=$!

echo "$PID" > "$PID_FILE"
sleep 2

if ps -p "$PID" > /dev/null 2>&1; then
    echo "✅ Auto-importer started (PID: $PID)"
    echo "   Log: $LOG_FILE"
else
    echo "❌ Failed to start auto-importer"
    exit 1
fi
