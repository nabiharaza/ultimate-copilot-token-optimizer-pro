#!/bin/bash
# Auto-import GitHub Copilot sessions into TrimP
# Run this in the background to continuously import sessions

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
IMPORT_SCRIPT="$SCRIPT_DIR/import_copilot_session.py"

echo "🔄 Auto-importing GitHub Copilot sessions..."

# If COPILOT_AGENT_SESSION_ID is set, import that specific session
if [ -n "$COPILOT_AGENT_SESSION_ID" ]; then
    echo "   Current session: $COPILOT_AGENT_SESSION_ID"
    python3 "$IMPORT_SCRIPT" "$COPILOT_AGENT_SESSION_ID" 2>&1 | grep -E "✅|❌|Importing"
fi

# Import all recent sessions (last 5)
echo "   Checking for recent sessions..."
SESSION_STATE_DIR="$HOME/.copilot/session-state"

if [ -d "$SESSION_STATE_DIR" ]; then
    # Get 5 most recently modified sessions
    find "$SESSION_STATE_DIR" -maxdepth 1 -type d -mtime -7 | tail -5 | while read session_dir; do
        session_id=$(basename "$session_dir")
        if [ "$session_id" != "session-state" ]; then
            python3 "$IMPORT_SCRIPT" "$session_id" 2>&1 | grep -E "✅|❌|Session already"
        fi
    done
fi

echo "✅ Import complete!"
