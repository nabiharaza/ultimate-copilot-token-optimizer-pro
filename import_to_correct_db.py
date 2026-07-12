"""Import session to the correct TrimP database (data/TrimP.db)"""
import sqlite3
import json
from pathlib import Path

# Source and destination databases
source_db = Path.home() / ".trimp" / "TrimP.db"
dest_db = Path.home() / "Projects/copilot-token-optimizer/data/TrimP.db"
session_id = "a5bdce91-7c0e-4b97-b4cf-ae67da453557"

print(f"Copying session {session_id}")
print(f"From: {source_db}")
print(f"To: {dest_db}")

# Connect to both databases
src_conn = sqlite3.connect(str(source_db))
src_conn.row_factory = sqlite3.Row
dst_conn = sqlite3.connect(str(dest_db))
dst_conn.row_factory = sqlite3.Row

# Get session from source
session = src_conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
if not session:
    print("❌ Session not found in source database")
    exit(1)

print(f"Found session: {dict(session)['repository']}")

# Copy session
dst_conn.execute("""
    INSERT OR REPLACE INTO sessions 
    (id, started_at, ended_at, cwd, repository, branch, total_tokens_in, total_tokens_out, 
     tokens_saved, quality_grade, model, status)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
""", (
    session['id'], session['started_at'], session['ended_at'], session['cwd'],
    session['repository'], session['branch'], session['total_tokens_in'], 
    session['total_tokens_out'], session['tokens_saved'], session['quality_grade'],
    session['model'], session['status']
))

# Get and copy turns
turns = src_conn.execute("SELECT * FROM turns WHERE session_id=?", (session_id,)).fetchall()
print(f"Copying {len(turns)} turns...")

for turn in turns:
    dst_conn.execute("""
        INSERT OR REPLACE INTO turns
        (session_id, turn_index, user_message, assistant_response, tokens_in, tokens_out, 
         tokens_saved, model, timestamp)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        turn['session_id'], turn['turn_index'], turn['user_message'], turn['assistant_response'],
        turn['tokens_in'], turn['tokens_out'], turn['tokens_saved'], turn['model'], turn['timestamp']
    ))

dst_conn.commit()
src_conn.close()
dst_conn.close()

print("✅ Session copied successfully!")
