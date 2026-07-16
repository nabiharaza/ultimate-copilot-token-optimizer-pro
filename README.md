# TrimPy

**TrimPy (Trim-Pilot)** is a local token optimizer for GitHub Copilot Enterprise: **cut tokens, keep context**. It shapes eligible request context before it reaches the upstream model, records the before/after evidence locally, and keeps exact upstream usage separate from TrimPy estimates.

## What it supports

- **Compression modes:** `bash`, `search`, `json`, `skeleton`, `stopword`, `prompt`, `code`, `conversation`, `log`, `image`, `architecture`, `semantic`, `lingua`, `mcp`, `universal`
- **Core workflows:** audit, coaching, quick health checks, savings reports, per-component breakdowns, and `MEMORY.md` review
- **Session tools:** session lookup, checkpoint save/list, archived output expansion, and cold-session resume
- **Integrations:** GitHub Copilot CLI hooks, a local compression proxy, VS Code, PyCharm, Rider, IntelliJ, and the web/terminal dashboard
- **Storage:** local SQLite data under `~/.trimp/TrimP.db`
- **Copilot history import:** reads GitHub Copilot session-state logs when available under `~/.copilot/session-state`
- **Audit boundary:** upstream Agent Debug Logs and response `usage` are shown as actual observed usage; request-body shaping is shown as TrimPy's estimate when upstream usage is unavailable

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
trimp init
trimp doctor
```

## Start locally

From a fresh checkout, install the CLI once:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
trimp init
```

Build the web dashboard whenever frontend files change:

```bash
trimp dashboard --build
```

Start the token optimizer dashboard:

```bash
trimp quick
trimp dashboard --mode web --port 7432 --no-browser
```

Open `http://localhost:7432` for the web dashboard. To keep it running in the background with `tmux`:

```bash
tmux new-session -d -s trimp-dashboard 'trimp dashboard --mode web --port 7432 --no-browser'
tmux attach -t trimp-dashboard
```

Detach from the dashboard with `Ctrl-b`, then `d`. To stop the background dashboard:

```bash
tmux kill-session -t trimp-dashboard
```

To start the local compression proxy for supported clients:

```bash
trimp proxy start --port 8765
```

Start the near-real-time editor capture monitor after configuring VS Code, PyCharm, or Rider:

```bash
trimp vscode configure
trimp intellij configure
trimp monitor --mode editors --daemon
trimp monitor --mode editor-status
```

The editor monitor keeps importing VS Code Agent Debug Logs and Copilot session-state usage snapshots, checks the BYOK trace service and IDE HTTPS proxy, and reports stale or spooled editor traces. To run an explicit local intercept probe without contacting GitHub:

```bash
trimp intellij probe --editor pycharm
trimp intellij probe --editor rider
trimp intellij probe --editor vscode
```

To stop the editor monitor:

```bash
trimp monitor --mode editor-stop
```

The web dashboard refreshes mounted data sources every second while the tab is visible. The refresh icon in the sidebar broadcasts the same refresh signal immediately, so it is useful for an on-demand retry after starting an IDE proxy or finishing a Copilot request. Live activity can also receive events immediately through the WebSocket bridge.

## Docker

TrimPy has two long-running services: the **web dashboard** (port `7432`) and the **compression proxy** (port `8765`, the thing IDEs and the Copilot CLI actually send requests through). Both read and write the same SQLite database, so running them together is what "everything" means below.

### Quickest path: docker compose (dashboard + proxy)

```bash
docker compose up --build
```

- Dashboard: **http://localhost:7432**
- Proxy: **http://localhost:8765** (health check at `/v1/health`)

Both containers share a single named volume (`trimp-data`, mounted at `/home/trimp/.trimp`), so a compression made through the proxy shows up in the dashboard immediately. Stop everything with `docker compose down` (add `-v` to also delete the stored data). Run `docker compose logs -f proxy` or `docker compose logs -f dashboard` to tail either service.

### Just the dashboard

If you only want to browse existing data (or run the proxy natively instead), the single-container form still works:

```bash
docker build -t trimp .
docker run --rm -p 7432:7432 \
  -v trimp-data:/home/trimp/.trimp \
  -v "$HOME/.copilot:/home/trimp/.copilot:ro" \
  trimp
```

The `-v "$HOME/.copilot:...:ro"` mount is optional — include it if you want the dashboard to import GitHub Copilot session-state logs from your own machine.

