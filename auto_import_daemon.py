#!/usr/bin/env python3
"""
Auto-importer for GitHub Copilot sessions.
Watches the active session and imports new turns automatically every second.
"""

import json
import os
import sqlite3
import time
from pathlib import Path
from datetime import datetime

# Configuration
PROJECT_ROOT = Path.home() / "Projects/copilot-token-optimizer"
TRIMP_DB = PROJECT_ROOT / "data/TrimP.db"
CHECK_INTERVAL = 1  # seconds
LOG_FILE = Path.home() / ".trimp" / "auto-import.log"

# Track last imported state
last_turn_count = {}
last_event_count = {}

def log(msg):
    """Log message to file and stdout."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = f"[{timestamp}] {msg}"
    print(message)
    
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(message + "\n")

def get_active_session():
    """Get the current GitHub Copilot session ID from environment."""
    return os.environ.get("COPILOT_AGENT_SESSION_ID")

def get_session_events_file(session_id):
    """Get path to session events file."""
    return Path.home() / ".copilot" / "session-state" / session_id / "events.jsonl"

def count_events(events_file):
    """Count total events in file."""
    if not events_file.exists():
        return 0
    try:
        with open(events_file) as f:
            return sum(1 for _ in f)
    except:
        return 0

def parse_session_events(session_id, events_file):
    """Parse events and extract conversation turns."""
    if not events_file.exists():
        return None
    
    try:
        events = []
        with open(events_file) as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        
        # Extract session info
        session_start = None
        model = "claude-sonnet-4.5"
        cwd = ""
        repo = ""
        branch = ""
        user_messages = []
        assistant_messages = []
        
        for event in events:
            event_type = event.get("type")
            timestamp = event.get("timestamp")
            
            if event_type == "session.start":
                session_start = timestamp
                model = event.get("data", {}).get("selectedModel", model)
                cwd = event.get("data", {}).get("context", {}).get("cwd", cwd)
                repo = Path(cwd).name if cwd else "unknown"
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
        
        return {
            "session_id": session_id,
            "started_at": session_start or datetime.now().isoformat(),
            "cwd": cwd,
            "repository": repo,
            "branch": branch,
            "model": model,
            "user_messages": user_messages,
            "assistant_messages": assistant_messages
        }
    except Exception as e:
        log(f"Error parsing events: {e}")
        return None

def import_session_to_db(session_data):
    """Import session data to database."""
    if not session_data:
        return False
    
    try:
        conn = sqlite3.connect(str(TRIMP_DB))
        conn.row_factory = sqlite3.Row
        
        session_id = session_data["session_id"]
        
        # Check if session exists
        existing = conn.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone()
        
        if existing:
            # Update existing session
            conn.execute("""
                UPDATE sessions 
                SET repository=?, branch=?, model=?, cwd=?
                WHERE id=?
            """, (
                session_data["repository"],
                session_data["branch"],
                session_data["model"],
                session_data["cwd"],
                session_id
            ))
        else:
            # Insert new session
            conn.execute("""
                INSERT INTO sessions (id, started_at, cwd, repository, branch, model, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
            """, (
                session_id,
                session_data["started_at"],
                session_data["cwd"],
                session_data["repository"],
                session_data["branch"],
                session_data["model"]
            ))
        
        # Insert turns
        new_turns = 0
        for idx, (user_msg, asst_msg) in enumerate(zip(
            session_data["user_messages"],
            session_data["assistant_messages"]
        )):
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
                """, (session_id, idx, user_content, asst_content, tokens_in, tokens_out, timestamp, session_data["model"]))
                
                # Update session totals
                conn.execute("""
                    UPDATE sessions
                    SET total_tokens_in = total_tokens_in + ?,
                        total_tokens_out = total_tokens_out + ?
                    WHERE id=?
                """, (tokens_in, tokens_out, session_id))
                
                new_turns += 1
        
        conn.commit()
        conn.close()
        
        if new_turns > 0:
            log(f"✅ Imported {new_turns} new turns for session {session_id[:20]}...")
        
        return True
        
    except Exception as e:
        log(f"❌ Error importing to database: {e}")
        return False

def watch_and_import():
    """Main loop: watch active session and import changes."""
    log("🚀 Starting auto-importer for GitHub Copilot sessions")
    log(f"   Database: {TRIMP_DB}")
    log(f"   Check interval: {CHECK_INTERVAL}s")
    log("")
    
    while True:
        try:
            session_id = get_active_session()
            
            if not session_id:
                # No active session
                time.sleep(CHECK_INTERVAL)
                continue
            
            # Initialize tracking for new session
            if session_id not in last_event_count:
                last_event_count[session_id] = 0
                last_turn_count[session_id] = 0
                log(f"📂 Detected new session: {session_id[:20]}...")
            
            events_file = get_session_events_file(session_id)
            
            if not events_file.exists():
                time.sleep(CHECK_INTERVAL)
                continue
            
            # Check if events file has changed
            current_event_count = count_events(events_file)
            
            if current_event_count > last_event_count[session_id]:
                # New events detected - parse and import
                session_data = parse_session_events(session_id, events_file)
                
                if session_data:
                    current_turn_count = min(
                        len(session_data["user_messages"]),
                        len(session_data["assistant_messages"])
                    )
                    
                    if current_turn_count > last_turn_count[session_id]:
                        import_session_to_db(session_data)
                        last_turn_count[session_id] = current_turn_count
                
                last_event_count[session_id] = current_event_count
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            log("\n⏹️  Auto-importer stopped by user")
            break
        except Exception as e:
            log(f"❌ Error in watch loop: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    watch_and_import()
