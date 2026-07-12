# TrimP Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION                             │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  │
        ┌─────────────────────────┴────────────────────────┐
        │                                                   │
        ▼                                                   ▼
┌───────────────┐                                  ┌──────────────────┐
│  GitHub       │                                  │   TrimP CLI      │
│  Copilot CLI  │                                  │   (10 commands)  │
└───────────────┘                                  └──────────────────┘
        │                                                   │
        │                                                   │
        │                    ┌──────────────────────────────┤
        │                    │                              │
        │                    ▼                              ▼
        │            ┌──────────────┐             ┌─────────────────┐
        │            │  Auto-Runner │             │  Manual Cmds    │
        │            │  (Daemon)    │             │  (One-off)      │
        │            └──────────────┘             └─────────────────┘
        │                    │                              │
        │                    │                              │
        └────────────────────┴──────────────────────────────┘
                             │
                             │
                             ▼
                  ┌──────────────────────────┐
                  │  COMPRESSION ENGINES (9) │
                  └──────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Bash (60+)   │   │ Search       │   │ JSON/Table   │
│ patterns     │   │ compression  │   │ columnar     │
└──────────────┘   └──────────────┘   └──────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Delta diffs  │   │ Code         │   │ Archive      │
│ for re-reads │   │ skeletons    │   │ (>4KB)       │
└──────────────┘   └──────────────┘   └──────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Verbosity    │   │ Structural   │   │ Loop         │
│ nudges       │   │ audit        │   │ detection    │
└──────────────┘   └──────────────┘   └──────────────┘
                             │
                             │
                             ▼
                  ┌──────────────────────────┐
                  │  SQLITE DATABASE (15)    │
                  │  ~/.trimp/TrimP.db       │
                  └──────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ sessions     │   │ file_reads   │   │ tool_outputs │
└──────────────┘   └──────────────┘   └──────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ compression_ │   │ savings_     │   │ quality_     │
│ events       │   │ events       │   │ scores       │
└──────────────┘   └──────────────┘   └──────────────┘
        │                    │                    │
        └────────────────────┴────────────────────┘
                             │
                             │
                             ▼
                  ┌──────────────────────────┐
                  │      DASHBOARDS          │
                  └──────────────────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        │                                         │
        ▼                                         ▼
┌──────────────────┐                    ┌──────────────────┐
│  Terminal TUI    │                    │  Web Dashboard   │
│  (Textual)       │                    │  (React+FastAPI) │
└──────────────────┘                    └──────────────────┘
        │                                         │
        │                                         │
        ▼                                         ▼
┌──────────────────┐                    ┌──────────────────┐
│ • Quick stats    │                    │ • Savings cards  │
│ • Quality score  │                    │ • History charts │
│ • Compression    │                    │ • Quality radar  │
│ • Recent events  │                    │ • Session list   │
└──────────────────┘                    │ • Feature toggle │
                                        └──────────────────┘
