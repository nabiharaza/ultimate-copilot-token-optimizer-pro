"""
SQLite database layer — 15-table audit trail.
DB stored at ~/.trimp/TrimP.db  (unified path used by all tools and scripts)
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

# Unified DB path — ~/.trimp/TrimP.db  (consistent across all tools, proxy, dashboard)
DB_DIR  = Path.home() / ".trimp"
DB_PATH = DB_DIR / "TrimP.db"

_local = threading.local()

SCHEMA = """
-- 1. sessions
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    cwd         TEXT,
    repository  TEXT,
    branch      TEXT,
    total_tokens_in  INTEGER DEFAULT 0,
    total_tokens_out INTEGER DEFAULT 0,
    tokens_saved     INTEGER DEFAULT 0,
    quality_grade    TEXT DEFAULT 'F',
    model            TEXT,
    status      TEXT DEFAULT 'active'  -- active | compacted | resumed
);

-- 2. turns
CREATE TABLE IF NOT EXISTS turns (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    turn_index   INTEGER NOT NULL,
    user_message TEXT,
    assistant_response TEXT,
    tokens_in    INTEGER DEFAULT 0,
    tokens_out   INTEGER DEFAULT 0,
    tokens_saved INTEGER DEFAULT 0,
    model        TEXT,
    timestamp    TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 3. checkpoints
CREATE TABLE IF NOT EXISTS checkpoints (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    checkpoint_num  INTEGER NOT NULL,
    title           TEXT,
    overview        TEXT,
    work_done       TEXT,
    technical_details TEXT,
    important_files TEXT,   -- JSON array
    next_steps      TEXT,
    token_count     INTEGER DEFAULT 0,
    quality_score   REAL DEFAULT 0.0,
    created_at      TEXT NOT NULL,
    restored_at     TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 4. compressions  (includes full text + model for live monitor)
CREATE TABLE IF NOT EXISTS compressions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id         TEXT NOT NULL,
    turn_id            INTEGER,
    compressor         TEXT NOT NULL,
    tokens_before      INTEGER NOT NULL,
    tokens_after       INTEGER NOT NULL,
    pattern_matched    TEXT,
    compressed_at      TEXT NOT NULL,
    model_used         TEXT,
    original_text      TEXT,
    compressed_text    TEXT,
    compression_method TEXT,
    chat_window        TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 5. quality_scores
CREATE TABLE IF NOT EXISTS quality_scores (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id           TEXT NOT NULL,
    turn_id              INTEGER,
    conciseness_ratio    REAL DEFAULT 0.0,
    compression_effectiveness REAL DEFAULT 0.0,
    context_utilization  REAL DEFAULT 0.0,
    model_routing_accuracy REAL DEFAULT 0.0,
    loop_detection_rate  REAL DEFAULT 0.0,
    cache_hit_rate       REAL DEFAULT 0.0,
    overall_score        REAL DEFAULT 0.0,
    grade                TEXT DEFAULT 'F',
    scored_at            TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 6. archives
CREATE TABLE IF NOT EXISTS archives (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    archive_key  TEXT UNIQUE NOT NULL,
    content      TEXT NOT NULL,
    summary      TEXT,
    char_count   INTEGER NOT NULL,
    tool_name    TEXT,
    archived_at  TEXT NOT NULL,
    expanded_at  TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 7. session_files
CREATE TABLE IF NOT EXISTS session_files (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    file_path    TEXT NOT NULL,
    tool_name    TEXT,
    turn_index   INTEGER,
    last_hash    TEXT,
    last_seen_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 8. model_routing
CREATE TABLE IF NOT EXISTS model_routing (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    turn_id      INTEGER,
    task_type    TEXT,   -- exploration|implementation|debug|review|test
    model_used   TEXT,
    model_recommended TEXT,
    was_optimal  INTEGER DEFAULT 1,  -- boolean
    nudge_sent   INTEGER DEFAULT 0,
    routed_at    TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 9. token_budgets
CREATE TABLE IF NOT EXISTS token_budgets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    context_window  INTEGER DEFAULT 200000,
    tokens_used     INTEGER DEFAULT 0,
    tokens_saved    INTEGER DEFAULT 0,
    snapshot_at     TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 10. compression_patterns
CREATE TABLE IF NOT EXISTS compression_patterns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    compressor  TEXT NOT NULL,
    pattern     TEXT NOT NULL,
    hit_count   INTEGER DEFAULT 0,
    tokens_saved_total INTEGER DEFAULT 0,
    last_seen   TEXT,
    UNIQUE(compressor, pattern)
);

-- 11. savings
CREATE TABLE IF NOT EXISTS savings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    tokens_saved    INTEGER NOT NULL,
    -- pricing tiers (per 1M tokens, blended in/out)
    cost_saved_haiku   REAL,   -- $0.80/1M
    cost_saved_sonnet  REAL,   -- $3.00/1M
    cost_saved_opus    REAL,   -- $15.00/1M
    cost_saved_gpt4    REAL,   -- $10.00/1M
    period_start    TEXT NOT NULL,
    period_end      TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 12. memory_audits
CREATE TABLE IF NOT EXISTS memory_audits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    char_count  INTEGER,
    token_est   INTEGER,
    issues      TEXT,   -- JSON array
    score       REAL DEFAULT 0.0,
    grade       TEXT,
    audited_at  TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 13. config
CREATE TABLE IF NOT EXISTS config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- 14. loop_detections
CREATE TABLE IF NOT EXISTS loop_detections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    turn_id     INTEGER,
    loop_type   TEXT,  -- tool_repeat|content_repeat|pattern_repeat
    pattern     TEXT,
    repeat_count INTEGER DEFAULT 2,
    detected_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 15. activity_modes
CREATE TABLE IF NOT EXISTS activity_modes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    turn_id     INTEGER,
    mode        TEXT NOT NULL,  -- exploration|implementation|debug|review|test|planning
    confidence  REAL DEFAULT 0.0,
    decisions   TEXT,           -- JSON array of key decisions extracted
    switched_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 16. copilot_agent_usage
-- Exact usage snapshots imported from local GitHub Copilot agent logs.
CREATE TABLE IF NOT EXISTS copilot_agent_usage (
    source_path TEXT PRIMARY KEY,
    source_hash TEXT NOT NULL,
    source_session_id TEXT NOT NULL,
    event_start TEXT,
    event_end TEXT,
    cwd TEXT,
    repository TEXT,
    model TEXT,
    copilot_version TEXT,
    requests INTEGER DEFAULT 0,
    user_messages INTEGER DEFAULT 0,
    model_turns INTEGER DEFAULT 0,
    tool_calls INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    compactions INTEGER DEFAULT 0,
    compaction_tokens INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cached_input_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    reasoning_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    system_tokens INTEGER DEFAULT 0,
    conversation_tokens INTEGER DEFAULT 0,
    tool_definitions_tokens INTEGER DEFAULT 0,
    total_nano_aiu INTEGER DEFAULT 0,
    model_usage TEXT,
    is_complete INTEGER DEFAULT 0,
    imported_at TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_turns_session        ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_compressions_session ON compressions(session_id);
CREATE INDEX IF NOT EXISTS idx_compressions_time    ON compressions(compressed_at);
CREATE INDEX IF NOT EXISTS idx_quality_session      ON quality_scores(session_id);
CREATE INDEX IF NOT EXISTS idx_archives_key         ON archives(archive_key);
CREATE INDEX IF NOT EXISTS idx_savings_session      ON savings(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started     ON sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_compressions_compressor ON compressions(compressor);
CREATE INDEX IF NOT EXISTS idx_agent_usage_end ON copilot_agent_usage(event_end);
CREATE INDEX IF NOT EXISTS idx_agent_usage_session ON copilot_agent_usage(source_session_id);
"""

# Safely add new columns to existing DBs without destroying data
_MIGRATIONS = [
    "ALTER TABLE compressions ADD COLUMN model_used TEXT",
    "ALTER TABLE compressions ADD COLUMN original_text TEXT",
    "ALTER TABLE compressions ADD COLUMN compressed_text TEXT",
    "ALTER TABLE compressions ADD COLUMN compression_method TEXT",
    "ALTER TABLE compressions ADD COLUMN chat_window TEXT",
    "ALTER TABLE compressions ADD COLUMN source TEXT",
    "ALTER TABLE compressions ADD COLUMN algorithm_details TEXT",
    "ALTER TABLE sessions ADD COLUMN label TEXT",
    "ALTER TABLE compressions ADD COLUMN request_body TEXT",
    "ALTER TABLE compressions ADD COLUMN optimized_body TEXT",
    "ALTER TABLE compressions ADD COLUMN response_body TEXT",
    "ALTER TABLE compressions ADD COLUMN request_source TEXT",
    "ALTER TABLE compressions ADD COLUMN debug_log_excerpt TEXT",
    "ALTER TABLE compressions ADD COLUMN actual_usage TEXT",
    "ALTER TABLE compressions ADD COLUMN compression_score REAL",
    "ALTER TABLE compressions ADD COLUMN compression_grade TEXT",
    "ALTER TABLE compressions ADD COLUMN recommendations TEXT",
]


def _ensure_db_dir() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Add new columns to existing tables — ignores 'duplicate column' errors safely."""
    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists


def get_connection() -> sqlite3.Connection:
    """Return a thread-local sqlite3 connection, creating DB if needed."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _ensure_db_dir()
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn = conn
        _apply_schema(conn)
    return _local.conn


def _apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    _run_migrations(conn)


@contextmanager
def db():
    """Context manager yielding a connection. Commits on success, rolls back on error."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_config_defaults() -> None:
    defaults = {
        "compression.enabled": "true",
        "compression.bash.enabled": "true",
        "compression.search.enabled": "true",
        "compression.json.enabled": "true",
        "compression.delta.enabled": "true",
        "compression.skeleton.enabled": "true",
        "compression.archive.enabled": "true",
        "compression.verbosity.enabled": "true",
        "compression.structural.enabled": "true",
        "compression.loop_detect.enabled": "true",
        "compression.activity.enabled": "true",
        "archive.threshold_chars": "4096",
        "quality.min_grade": "B",
        "pricing.haiku_per_1m": "0.80",
        "pricing.sonnet_per_1m": "3.00",
        "pricing.opus_per_1m": "15.00",
        "pricing.gpt4_per_1m": "10.00",
        "dashboard.web.port": "7432",
        "dashboard.web.auto_open": "true",
        "proxy.port": "8765",
        "proxy.upstream": "anthropic",
        "proxy.azure_endpoint": "https://api.openai.azure.com",
        "session.copilot_db_path": str(Path.home() / ".config/github-copilot/sessions.db"),
    }
    with db() as conn:
        for key, val in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO config(key, value, updated_at) VALUES (?,?,?)",
                (key, val, now_iso()),
            )


def get_config(key: str, default: str = "") -> str:
    with db() as conn:
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_config(key: str, value: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO config(key, value, updated_at) VALUES (?,?,?)",
            (key, value, now_iso()),
        )