### Just the proxy

```bash
docker run --rm -p 8765:8765 \
  -v trimp-data:/home/trimp/.trimp \
  trimp python3 byok_server.py --host 0.0.0.0 --port 8765
```

### How to connect an IDE or the Copilot CLI to the dockerized proxy

The proxy's contract doesn't change based on where it runs — Docker just publishes port `8765` to `localhost` on your machine, so every one of these points at `http://localhost:8765` exactly as it would for a natively-run proxy:

- **GitHub Copilot CLI (BYOK):**
  ```bash
  export COPILOT_PROVIDER_URL=http://localhost:8765/v1
  ```
- **VS Code / PyCharm / Rider / IntelliJ:** these IDEs are configured by editing *your own machine's* settings files (`trimp vscode configure`, `trimp intellij configure` — see [IDE setup and verification](#ide-setup-and-verification)). Run those two commands from a natively installed `trimp` (`pip install -e .`) on your host, not inside the container — the container has no access to your IDE's config directory. Once configured, point the IDE's proxy settings at `localhost:8765` as usual; it makes no difference to the IDE whether that port is served by a container or a local process.
- **Dashboard:** just open `http://localhost:7432` in a browser.

### Persistence and health

- All state lives at `/home/trimp/.trimp` inside the container (`~/.trimp` for a native install) — back up or reset it via the `trimp-data` volume.
- Both images expose a `HEALTHCHECK` (`docker ps` shows `healthy`/`unhealthy`): the dashboard hits `/api/health`, the proxy hits `/v1/health`.
- Containers run as a non-root `trimp` user.

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

## Dashboard pages

The active navigation is intentionally small and evidence-oriented:

- **Overview:** current requests, estimated before/after/saved tokens, estimated cost saved, model mix, request-volume chart, and recent activity.
- **Repositories:** repository-level requests, before volume, saved tokens, reduction, model, IDE, and local-time attribution.
- **Trim policy:** repository scope, conservative/balanced/aggressive policy, per-algorithm switches, and estimated impact.
- **Connections:** configured proxy and IDE bridge endpoints.
- **Conversations:** searchable session groups with prompt, repository, IDE, model, exact Agent Debug Log usage when available, context details, and cost estimates.
- **Live activity:** request-level events and an idle flatline when TrimPy is off or no traffic is arriving.
- **A/B preflight:** local reproducible baseline versus optimized request-body evidence.
- **Validation:** quick, standard, and full local certification runs with scenario-level audit evidence.
- **Diff review:** before/after context changes, algorithm attribution, restore, and approval workflow.
- **Alerts, Help & feedback, Settings:** operational recovery, documentation, feedback, health, retention, database controls, pricing, and compression configuration.

## IDE setup and verification

Configure an IDE with the local bridge, then fully restart the IDE so its Copilot client loads the new proxy settings:

```bash
trimp vscode configure
trimp intellij configure
```

Use a fresh chat in a known repository and keep the model fixed. In **Conversations**, filter by the IDE and repository, then compare a TrimPy-off request with the same prompt sent with TrimPy on. The evidence row should preserve the prompt fingerprint, timestamps, repository, IDE, model label, proxy before/after estimate, actual input/output/cached tokens from the Agent Debug Logs when present, and the model-specific API-equivalent cost estimate. Restart Rider/PyCharm/IntelliJ after changing proxy configuration; no absolute project path is required.

For a management proof, use the same fixed prompt across five contexts: long conversation, repeated tool output, code context, multiple files, and a short request. Show the matched off/on pair, then open its trace details. The local A/B and Validation pages measure deterministic request shaping; the IDE pair demonstrates real traffic. Neither should be presented as an invoice claim for GitHub Enterprise quota unless the upstream source exposes that exact field.

## Development and QA

Run the backend tests, production frontend build, and repository hygiene checks before sharing a build:

```bash
pytest -q tests
npm --prefix TrimP/dashboard/frontend run build
git diff --check
```

With the dashboard running at `http://localhost:7432`, staff QA should visit every navigation page, switch light/dark mode, use the sidebar refresh control, verify the `Updated` timestamp changes each second, and exercise every visible action. Check that destructive database actions require confirmation, filter/search controls change their result set, links navigate to real pages, and no browser console/runtime errors occur. See [docs/TESTING.md](docs/TESTING.md) for the full manual, automated, evidence, and troubleshooting procedure.

## Version

```bash
trimp version
```