```

## Component Details

### 1. CLI Layer (`TrimP/cli.py`)
- **Entry point**: Main Typer app with 10 commands
- **Commands**: quick, token-optimizer, token-coach, savings, report, memory-review, expand, resume-lean, compress, dashboard
- **Sub-apps**: auto (start/stop/status), proxy (start/test)

### 2. Auto-Runner (`TrimP/auto_runner.py`)
- **Daemon process**: Monitors GitHub Copilot sessions
- **Session detection**: Via `COPILOT_AGENT_SESSION_ID` env var
- **Interval**: Checks every 30 seconds
- **Logs**: `~/.trimp/auto-runner.log`
- **PID file**: `~/.trimp/auto-runner.pid`

### 3. Compression Engines (`TrimP/compression/`)
Each engine is a Python module with `compress()` function:

| Engine | File | Purpose |
|--------|------|---------|
| **Bash** | `bash.py` | 60+ patterns for CLI output |
| **Search** | `search.py` | Grep/search result compression |
| **JSON/Table** | `json_table.py` | Columnar compression |
| **Delta** | `delta.py` | File re-read diffs |
| **Skeleton** | `skeleton.py` | Code structure extraction |
| **Archive** | `archive.py` | Large output storage (>4KB) |
| **Verbosity** | `verbosity.py` | Model output analysis |
| **Structural** | `structural.py` | Config/MEMORY audit |
| **Loop** | `loop_detect.py` | Retry loop detection |

### 4. Database Layer (`TrimP/db.py`)
**15 tables** in SQLite at `~/.trimp/TrimP.db`:

#### Core Tables
- `sessions` — Session metadata (id, start_time, end_time, branch)
- `file_reads` — Every file read with compression deltas
- `tool_outputs` — Every tool call with before/after tokens
- `command_outputs` — Every bash command execution

#### Event Tables
- `compression_events` — Before/after tokens per compression
- `savings_events` — Dollar savings per event
- `quality_scores` — Real-time quality metrics per session

#### Analysis Tables
- `session_history` — Daily aggregates for trend analysis
- `skill_usage` — Per-skill usage tracking
- `model_usage` — Per-model routing stats
- `subagent_usage` — Subagent cost breakdown

#### Supporting Tables
- `cached_content` — Prompt cache tracking
- `context_intel` — Post-compaction hints
- `activity_log` — Session activity mode
- `config` — Key-value config storage

### 5. Quality Scoring (`TrimP/quality/`)
**7 signals** combined into S-F letter grade:

1. **Conciseness**: Output verbosity ratio
2. **Compression**: Effectiveness of compression engines
3. **Context Utilization**: Token usage efficiency
4. **Model Routing**: Right model for task
5. **Loop-Free**: No retry loops detected
6. **Cache Hit Rate**: Prompt caching effectiveness
7. **Overall**: Composite score (weighted average)

**Grades**:
- S: 90-100 (Exceptional)
- A: 80-89 (Excellent)
- B: 70-79 (Good)
- C: 60-69 (Fair)
- D: 50-59 (Poor)
- F: 0-49 (Failing)

### 6. Dashboard Server (`TrimP/dashboard/server.py`)
**FastAPI backend** on port 7432:

#### Endpoints
- `GET /` — Serve React frontend
- `GET /api/stats` — Current session stats
- `GET /api/sessions` — Session history (paginated)
- `GET /api/compression` — Per-engine breakdown
- `GET /api/savings` — Dollar savings by tier
- `GET /api/quality` — Quality signals
- `GET /api/config` — Current config
- `POST /api/config` — Update config
- `GET /ws` — WebSocket for real-time updates

### 7. Dashboard Frontend (`TrimP/dashboard/frontend/`)
**React + Vite** application:

#### Pages
- `HomeNew.jsx` — Savings cards + history (Headroom-style)
- `Compression.jsx` — Per-engine breakdown with charts
- `Quality.jsx` — Quality radar + signal details
- `Savings.jsx` — Dollar savings by pricing tier
- `Sessions.jsx` — Session history table
- `Config.jsx` — Feature toggles + settings

#### Components
- `Sidebar.jsx` — Icon navigation (Headroom-style)
- `Charts.jsx` — Reusable Recharts components

#### Styling
- `index.css` — Light theme, sidebar, cards, charts

### 8. Proxy Server (`TrimP/proxy.py`)
**Optional HTTP proxy** for API interception:

- **Port**: 8765
- **Upstreams**: Anthropic, GitHub Copilot, GitHub Enterprise
- **Compression**: Real-time on request/response
- **Logging**: All events to database

**Note**: GitHub Copilot doesn't expose proxy hooks by default.

## Data Flow

### Normal Operation (Auto-Runner)
```
1. User starts: bash scripts/start-all.sh
2. Auto-runner detects: COPILOT_AGENT_SESSION_ID
3. Compression engines monitor: Tool calls, file reads, commands
4. Database logs: All events with before/after tokens
5. Quality scorer calculates: Real-time S-F grade
6. Dashboard updates: Via FastAPI polling or WebSocket
7. User views: http://localhost:7432
```

### Manual Compression
```
1. User pipes output: pytest | TrimP compress --mode bash
2. Bash compressor applies: 60+ patterns
3. Compressed output returned: To stdout
4. Event logged: To database
5. User can review: TrimP quick or dashboard
```

### Full Analysis
```
1. User runs: TrimP token-optimizer
2. Database queried: Last 30 days of sessions
3. Analyzers run: 7 quality signals, compression stats, savings
4. Report generated: Markdown with recommendations
5. Saved to: ~/.trimp/reports/
```

## File Structure

```
~/Projects/copilot-token-optimizer/
├── TrimP/                          # Main package
│   ├── __init__.py
│   ├── cli.py                      # Main CLI (10 commands)
│   ├── db.py                       # SQLite schema (15 tables)
│   ├── session.py                  # Session management
│   ├── compaction.py               # Checkpoint management
│   ├── proxy.py                    # HTTP proxy server
│   ├── auto_runner.py              # Background daemon
│   ├── compression/                # 9 compression engines
│   │   ├── __init__.py
│   │   ├── bash.py
│   │   ├── search.py
│   │   ├── json_table.py
│   │   ├── delta.py
│   │   ├── skeleton.py
│   │   ├── archive.py
│   │   ├── verbosity.py
│   │   ├── structural.py
│   │   └── loop_detect.py
│   ├── quality/                    # Quality scoring
│   │   └── __init__.py
│   ├── commands/                   # CLI command implementations
│   │   ├── quick.py
│   │   ├── token_optimizer.py
│   │   ├── token_coach.py
│   │   ├── doctor.py
│   │   ├── savings.py
│   │   ├── report_cmd.py
│   │   ├── memory_review.py
│   │   ├── expand.py
│   │   └── resume_lean.py
│   └── dashboard/                  # Dashboard implementations
│       ├── terminal.py             # Textual TUI
│       ├── server.py               # FastAPI backend
│       └── frontend/               # React app
│           ├── src/
│           │   ├── App.jsx
│           │   ├── pages/
│           │   └── components/
│           ├── package.json
│           └── vite.config.js
├── scripts/
│   └── start-all.sh                # One-command setup
├── tests/
│   └── ...                         # Test suite
├── pyproject.toml                  # Package definition
├── README.md                       # Main documentation
├── QUICKSTART.md                   # Quick guide
├── CHEATSHEET.md                   # Quick reference
├── ARCHITECTURE.md                 # This file
├── GITHUB_COPILOT_INTEGRATION.md   # GitHub Copilot setup
└── YOUR_SETUP.md                   # User-specific setup

