# Trim-Pilot - A token optimizer for GitHub Copilot (cut tokens, keep context)

Trim-Pilot, or **TrimP**, is a local enterprise observability and token-optimization layer for GitHub Copilot Enterprise. It shapes eligible request context before it reaches Copilot, preserves the original trace for audit, and shows what was actually sent, what was saved, and what the upstream model reported.

TrimP is designed for teams that need measurable savings without silently deleting context. Every compression event records the source client, repository, IDE, model, timestamps, before/after estimates, algorithm attribution, request bodies, response usage, and recommendations.

## What TrimP does

- Reduces repetitive text, oversized tool output, JSON noise, stale code context, duplicate blocks, comments, and low-value formatting.
- Supports conservative, balanced, and aggressive shaping policies with reversible diff evidence.
- Routes GitHub Copilot Enterprise traffic through a local BYOK or HTTPS interception proxy where the client permits it.
- Supports Copilot CLI, PyCharm, Rider, and VS Code integration paths.
- Stores local audit data in SQLite and exposes request, repository, model, conversation, and service-health views.
- Shows real token estimates alongside upstream actual usage when GitHub returns usage metadata. Estimates and billed usage are intentionally labeled separately.
- Imports exact GitHub Copilot Agent Debug Log usage snapshots from `~/.copilot/session-state/*/events.jsonl` when the local agent writes them.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
trimp init
trimp doctor
```

## Quick start

```bash
trimp quick
trimp dashboard --mode web --port 7432
```

Open [http://localhost:7432](http://localhost:7432). The dashboard includes:

- 1H, 24H, 7D, 30D, 3M, 1Y, and all-time windows
- Auto, minute, hour, day, week, month, and year chart buckets
- Actual request volume versus TrimP-sent volume
- Repository-level requests, before volume, saved tokens, and reduction
- Live trim events with algorithm attribution
- Conversation traces with original, optimized, response, and debug context
- Agent Debug Log snapshots with input, cached input, output, total tokens, model turns, tool calls, errors, compaction tokens, AIU, model, repository, and local time
- Service health for the BYOK proxy and IDE HTTPS bridge

### Agent log accounting

GitHub Copilot CLI agent logs include a cumulative `session.shutdown` usage record. TrimP imports `modelMetrics` without forwarding or modifying it:

```text
actual total tokens = actual input tokens + actual output tokens
cached input tokens = cache-read tokens reported by Copilot
```

For example, a log containing `174,312` input tokens, `443` output tokens, and `83,840` cached input tokens is shown as `174,755` total tokens. Cached input is displayed separately because it is a billing and quota dimension, not silently subtracted from total input. TrimP never presents these upstream numbers as compression savings: TrimP savings remain `estimated before - estimated after` until a paired upstream baseline exists.

The importer is read-only with respect to Copilot files and does not store prompt bodies or tool arguments. The dashboard exposes the imported snapshots at `/api/agent-logs/sessions` and the aggregate at `/api/agent-logs/usage`; `POST /api/agent-logs/import` forces a refresh.

## CLI commands

| Command | Purpose |
| --- | --- |
| `trimp token-optimizer` | Full audit with guided fixes |
| `trimp token-coach` | Trend analysis and recommendations |
| `trimp quick` | Fast installation and health check |
| `trimp doctor --fix` | Diagnose and repair local setup |
| `trimp savings` | Estimate savings across pricing tiers |
| `trimp report` | Show per-component token breakdown |
| `trimp dashboard` | Start the terminal or web dashboard |
| `trimp session` | Inspect and manage sessions |
| `trimp compress` | Manually test a compression mode |
| `trimp proxy` | Start and test the local proxy |
| `trimp intellij` | Configure or run the JetBrains bridge |
| `trimp vscode` | Configure the VS Code proxy path |

## Enterprise routing

TrimP does not replace GitHub Copilot authentication. GitHub Enterprise continues to own identity, policy, model access, and upstream billing. TrimP observes and shapes eligible local request traffic before forwarding it through the configured endpoint.

```text
PyCharm / Rider / VS Code / Copilot CLI
                 |
                 v
       TrimP local HTTPS bridge
                 |
                 v
      context shaper + audit trace
                 |
                 v
       GitHub Copilot Enterprise
                 |
                 v
          response + usage data
```

Start the local integration using the dashboard or CLI. For JetBrains IDEs, verify the IDE proxy points to `127.0.0.1:8767`; for the BYOK path, verify the service is listening on `127.0.0.1:8766`.

## Compression and trust

TrimP records an estimated calculation as:

```text
estimated tokens saved = estimate(original request) - estimate(optimized request)
request reduction %    = saved / estimate(original request) * 100
```

The dashboard also reports actual input, cached input, output, and total tokens when present in the upstream response. These actual fields are not reverse-engineered from the estimate. Diff Review shows the exact changed fields and the algorithm responsible, and the original request remains available for audit and rollback.

## Development

```bash
python3 -m pytest tests -q
trimp dashboard --build
```

The frontend lives in `TrimP/dashboard/frontend`. The Python package is `TrimP`; the supported console command is `trimp`.

## Data and privacy

TrimP is local-first. Runtime data is stored under `~/.trimp/` and the project dashboard database is kept under `data/TrimP.db`. Request and debug traces may contain source code or prompts, so protect the local database and logs using the same controls as the IDE workspace.

## Product identity

**Trim-Pilot / TrimP**  
Cut tokens. Keep context.  
GitHub Copilot Enterprise token observability and optimization.
