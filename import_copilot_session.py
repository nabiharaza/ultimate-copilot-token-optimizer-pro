#!/usr/bin/env python3
"""
Import GitHub Copilot CLI sessions into TrimP database.
Reads from ~/.copilot/session-state/ and imports into ~/.trimp/TrimP.db
"""

import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime

def import_session(session_id: str):
    """Import a GitHub Copilot session into TrimP database."""
    
    # Paths
    session_dir = Path.home() / ".copilot" / "session-state" / session_id
    events_file = session_dir / "events.jsonl"
    workspace_file = session_dir / "workspace.yaml"
    # Use project database (not legacy ~/.trimp/)
    TrimP_db = Path.home() / "Projects/copilot-token-optimizer/data/TrimP.db"
    
    if not events_file.exists():
        print(f"❌ Session not found: {session_id}")
        return
    
    print(f"📂 Importing session: {session_id}")
    print(f"   Events: {events_file}")
    
    # Read workspace info
    cwd = ""
    repo = ""
    branch = ""
    if workspace_file.exists():
        import yaml
        try:
            with open(workspace_file) as f:
                ws = yaml.safe_load(f)
                cwd = ws.get("cwd", "")
                repo = Path(cwd).name if cwd else "unknown"
        except:
            pass
    
    # Parse events
    events = []
    with open(events_file) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    
    print(f"   Found {len(events)} events")
    
    # Extract session info
    session_start = None
    model = "claude-sonnet-4.5"
    user_messages = []
    assistant_messages = []
    tool_calls = 0
    
    for event in events:
        event_type = event.get("type")
        timestamp = event.get("timestamp")
        
        if event_type == "session.start":
            session_start = timestamp
            model = event.get("data", {}).get("selectedModel", model)
            cwd = event.get("data", {}).get("context", {}).get("cwd", cwd)
            repo = Path(cwd).name if cwd else repo
        elif event_type == "user.message":
            user_messages.append({
                "content": event.get("data", {}).get("content", ""),
                "timestamp": timestamp
            })
        elif event_type == "assistant.message":
            assistant_messages.append({
                "content": event.get("data", {}).get("content", ""),
                "timestamp": timestamp
            })
        elif event_type == "tool.execution_complete":
            tool_calls += 1
    
    print(f"   User messages: {len(user_messages)}")
    print(f"   Assistant messages: {len(assistant_messages)}")
    print(f"   Tool calls: {tool_calls}")
    
    # Connect to TrimP database
    conn = sqlite3.connect(str(TrimP_db))
    conn.row_factory = sqlite3.Row
    
    # Check if session already exists
    existing = conn.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone()
    if existing:
        print(f"   ⚠️  Session already in database")
        
        # Update it instead
        conn.execute("""
            UPDATE sessions 
            SET repository=?, branch=?, model=?, cwd=?
            WHERE id=?
        """, (repo, branch, model, cwd, session_id))
    else:
        # Insert new session
        conn.execute("""
            INSERT INTO sessions (id, started_at, cwd, repository, branch, model, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
        """, (session_id, session_start or datetime.now().isoformat(), cwd, repo, branch, model))
    
    # Insert turns (match user/assistant messages)
    for idx, (user_msg, asst_msg) in enumerate(zip(user_messages, assistant_messages)):
        user_content = user_msg["content"]
        asst_content = asst_msg["content"]
        timestamp = user_msg["timestamp"]
        
        # Estimate tokens (rough: 4 chars = 1 token)
        tokens_in = len(user_content) // 4
        tokens_out = len(asst_content) // 4
        
        # Check if turn already exists
        existing_turn = conn.execute(
            "SELECT id FROM turns WHERE session_id=? AND turn_index=?",
            (session_id, idx)
        ).fetchone()
        
        if not existing_turn:
            conn.execute("""
                INSERT INTO turns (session_id, turn_index, user_message, assistant_response, 
                                   tokens_in, tokens_out, timestamp, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, idx, user_content, asst_content, tokens_in, tokens_out, timestamp, model))
            
            # Update session totals
            conn.execute("""
                UPDATE sessions
                SET total_tokens_in = total_tokens_in + ?,
                    total_tokens_out = total_tokens_out + ?
                WHERE id=?
            """, (tokens_in, tokens_out, session_id))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Session imported successfully!")
    print(f"   View in dashboard: http://localhost:7432")

def list_sessions():
    """List all GitHub Copilot sessions."""
    session_state_dir = Path.home() / ".copilot" / "session-state"
    
    if not session_state_dir.exists():
        print("❌ No GitHub Copilot sessions found")
        return []
    
    sessions = []
    for session_dir in session_state_dir.iterdir():
        if session_dir.is_dir():
            workspace_file = session_dir / "workspace.yaml"
            events_file = session_dir / "events.jsonl"
            
            if events_file.exists():
                # Get session info
                session_info = {
                    "id": session_dir.name,
                    "path": str(session_dir),
                    "events_count": sum(1 for _ in open(events_file))
                }
                
                if workspace_file.exists():
                    try:
                        import yaml
                        with open(workspace_file) as f:
                            ws = yaml.safe_load(f)
                            session_info["name"] = ws.get("name", "")
                            session_info["cwd"] = ws.get("cwd", "")
                            session_info["created_at"] = ws.get("created_at", "")
                    except:
                        pass
                
                sessions.append(session_info)
    
    return sorted(sessions, key=lambda x: x.get("created_at", ""), reverse=True)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        session_id = sys.argv[1]
        import_session(session_id)
    else:
        # List available sessions
        print("📊 GitHub Copilot Sessions Available:\n")
        sessions = list_sessions()
        
        for idx, session in enumerate(sessions[:10], 1):
            print(f"{idx}. {session['id'][:20]}...")
            print(f"   Name: {session.get('name', 'N/A')}")
            print(f"   Events: {session.get('events_count', 0)}")
            print(f"   Path: {session.get('cwd', 'N/A')}")
            print()
        
        print(f"\nTotal sessions: {len(sessions)}")
        print("\nTo import a session:")
        print(f"  python3 import_copilot_session.py <session_id>")
        print("\nTo import current session:")
        current = os.environ.get("COPILOT_AGENT_SESSION_ID")
        if current:
            print(f"  python3 import_copilot_session.py {current}")
        else:
            print("  (no active session detected)")