~/.trimp/                           # Runtime data
├── TrimP.db                        # SQLite database (15 tables)
├── auto-runner.log                 # Auto-runner logs
├── auto-runner.pid                 # Auto-runner PID
├── dashboard.log                   # Dashboard server logs
├── archived/                       # Large tool outputs (>4KB)
│   └── <session-id>/
│       └── <tool-use-id>.txt
└── reports/                        # Generated reports
    └── token-optimizer-<date>.md
```

## Performance Characteristics

### Compression Ratios
| Surface | Typical | Best Case |
|---------|---------|-----------|
| Bash output | 60-80% | 95% |
| Search results | 80-95% | 99% |
| JSON/tables | 30-50% | 70% |
| File re-reads | 80-95% | 99% |
| Code skeletons | 95-99% | 99.9% |
| Model output | 10-30% | 41% |

### Database Size
- Per session: ~50KB (with 50KB cap)
- Trends DB: ~10MB after 30 days (1000 sessions)
- Archives: Variable (depends on >4KB outputs)

### Resource Usage
- Auto-runner: ~10MB RAM, negligible CPU (checks every 30s)
- Dashboard server: ~50MB RAM, negligible CPU (polling only)
- React frontend: Standard browser memory

## Extension Points

### Adding a New Compression Engine
1. Create `TrimP/compression/new_engine.py`
2. Implement `compress(text: str) -> Tuple[str, Dict]`
3. Add to `TrimP/compression/__init__.py`
4. Add to `AUTO_COMPRESSION_ENGINES` in `auto_runner.py`
5. Add config key to `db.py` DEFAULT_CONFIG
6. Add feature toggle to dashboard Config page

### Adding a New CLI Command
1. Create `TrimP/commands/new_cmd.py`
2. Implement function with `@app.command()` decorator
3. Import in `TrimP/cli.py` and add to app
4. Add tests in `tests/`
5. Update CHEATSHEET.md

### Adding a New Dashboard Page
1. Create `TrimP/dashboard/frontend/src/pages/NewPage.jsx`
2. Add to pages object in `App.jsx`
3. Add sidebar item to `components/Sidebar.jsx`
4. Rebuild: `npm run build`
5. Reinstall: `pip install -e .`

## Security Considerations

### Data Storage
- All data stored locally (`~/.trimp/`)
- No network calls (except to API during proxy mode)
- No telemetry, no analytics
- Credential-safe compression (bash engine removes tokens/passwords)

### Proxy Mode
- Only intercepts if explicitly started: `TrimP proxy start`
- Requires explicit environment variable: `GITHUB_COPILOT_API_URL`
- Not enabled by default
- Optional feature

### Database
- SQLite with WAL mode (concurrent read/write)
- 50KB cap per session prevents disk fill
- Automatic cleanup of old archives (configurable)

## Future Enhancements

### Potential Features
- [ ] Real-time WebSocket updates (scaffolded, not enabled)
- [ ] Coach Mode page in dashboard (CLI only currently)
- [ ] Model routing suggestions based on activity mode
- [ ] Loop detection alerts in dashboard
- [ ] Cross-session trend charts (30-day view)
- [ ] Export reports to PDF/HTML
- [ ] Integration with GitHub Enterprise SSO
- [ ] Multi-user support (per-user databases)
- [ ] Plugin system for custom compression engines

### Performance Improvements
- [ ] Compression engine caching (avoid re-compressing identical text)
- [ ] Parallel compression (ThreadPoolExecutor for multiple engines)
- [ ] Database query optimization (more indexes)
- [ ] Archive compression (gzip archived files)
- [ ] Lazy loading in dashboard (pagination, infinite scroll)

---

**Built for GitHub Copilot Enterprise users**
**Inspired by Headroom, optimized for code compression**
