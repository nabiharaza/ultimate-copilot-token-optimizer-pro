# Trim-Pilot (TrimP)

Trim-Pilot, or **TrimP**, is a local token-optimization layer for GitHub Copilot workflows. It trims noisy context, tracks what was compressed, keeps local audit data, and provides a dashboard plus helper commands for recovery and analysis.

## What it supports

- **Compression modes:** `bash`, `search`, `json`, `skeleton`, `stopword`, `prompt`, `code`, `conversation`, `log`, `image`, `architecture`, `semantic`, `lingua`, `mcp`, `universal`
- **Core workflows:** audit, coaching, quick health checks, savings reports, per-component breakdowns, and `MEMORY.md` review
- **Session tools:** session lookup, checkpoint save/list, archived output expansion, and cold-session resume
- **Integrations:** GitHub Copilot CLI hooks, a local compression proxy, VS Code, PyCharm/Rider/IntelliJ, and the web/terminal dashboard
- **Storage:** local SQLite data under `~/.trimp/TrimP.db`
- **Copilot history import:** reads GitHub Copilot session-state logs when available under `~/.copilot/session-state`

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
trimp init
trimp doctor
```

## Start locally

```bash
trimp quick
trimp dashboard --mode terminal
trimp dashboard --build
trimp dashboard --mode web --port 7432 --no-browser
```

Open `http://localhost:7432` for the web dashboard after building the frontend.

## Docker

Build and run the dashboard in a container:

```bash
docker build -t trimp .
docker run --rm -p 7432:7432 \
  -v trimp-data:/root/.trimp \
  -v "$HOME/.copilot:/root/.copilot:ro" \
  trimp
```

The container starts the web dashboard on port `7432` and persists local TrimP state in the `trimp-data` volume.

## Commands

| Command | Purpose |
| --- | --- |
| `trimp token-optimizer` | Full audit with guided fixes |
| `trimp token-coach` | 30-day trend analysis and recommendations |
| `trimp quick` | Fast installation and health check |
| `trimp doctor --fix` | Diagnose and repair local setup |
| `trimp savings` | Estimate savings across pricing tiers |
| `trimp report` | Show per-component token breakdown |
| `trimp memory-review` | Audit a `MEMORY.md` file |
| `trimp resume-lean` | Restore checkpoint context for a cold session |
| `trimp expand <key>` | Retrieve archived tool output |
| `trimp session show` | Show the current session |
| `trimp checkpoint save` | Save a checkpoint |
| `trimp checkpoint list` | List checkpoints |
| `trimp auto start` | Start the background auto-runner |
| `trimp monitor` | Watch events or logs |
| `trimp config list` | List current configuration |
| `trimp proxy start` | Start the local compression proxy |
| `trimp copilot install` | Install Copilot CLI hooks |
| `trimp intellij configure` | Configure JetBrains proxy settings |
| `trimp vscode configure` | Configure VS Code to use the proxy |

## Example usage

```bash
trimp compress "very large tool output" --mode bash
cat build.log | trimp compress --mode log
trimp copilot measure --file payload.json
trimp checkpoint save --title "Before refactor"
```

## Dashboard modes

- `terminal` shows the TUI dashboard in your terminal
- `web` starts the FastAPI dashboard in the browser or headless
- `both` runs the web dashboard and terminal view together

## Version

```bash
trimp version
```
