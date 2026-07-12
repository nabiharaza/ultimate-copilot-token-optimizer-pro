"""Web dashboard — FastAPI backend."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from TrimP.db import db, get_config, DB_PATH
from TrimP.chat_optimizer import ChatPayloadOptimizer, estimate_tokens
from TrimP.copilot_logs import (
    discover_events_files,
    import_vscode_debug_sessions,
    parse_events_file,
)
from TrimP.quality import score_session
from TrimP.session import get_or_create_session, get_recent_sessions

app = FastAPI(title="TrimP Dashboard", version="1.0.0")

test_optimizer = ChatPayloadOptimizer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

_AGENT_LOG_CACHE: dict[str, tuple[float, int, dict]] = {}
_DEBUG_LOG_CACHE: dict[str, tuple[float, int, dict]] = {}


MODEL_INPUT_PRICES_PER_1M = {
    "haiku": 0.80,
    "sonnet": 3.00,
    "opus": 15.00,
    "gpt": 10.00,
    "gemini": 3.00,
    "default": 3.00,
}

MODEL_PRICING_PER_1M = {
    "haiku": {"input": 0.80, "output": 4.00, "cached": 0.08},
    "sonnet": {"input": 3.00, "output": 15.00, "cached": 0.30},
    "opus": {"input": 15.00, "output": 75.00, "cached": 1.50},
    "gpt-5-mini": {"input": 0.25, "output": 2.00, "cached": 0.025},
    "gpt": {"input": 1.25, "output": 10.00, "cached": 0.125},
    "gemini": {"input": 1.25, "output": 5.00, "cached": 0.125},
    "default": {"input": 3.00, "output": 15.00, "cached": 0.30},
}


def _threshold_for_range(range_name: str) -> str:
    now = datetime.now(timezone.utc)
    if range_name == "hour":
        return (now - timedelta(hours=1)).isoformat()
    if range_name == "day":
        return (now - timedelta(days=1)).isoformat()
    if range_name == "10d":
        return (now - timedelta(days=10)).isoformat()
    if range_name == "15d":
        return (now - timedelta(days=15)).isoformat()
    if range_name == "20d":
        return (now - timedelta(days=20)).isoformat()
    if range_name == "week":
        return (now - timedelta(weeks=1)).isoformat()
    if range_name == "month":
        return (now - timedelta(days=30)).isoformat()
    if range_name == "quarter":
        return (now - timedelta(days=90)).isoformat()
    if range_name == "year":
        return (now - timedelta(days=365)).isoformat()
    return "2000-01-01T00:00:00"


def _parse_event_time(value: str | None) -> datetime | None:
    """Parse stored UTC timestamps and return them in the computer's local zone."""
    if not value:
        return None
    try:
        text = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone()
    except (TypeError, ValueError):
        return None


def _auto_granularity(range_name: str) -> str:
    return {
        "hour": "minute",
        "day": "hour",
        "week": "day",
        "month": "day",
        "quarter": "week",
        "year": "month",
        "all": "month",
    }.get(range_name, "day")


def _bucket_time(value: datetime, granularity: str) -> datetime:
    if granularity == "minute":
        return value.replace(second=0, microsecond=0)
    if granularity == "hour":
        return value.replace(minute=0, second=0, microsecond=0)
    if granularity == "day":
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == "week":
        start = value - timedelta(days=value.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == "year":
        return value.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _bucket_label(value: datetime, granularity: str) -> str:
    if granularity == "minute":
        return value.strftime("%b %d, %H:%M").replace(" 0", " ")
    if granularity == "hour":
        return value.strftime("%b %d, %H:%M").replace(" 0", " ")
    if granularity == "day":
        return value.strftime("%b %d").replace(" 0", " ")
    if granularity == "week":
        return f"Week of {value.strftime('%b %d').replace(' 0', ' ')}"
    if granularity == "year":
        return value.strftime("%Y")
    return value.strftime("%b %Y")


def _model_rate(model: str | None) -> float:
    model_l = (model or "").lower()
    for key, rate in MODEL_INPUT_PRICES_PER_1M.items():
        if key != "default" and key in model_l:
            return rate
    return MODEL_INPUT_PRICES_PER_1M["default"]


def _dollars_saved(tokens_saved: int, model: str | None = None) -> float:
    return round((tokens_saved / 1_000_000.0) * _model_rate(model), 6)


def _actual_cost(input_tokens: int, output_tokens: int, cached_tokens: int, model: str | None) -> float:
    """Estimate API-equivalent cost from exact IDE usage, not GitHub billing."""
    name = (model or "").lower()
    pricing = next((value for key, value in MODEL_PRICING_PER_1M.items() if key != "default" and key in name), MODEL_PRICING_PER_1M["default"])
    cached = min(max(int(cached_tokens or 0), 0), max(int(input_tokens or 0), 0))
    uncached = max(int(input_tokens or 0) - cached, 0)
    return round((uncached * pricing["input"] + cached * pricing["cached"] + int(output_tokens or 0) * pricing["output"]) / 1_000_000.0, 8)


def _pricing_for(model: str | None) -> dict[str, float]:
    name = (model or "").lower()
    return next((value for key, value in MODEL_PRICING_PER_1M.items() if key != "default" and key in name), MODEL_PRICING_PER_1M["default"])


def _safe_json(value: str | None) -> dict:
    if not value:
        return {}
    try:
        payload = json.loads(value)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _sync_agent_logs(limit: int = 200) -> int:
    """Import changed Copilot event snapshots without retaining prompt content."""
    imported = 0
    for path in discover_events_files(limit=limit):
        try:
            stat = path.stat()
        except OSError:
            continue
        key = str(path)
        cached = _AGENT_LOG_CACHE.get(key)
        if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
            continue
        else:
            snapshot = parse_events_file(path)
            if snapshot:
                _AGENT_LOG_CACHE[key] = (stat.st_mtime, stat.st_size, snapshot)
        if not snapshot:
            continue
        if not snapshot.get("input_tokens") and not snapshot.get("output_tokens"):
            continue
        with db() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO copilot_agent_usage (
                    source_path, source_hash, source_session_id, event_start, event_end,
                    cwd, repository, model, copilot_version, requests, user_messages,
                    model_turns, tool_calls, errors, compactions, compaction_tokens,
                    input_tokens, output_tokens, cached_input_tokens, cache_write_tokens,
                    reasoning_tokens, total_tokens, system_tokens, conversation_tokens,
                    tool_definitions_tokens, total_nano_aiu, model_usage, is_complete,
                    imported_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    snapshot["source_path"], snapshot["source_hash"], snapshot["session_id"],
                    snapshot.get("event_start"), snapshot.get("event_end"), snapshot.get("cwd"),
                    snapshot.get("repository"), snapshot.get("model"), snapshot.get("copilot_version"),
                    snapshot.get("requests", 0), snapshot.get("user_messages", 0), snapshot.get("model_turns", 0),
                    snapshot.get("tool_calls", 0), snapshot.get("errors", 0), snapshot.get("compactions", 0),
                    snapshot.get("compaction_tokens", 0), snapshot.get("input_tokens", 0), snapshot.get("output_tokens", 0),
                    snapshot.get("cached_input_tokens", 0), snapshot.get("cache_write_tokens", 0),
                    snapshot.get("reasoning_tokens", 0), snapshot.get("total_tokens", 0), snapshot.get("system_tokens", 0),
                    snapshot.get("conversation_tokens", 0), snapshot.get("tool_definitions_tokens", 0),
                    snapshot.get("total_nano_aiu", 0), json.dumps(snapshot.get("model_usage", []), separators=(",", ":")),
                    int(bool(snapshot.get("is_complete"))), datetime.now(timezone.utc).isoformat(),
                ),
            )
        imported += 1
    return imported


def _sync_debug_logs(limit: int = 200) -> int:
    """Import per-turn IDE debug traces while retaining their full local context."""
    imported = 0
    for snapshot in import_vscode_debug_sessions(limit=limit):
        source_path = str(snapshot["source_path"])
        try:
            stat = Path(source_path).stat()
        except OSError:
            continue
        cached = _DEBUG_LOG_CACHE.get(source_path)
        if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
            continue
        _DEBUG_LOG_CACHE[source_path] = (stat.st_mtime, stat.st_size, snapshot)
        turns = snapshot.get("turns") or []
        primary = [turn for turn in turns if turn.get("request_kind") == "primary"]
        if not primary:
            continue
        model = primary[0].get("model") or "unknown"
        started = snapshot.get("event_start") or datetime.now(timezone.utc).isoformat()
        ended = snapshot.get("event_end") or started
        with db() as conn:
            conn.execute(
                """INSERT INTO sessions (id, started_at, ended_at, cwd, repository, branch,
                   total_tokens_in, total_tokens_out, model, status, label)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
                   ON CONFLICT(id) DO UPDATE SET ended_at=excluded.ended_at,
                   cwd=excluded.cwd, repository=excluded.repository, model=excluded.model,
                   total_tokens_in=excluded.total_tokens_in, total_tokens_out=excluded.total_tokens_out,
                   status='completed', label=excluded.label""",
                (
                    snapshot["parent_session_id"], started, ended, snapshot.get("cwd"),
                    snapshot.get("repository"), "unknown",
                    sum(int(turn.get("input_tokens") or 0) for turn in primary),
                    sum(int(turn.get("output_tokens") or 0) for turn in primary),
                    model, primary[0].get("user_message") or "VS Code agent session",
                ),
            )
            for turn in turns:
                conn.execute(
                    """INSERT INTO copilot_debug_turns (
                       source_key, source_path, parent_session_id, child_session_id, turn_index,
                       request_kind, occurred_at, model, debug_name, input_tokens, output_tokens,
                       cached_tokens, total_tokens, ttft_ms, max_output_tokens, copilot_usage_nano_aiu,
                       user_message, context_json, trace_json, cwd, repository, ide, status, imported_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(source_key) DO UPDATE SET
                       input_tokens=excluded.input_tokens, output_tokens=excluded.output_tokens,
                       cached_tokens=excluded.cached_tokens, total_tokens=excluded.total_tokens,
                       context_json=excluded.context_json, trace_json=excluded.trace_json,
                       imported_at=excluded.imported_at""",
                    (
                        turn["source_key"], turn["source_path"], turn["parent_session_id"],
                        turn.get("child_session_id"), turn.get("turn_index", 0), turn.get("request_kind"),
                        turn.get("occurred_at"), turn.get("model"), turn.get("debug_name"),
                        turn.get("input_tokens", 0), turn.get("output_tokens", 0), turn.get("cached_tokens", 0),
                        turn.get("total_tokens", 0), turn.get("ttft_ms", 0), turn.get("max_output_tokens", 0),
                        turn.get("copilot_usage_nano_aiu", 0), turn.get("user_message"), turn.get("context_json"),
                        turn.get("trace_json"), turn.get("cwd"), turn.get("repository"), turn.get("ide"),
                        turn.get("status"), datetime.now(timezone.utc).isoformat(),
                    ),
                )
            # Keep the familiar turns endpoint useful for exact primary IDE turns.
            for turn in primary:
                conn.execute(
                    """INSERT INTO turns (session_id, turn_index, user_message, assistant_response,
                       tokens_in, tokens_out, tokens_saved, model, timestamp)
                       SELECT ?, ?, ?, '', ?, ?, 0, ?, ?
                       WHERE NOT EXISTS (SELECT 1 FROM turns WHERE session_id=? AND turn_index=?)""",
                    (snapshot["parent_session_id"], turn.get("turn_index", 0), turn.get("user_message", ""),
                     turn.get("input_tokens", 0), turn.get("output_tokens", 0), turn.get("model"), turn.get("occurred_at") or started,
                     snapshot["parent_session_id"], turn.get("turn_index", 0)),
                )
        imported += 1
    return imported


def _agent_log_rows(threshold: str, limit: int = 200) -> list[dict]:
    _sync_agent_logs()
    with db() as conn:
        rows = conn.execute(
            """SELECT * FROM copilot_agent_usage
               WHERE COALESCE(event_end, event_start, imported_at) >= ?
               ORDER BY COALESCE(event_end, event_start, imported_at) DESC LIMIT ?""",
            (threshold, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def _agent_usage_summary(threshold: str) -> dict:
    rows = _agent_log_rows(threshold)
    fields = ("requests", "user_messages", "model_turns", "tool_calls", "errors", "compactions",
              "compaction_tokens", "input_tokens", "output_tokens", "cached_input_tokens", "cache_write_tokens",
              "reasoning_tokens", "total_tokens", "system_tokens", "conversation_tokens",
              "tool_definitions_tokens", "total_nano_aiu")
    totals = {field: sum(int(row.get(field) or 0) for row in rows) for field in fields}
    model_mix: dict[str, dict[str, int]] = {}
    for row in rows:
        for model_row in _safe_json_list(row.get("model_usage")):
            model = str(model_row.get("model") or row.get("model") or "unknown")
            item = model_mix.setdefault(model, {"model": model, "requests": 0, "input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0, "cache_write_tokens": 0, "reasoning_tokens": 0, "total_nano_aiu": 0})
            for field in ("requests", "input_tokens", "output_tokens", "cached_input_tokens", "cache_write_tokens", "reasoning_tokens", "total_nano_aiu"):
                item[field] += int(model_row.get(field) or 0)
    return {
        **totals,
        "sessions": len(rows),
        "last_seen": max((row.get("event_end") or row.get("event_start") or "" for row in rows), default=None),
        "source": "github_copilot_agent_logs" if rows else "not_reported",
        "models": sorted(model_mix.values(), key=lambda item: item["input_tokens"] + item["output_tokens"], reverse=True),
        "sessions_detail": rows,
    }


def _safe_json_list(value: str | list | None) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


# ──────────────────────── REST API ────────────────────────────────────────

@app.get("/api/status")
async def status():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    """Full health check — DB, sessions, recent compressions, proxy status."""
    db_ok = DB_PATH.exists()
    compression_count = 0
    session_count = 0
    active_sessions = 0
    recent_compression = None

    if db_ok:
        try:
            with db() as conn:
                compression_count = conn.execute(
                    "SELECT COUNT(*) as c FROM compressions"
                ).fetchone()["c"]
                session_count = conn.execute(
                    "SELECT COUNT(*) as c FROM sessions"
                ).fetchone()["c"]
                active_sessions = conn.execute(
                    "SELECT COUNT(*) as c FROM sessions WHERE status='active'"
                ).fetchone()["c"]
                row = conn.execute(
                    """SELECT compressed_at, compressor, tokens_before, tokens_after
                       FROM compressions ORDER BY compressed_at DESC LIMIT 1"""
                ).fetchone()
                if row:
                    recent_compression = dict(row)
        except Exception as e:
            db_ok = False

    proxy_running = False
    try:
        r = httpx.get("http://localhost:8765/TrimP/status", timeout=1.0)
        proxy_running = r.status_code == 200
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "db": {
            "path": str(DB_PATH),
            "exists": db_ok,
            "sessions": session_count,
            "active_sessions": active_sessions,
            "compressions": compression_count,
            "recent_compression": recent_compression,
        },
        "proxy_running": proxy_running,
    }


@app.get("/api/live-health")
async def live_health():
    """Fast operational status for the live dashboard indicator."""
    services = []
    for name, url in (("BYOK proxy", "http://127.0.0.1:8766/v1/health"),):
        try:
            response = httpx.get(url, timeout=1.5)
            payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            services.append({"name": name, "status": "up" if response.status_code == 200 else "degraded", "detail": payload.get("api_url", "")})
        except Exception as exc:
            services.append({"name": name, "status": "down", "detail": str(exc)[:120]})
    try:
        from TrimP.intellij_proxy import proxy_status
        ide_proxy = proxy_status()
        services.append({"name": "IDE HTTPS proxy", "status": "up" if ide_proxy.get("running") else "down", "detail": f"127.0.0.1:{ide_proxy.get('port', 8767)}"})
        configured = list(ide_proxy.get("configured_ides", []))
        if ide_proxy.get("vscode_configured"):
            configured.append({
                "product": "VS Code",
                "path": ide_proxy.get("vscode_settings", ""),
                "host": "127.0.0.1",
                "port": int(ide_proxy.get("vscode_port") or ide_proxy.get("port") or 8767),
            })
    except Exception as exc:
        configured = []
        services.append({"name": "IDE HTTPS proxy", "status": "degraded", "detail": str(exc)[:120]})
    with db() as conn:
        rows = conn.execute(
            """SELECT request_source, COUNT(*) AS requests,
                      COALESCE(SUM(tokens_before - tokens_after), 0) AS saved
               FROM compressions GROUP BY request_source"""
        ).fetchall()
    clients = []
    for row in rows:
        source = str(row["request_source"] or "unknown")
        label = "PyCharm" if "pycharm" in source else "Rider" if "rider" in source else "VS Code" if "vscode" in source else "Copilot CLI" if "cli" in source else source
        clients.append({"name": label, "requests": int(row["requests"] or 0), "tokens_saved": int(row["saved"] or 0), "active": int(row["requests"] or 0) > 0})
    return {"status": "up" if all(s["status"] == "up" for s in services) else "degraded", "checked_at": datetime.now(timezone.utc).isoformat(), "services": services, "configured_ides": configured, "clients": clients}


@app.post("/api/agent-logs/import")
async def import_agent_logs():
    """Refresh exact local Copilot agent usage snapshots."""
    from TrimP.db import prune_expired_logs
    _AGENT_LOG_CACHE.clear()
    count = _sync_agent_logs()
    return {"imported": count, "source": str(Path.home() / ".copilot" / "session-state"), "read_only": True, "pruned": prune_expired_logs()}


@app.get("/api/agent-logs/sessions")
async def agent_log_sessions(range: str = "all", limit: int = 100):
    threshold = _threshold_for_range(range)
    rows = _agent_log_rows(threshold, limit=max(1, min(limit, 500)))
    for row in rows:
        row["model_usage"] = _safe_json_list(row.get("model_usage"))
        row["source"] = "github_copilot_agent_logs"
    return rows


@app.get("/api/agent-logs/usage")
async def agent_log_usage(range: str = "day"):
    return _agent_usage_summary(_threshold_for_range(range))


@app.get("/api/copilot/debug-sessions")
async def copilot_debug_sessions(range: str = "day", limit: int = 50):
    """Return parent IDE sessions with exact per-model-turn debug records."""
    threshold = _threshold_for_range(range)
    _sync_debug_logs()
    with db() as conn:
        session_rows = conn.execute(
            """SELECT parent_session_id, MIN(occurred_at) AS started_at,
                      MAX(occurred_at) AS ended_at, MAX(cwd) AS cwd,
                      MAX(repository) AS repository, MAX(ide) AS ide,
                      COUNT(*) AS request_count,
                      SUM(CASE WHEN request_kind='primary' THEN 1 ELSE 0 END) AS model_turns,
                      SUM(input_tokens) AS all_input_tokens, SUM(output_tokens) AS all_output_tokens,
                      SUM(cached_tokens) AS all_cached_tokens, SUM(total_tokens) AS all_total_tokens
               FROM copilot_debug_turns
               WHERE COALESCE(occurred_at, imported_at) >= ?
               GROUP BY parent_session_id
               ORDER BY ended_at DESC LIMIT ?""",
            (threshold, max(1, min(limit, 200))),
        ).fetchall()
        output = []
        for session_row in session_rows:
            session = dict(session_row)
            turns = conn.execute(
                """SELECT * FROM copilot_debug_turns
                   WHERE parent_session_id=? ORDER BY occurred_at ASC, source_key ASC""",
                (session["parent_session_id"],),
            ).fetchall()
            turn_items = []
            primary_input = primary_output = primary_cached = primary_total = 0
            exact_cost = primary_cost = 0.0
            model_costs: dict[str, float] = {}
            for row in turns:
                item = dict(row)
                try:
                    item["context"] = json.loads(item.get("context_json") or "{}")
                except (TypeError, ValueError, json.JSONDecodeError):
                    item["context"] = {}
                try:
                    item["trace"] = json.loads(item.get("trace_json") or "{}")
                except (TypeError, ValueError, json.JSONDecodeError):
                    item["trace"] = {}
                item["exact_cost_estimate"] = _actual_cost(item["input_tokens"], item["output_tokens"], item["cached_tokens"], item["model"])
                item["uncached_input_tokens"] = max(int(item["input_tokens"] or 0) - int(item["cached_tokens"] or 0), 0)
                item["pricing_per_million"] = _pricing_for(item["model"])
                exact_cost += item["exact_cost_estimate"]
                model_costs[item["model"]] = round(model_costs.get(item["model"], 0) + item["exact_cost_estimate"], 8)
                if item["request_kind"] == "primary":
                    primary_input += int(item["input_tokens"] or 0)
                    primary_output += int(item["output_tokens"] or 0)
                    primary_cached += int(item["cached_tokens"] or 0)
                    primary_total += int(item["total_tokens"] or 0)
                    primary_cost += item["exact_cost_estimate"]
                # Full context is intentionally available behind an expand control.
                item.pop("context_json", None)
                item.pop("trace_json", None)
                item.pop("imported_at", None)
                turn_items.append(item)

            # Correlate nearby TrimPy proxy records by repo and time. This is
            # shown as an estimate because IDE and proxy session IDs differ.
            trim = conn.execute(
                """SELECT COUNT(*) AS requests, COALESCE(SUM(c.tokens_before),0) AS tokens_before,
                          COALESCE(SUM(c.tokens_after),0) AS tokens_after,
                          COALESCE(SUM(c.tokens_before-c.tokens_after),0) AS tokens_saved
                   FROM compressions c LEFT JOIN sessions s ON s.id=c.session_id
                   WHERE c.source='byok' AND c.request_source LIKE '%vscode%'
                     AND s.repository=? AND julianday(c.compressed_at) BETWEEN julianday(?) - (30.0 / 86400.0) AND julianday(?) + (30.0 / 86400.0)""",
                (session.get("repository"), session.get("started_at"), session.get("ended_at")),
            ).fetchone()
            trim = dict(trim) if trim else {"requests": 0, "tokens_before": 0, "tokens_after": 0, "tokens_saved": 0}
            trim["savings_pct"] = round((trim["tokens_saved"] / trim["tokens_before"] * 100) if trim["tokens_before"] else 0, 2)
            primary_model = next((item.get("model") for item in turn_items if item.get("request_kind") == "primary"), None)
            trim["estimated_cost_saved"] = _dollars_saved(trim["tokens_saved"], primary_model or next(iter(model_costs), None))
            output.append({
                "session_id": session["parent_session_id"],
                "started_at": session["started_at"],
                "ended_at": session["ended_at"],
                "cwd": session["cwd"],
                "repository": session["repository"],
                "ide": session["ide"],
                "request_count": int(session["request_count"] or 0),
                "model_turns": int(session["model_turns"] or 0),
                "primary_usage": {"input_tokens": primary_input, "cached_tokens": primary_cached, "output_tokens": primary_output, "total_tokens": primary_total},
                "all_usage": {"input_tokens": int(session["all_input_tokens"] or 0), "cached_tokens": int(session["all_cached_tokens"] or 0), "output_tokens": int(session["all_output_tokens"] or 0), "total_tokens": int(session["all_total_tokens"] or 0)},
                "usage_source": "ide_debug_log",
                "exact_cost_estimate": round(exact_cost, 8),
                "primary_cost_estimate": round(primary_cost, 8),
                "model_costs": model_costs,
                "pricing_basis": "API-equivalent estimate from exact IDE tokens; GitHub Enterprise billing may differ",
                "trimpy": trim,
                "turns": turn_items,
            })
        # Fallback for PyCharm, Rider, and other JetBrains clients. These IDEs
        # do not emit VS Code's JSONL Agent Debug Logs, but the HTTPS bridge
        # still records a complete session-scoped request trace.
        debug_ids = {item["session_id"] for item in output}
        proxy_rows = conn.execute(
            """SELECT c.*, s.cwd, s.repository, s.branch, s.label, s.status
               FROM compressions c LEFT JOIN sessions s ON s.id=c.session_id
               WHERE c.source='byok' AND c.compressed_at >= ?
                 AND c.request_source IS NOT NULL
                 AND (c.request_source LIKE '%pycharm%' OR c.request_source LIKE '%rider%' OR c.request_source LIKE '%jetbrains%' OR c.request_source LIKE '%vscode%')
               ORDER BY c.compressed_at ASC""",
            (threshold,),
        ).fetchall()
        proxy_groups: dict[str, list[dict]] = {}
        for row in proxy_rows:
            item = dict(row)
            if item.get("session_id") in debug_ids:
                continue
            if "vscode" in str(item.get("request_source") or "").lower():
                correlated = conn.execute(
                    """SELECT 1 FROM copilot_debug_turns
                       WHERE repository=? AND julianday(occurred_at) BETWEEN julianday(?) - (30.0 / 86400.0) AND julianday(?) + (30.0 / 86400.0)
                       LIMIT 1""",
                    (item.get("repository"), item.get("compressed_at"), item.get("compressed_at")),
                ).fetchone()
                if correlated:
                    continue
            proxy_groups.setdefault(str(item.get("session_id") or f"proxy-{item.get('id')}"), []).append(item)
        for session_id, rows in proxy_groups.items():
            first = rows[0]
            turns = []
            primary_input = primary_output = primary_cached = primary_total = 0
            exact_cost = 0.0
            model_costs: dict[str, float] = {}
            for index, row in enumerate(rows):
                usage = _safe_json(row.get("actual_usage"))
                usage_details = usage.get("usage", usage) if isinstance(usage, dict) else {}
                input_tokens = int(usage_details.get("input_tokens") or usage_details.get("prompt_tokens") or row.get("tokens_after") or 0)
                output_tokens = int(usage_details.get("output_tokens") or usage_details.get("completion_tokens") or 0)
                cached_tokens = int((usage_details.get("input_tokens_details") or {}).get("cached_tokens") or usage_details.get("cached_tokens") or 0)
                observed_exact = bool(usage_details.get("input_tokens") or usage_details.get("prompt_tokens"))
                model = str(row.get("model_used") or "unknown")
                turn_cost = _actual_cost(input_tokens, output_tokens, cached_tokens, model)
                exact_cost += turn_cost
                model_costs[model] = round(model_costs.get(model, 0) + turn_cost, 8)
                try:
                    request_body = json.loads(row.get("request_body") or "{}")
                except (TypeError, ValueError, json.JSONDecodeError):
                    request_body = {}
                try:
                    optimized_body = json.loads(row.get("optimized_body") or "{}")
                except (TypeError, ValueError, json.JSONDecodeError):
                    optimized_body = {}
                turns.append({
                    "source_key": f"proxy:{row.get('id')}", "source_path": "TrimPy HTTPS proxy",
                    "parent_session_id": session_id, "child_session_id": session_id, "turn_index": index,
                    "request_kind": "primary", "occurred_at": row.get("compressed_at"), "model": model,
                    "debug_name": row.get("request_source") or "IDE Copilot chat",
                    "input_tokens": input_tokens, "output_tokens": output_tokens, "cached_tokens": cached_tokens,
                    "total_tokens": input_tokens + output_tokens, "ttft_ms": 0, "max_output_tokens": 0,
                    "user_message": row.get("original_text") or "", "cwd": row.get("cwd"),
                    "repository": row.get("repository"), "ide": "VS Code" if "vscode" in str(row.get("request_source")).lower() else "Rider" if "rider" in str(row.get("request_source")).lower() else "PyCharm",
                    "status": "reported" if observed_exact else "estimated",
                    "usage_source": "proxy_response" if observed_exact else "trimp_request_estimate",
                    "context": {"request_body": request_body, "optimized_body": optimized_body, "debug_log": row.get("debug_log_excerpt") or ""},
                    "trace": {"request_source": row.get("request_source"), "compression_method": row.get("compression_method"), "compression_grade": row.get("compression_grade")},
                    "exact_cost_estimate": turn_cost, "uncached_input_tokens": max(input_tokens - cached_tokens, 0),
                    "pricing_per_million": _pricing_for(model),
                })
                primary_input += input_tokens
                primary_output += output_tokens
                primary_cached += cached_tokens
                primary_total += input_tokens + output_tokens
            before = sum(int(row.get("tokens_before") or 0) for row in rows)
            after = sum(int(row.get("tokens_after") or 0) for row in rows)
            saved = before - after
            model = turns[0]["model"] if turns else "unknown"
            output.append({
                "session_id": session_id, "started_at": first.get("compressed_at"), "ended_at": rows[-1].get("compressed_at"),
                "cwd": first.get("cwd"), "repository": first.get("repository"), "ide": turns[0]["ide"] if turns else "JetBrains",
                "request_count": len(turns), "model_turns": len(turns), "primary_usage": {"input_tokens": primary_input, "cached_tokens": primary_cached, "output_tokens": primary_output, "total_tokens": primary_total},
                "all_usage": {"input_tokens": primary_input, "cached_tokens": primary_cached, "output_tokens": primary_output, "total_tokens": primary_total},
                "exact_cost_estimate": round(exact_cost, 8), "primary_cost_estimate": round(exact_cost, 8), "model_costs": model_costs,
                "usage_source": "ide_proxy_response" if any(turn["usage_source"] == "proxy_response" for turn in turns) else "trimp_proxy_estimate",
                "pricing_basis": "Exact usage from proxy response when available; otherwise TrimPy sent-volume estimate. GitHub Enterprise billing may differ",
                "trimpy": {"requests": len(rows), "tokens_before": before, "tokens_after": after, "tokens_saved": saved, "savings_pct": round(saved / before * 100, 2) if before else 0, "estimated_cost_saved": _dollars_saved(saved, model)},
                "turns": turns,
            })
        output.sort(key=lambda item: item.get("ended_at") or "", reverse=True)
    return output[: max(1, min(limit, 200))]


@app.get("/api/copilot/summary")
async def copilot_summary(range: str = "day"):
    """Token-optimizer metrics sourced from real Copilot proxy compression events."""
    threshold = _threshold_for_range(range)
    agent_usage = _agent_usage_summary(threshold)
    with db() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS requests,
                      COUNT(DISTINCT session_id) AS conversations,
                      COALESCE(SUM(tokens_before), 0) AS tokens_before,
                      COALESCE(SUM(tokens_after), 0) AS tokens_after,
                      COALESCE(SUM(tokens_before - tokens_after), 0) AS tokens_saved,
                      AVG(CASE WHEN tokens_before > 0
                          THEN 100.0 * (tokens_before - tokens_after) / tokens_before
                          ELSE 0 END) AS avg_request_savings_pct,
                      MAX(compressed_at) AS last_seen
               FROM compressions
               WHERE source='byok' AND compressed_at >= ?""",
            (threshold,),
        ).fetchone()
        model_rows = conn.execute(
            """SELECT COALESCE(model_used, 'unknown') AS model,
                      COUNT(*) AS requests,
                      COALESCE(SUM(tokens_after), 0) AS tokens_after,
                      COALESCE(SUM(tokens_before - tokens_after), 0) AS tokens_saved
               FROM compressions
               WHERE source='byok' AND compressed_at >= ?
               GROUP BY COALESCE(model_used, 'unknown')
               ORDER BY tokens_saved DESC""",
            (threshold,),
        ).fetchall()
        repo_rows = conn.execute(
            """SELECT COALESCE(s.repository, 'unknown') AS repository,
                      COUNT(*) AS requests,
                      COALESCE(SUM(c.tokens_before), 0) AS tokens_before,
                      COALESCE(SUM(c.tokens_after), 0) AS tokens_after,
                      COALESCE(SUM(c.tokens_before - c.tokens_after), 0) AS tokens_saved
               FROM compressions c
               LEFT JOIN sessions s ON s.id = c.session_id
               WHERE c.source='byok' AND c.compressed_at >= ?
               GROUP BY COALESCE(s.repository, 'unknown')
               ORDER BY tokens_saved DESC
               LIMIT 8""",
            (threshold,),
        ).fetchall()
        usage_rows = conn.execute(
            """SELECT actual_usage FROM compressions
               WHERE source='byok' AND compressed_at >= ?
                 AND actual_usage IS NOT NULL AND actual_usage != ''""",
            (threshold,),
        ).fetchall()

    tokens_before = int(row["tokens_before"] or 0)
    tokens_after = int(row["tokens_after"] or 0)
    tokens_saved = int(row["tokens_saved"] or 0)
    model_mix = [dict(r) | {"dollars_saved": _dollars_saved(int(r["tokens_saved"] or 0), r["model"])} for r in model_rows]
    total_dollars = round(sum(m["dollars_saved"] for m in model_mix), 6)
    actual_input = actual_output = actual_cached = actual_total = 0
    for usage_row in usage_rows:
        try:
            usage = json.loads(usage_row["actual_usage"] or "{}")
            details = usage.get("usage", usage)
            actual_input += int(details.get("input_tokens", 0) or 0)
            actual_output += int(details.get("output_tokens", 0) or 0)
            actual_cached += int((details.get("input_tokens_details") or {}).get("cached_tokens", 0) or 0)
            actual_total += int(details.get("total_tokens", 0) or 0)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    proxy_actual_input = actual_input
    proxy_actual_output = actual_output
    proxy_actual_cached = actual_cached
    proxy_actual_total = actual_total
    # GitHub's local agent shutdown record is the authoritative fallback when
    # the upstream response did not expose a usage object to the proxy.
    if not actual_input and agent_usage["input_tokens"]:
        actual_input = agent_usage["input_tokens"]
    if not actual_output and agent_usage["output_tokens"]:
        actual_output = agent_usage["output_tokens"]
    if not actual_cached and agent_usage["cached_input_tokens"]:
        actual_cached = agent_usage["cached_input_tokens"]
    if not actual_total and agent_usage["total_tokens"]:
        actual_total = agent_usage["total_tokens"]
    return {
        "range": range,
        "requests": int(row["requests"] or 0),
        "conversations": int(row["conversations"] or 0),
        "tokens_before": tokens_before,
        "tokens_after": tokens_after,
        "tokens_saved": tokens_saved,
        "savings_pct": round(tokens_saved / tokens_before * 100.0, 2) if tokens_before else 0.0,
        "avg_request_savings_pct": round(float(row["avg_request_savings_pct"] or 0), 2),
        "dollars_saved": total_dollars,
        "actual_input_tokens": actual_input,
        "actual_output_tokens": actual_output,
        "actual_cached_input_tokens": actual_cached,
        "actual_total_tokens": actual_total,
        "proxy_actual_input_tokens": proxy_actual_input,
        "proxy_actual_output_tokens": proxy_actual_output,
        "proxy_actual_cached_input_tokens": proxy_actual_cached,
        "proxy_actual_total_tokens": proxy_actual_total,
        "agent_log_input_tokens": agent_usage["input_tokens"],
        "agent_log_output_tokens": agent_usage["output_tokens"],
        "agent_log_cached_input_tokens": agent_usage["cached_input_tokens"],
        "agent_log_total_tokens": agent_usage["total_tokens"],
        "agent_log_requests": agent_usage["requests"],
        "agent_log_model_turns": agent_usage["model_turns"],
        "agent_log_tool_calls": agent_usage["tool_calls"],
        "agent_log_errors": agent_usage["errors"],
        "agent_log_compaction_tokens": agent_usage["compaction_tokens"],
        "agent_log_total_nano_aiu": agent_usage["total_nano_aiu"],
        "agent_log_sessions": agent_usage["sessions"],
        "agent_log_last_seen": agent_usage["last_seen"],
        "agent_log_models": agent_usage["models"],
        "actual_usage_source": "proxy_response" if proxy_actual_input else agent_usage["source"],
        "measurement_note": "actual_* values come from GitHub's proxy response or local agent logs; tokens_before/after and dollars_saved are TrimP estimates",
        "last_seen": row["last_seen"],
        "model_mix": model_mix,
        "repositories": [dict(r) for r in repo_rows],
    }


@app.get("/api/copilot/conversations")
async def copilot_conversations(range: str = "day", limit: int = 100):
    """Detailed Copilot proxy conversations/requests with prompt and compression metadata."""
    threshold = _threshold_for_range(range)
    with db() as conn:
        rows = conn.execute(
            """SELECT c.id,
                      c.session_id,
                      c.turn_id,
                      c.compressed_at,
                      c.model_used,
                      c.tokens_before,
                      c.tokens_after,
                      (c.tokens_before - c.tokens_after) AS tokens_saved,
                      ROUND(100.0 * (c.tokens_before - c.tokens_after) / NULLIF(c.tokens_before, 0), 2) AS savings_pct,
                      c.original_text,
                      c.compressed_text,
                      c.algorithm_details,
                      c.request_body,
                      c.optimized_body,
                      c.response_body,
                      c.request_source,
                      c.debug_log_excerpt,
                      c.actual_usage,
                      c.compression_score,
                      c.compression_grade,
                      c.recommendations,
                      c.compression_method,
                      s.label,
                      s.cwd,
                      s.repository,
                      s.branch,
                      s.status,
                      t.assistant_response
               FROM compressions c
               LEFT JOIN sessions s ON s.id = c.session_id
               LEFT JOIN turns t ON t.id = c.turn_id
               WHERE c.source='byok' AND c.compressed_at >= ?
               ORDER BY c.compressed_at DESC
               LIMIT ?""",
            (threshold, limit),
        ).fetchall()

    conversations = []
    for row in rows:
        item = dict(row)
        saved = int(item.get("tokens_saved") or 0)
        model = item.get("model_used")
        details = _safe_json(item.get("algorithm_details"))
        changes = details.get("changes") if isinstance(details.get("changes"), list) else []
        item["dollars_saved"] = _dollars_saved(saved, model)
        item["change_count"] = len(changes)
        item["changes"] = changes[:8]
        item["prompt_preview"] = " ".join((item.get("original_text") or "").split())[:240]
        item["optimized_preview"] = " ".join((item.get("compressed_text") or "").split())[:240]
        item["assistant_preview"] = " ".join((item.get("assistant_response") or "").split())[:240]
        item["request_source"] = item.get("request_source") or "unknown"
        item["actual_usage"] = _safe_json(item.get("actual_usage"))
        raw_recommendations = item.get("recommendations")
        try:
            parsed_recommendations = json.loads(raw_recommendations or "[]")
        except Exception:
            parsed_recommendations = []
        item["recommendations"] = parsed_recommendations if isinstance(parsed_recommendations, list) else []
        item["request_body_preview"] = (item.get("request_body") or "")[:4000]
        item["optimized_body_preview"] = (item.get("optimized_body") or "")[:4000]
        item["response_body_preview"] = (item.get("response_body") or "")[:4000]
        item["debug_log_preview"] = (item.get("debug_log_excerpt") or "")[-4000:]
        conversations.append(item)
    return conversations


@app.get("/api/copilot/daily")
async def copilot_daily(days: int = 14, repository: str = ""):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with db() as conn:
        query = """SELECT date(c.compressed_at) AS day,
                      COUNT(*) AS requests,
                      COALESCE(SUM(c.tokens_before), 0) AS tokens_before,
                      COALESCE(SUM(c.tokens_after), 0) AS tokens_after,
                      COALESCE(SUM(c.tokens_before - c.tokens_after), 0) AS tokens_saved
               FROM compressions c LEFT JOIN sessions s ON s.id=c.session_id
               WHERE c.source='byok' AND c.compressed_at >= ?"""
        params = [cutoff]
        if repository:
            query += " AND COALESCE(s.repository, 'unknown') = ?"
            params.append(repository)
        query += " GROUP BY date(c.compressed_at) ORDER BY day"
        rows = conn.execute(query, params).fetchall()
    output = []
    for row in rows:
        item = dict(row)
        item["savings_pct"] = round((item["tokens_saved"] / item["tokens_before"]) * 100.0, 2) if item["tokens_before"] else 0
        item["dollars_saved"] = _dollars_saved(int(item["tokens_saved"] or 0))
        output.append(item)
    return output


@app.get("/api/copilot/timeseries")
async def copilot_timeseries(range: str = "day", granularity: str = "auto", repository: str = ""):
    """Aggregate real BYOK events for the dashboard's selected time window and bucket."""
    valid_granularities = {"auto", "minute", "hour", "day", "week", "month", "year"}
    selected_granularity = granularity if granularity in valid_granularities else "auto"
    if selected_granularity == "auto":
        selected_granularity = _auto_granularity(range)
    threshold = _threshold_for_range(range)
    with db() as conn:
        query = """SELECT c.compressed_at, c.model_used, c.tokens_before, c.tokens_after,
                          COALESCE(s.repository, 'unknown') AS repository
                   FROM compressions c
                   LEFT JOIN sessions s ON s.id = c.session_id
                   WHERE c.source='byok' AND c.compressed_at >= ?"""
        params: list[str] = [threshold]
        if repository:
            query += " AND COALESCE(s.repository, 'unknown') = ?"
            params.append(repository)
        query += " ORDER BY c.compressed_at"
        rows = conn.execute(query, params).fetchall()

    start = None if range == "all" else _parse_event_time(threshold)
    buckets: dict[datetime, dict] = {}
    for row in rows:
        timestamp = _parse_event_time(row["compressed_at"])
        if not timestamp or (start and timestamp < start):
            continue
        bucket = _bucket_time(timestamp, selected_granularity)
        item = buckets.setdefault(bucket, {
            "bucket": bucket.isoformat(),
            "label": _bucket_label(bucket, selected_granularity),
            "requests": 0,
            "tokens_before": 0,
            "tokens_after": 0,
            "tokens_saved": 0,
            "dollars_saved": 0.0,
        })
        before = int(row["tokens_before"] or 0)
        after = int(row["tokens_after"] or 0)
        saved = before - after
        item["requests"] += 1
        item["tokens_before"] += before
        item["tokens_after"] += after
        item["tokens_saved"] += saved
        item["dollars_saved"] += _dollars_saved(saved, row["model_used"])

    output = []
    for item in sorted(buckets.values(), key=lambda value: value["bucket"]):
        item["savings_pct"] = round(item["tokens_saved"] / item["tokens_before"] * 100.0, 2) if item["tokens_before"] else 0
        item["dollars_saved"] = round(item["dollars_saved"], 6)
        output.append(item)
    return {"range": range, "granularity": selected_granularity, "repository": repository, "points": output}


@app.get("/api/copilot/activity")
async def copilot_activity(range: str = "day", limit: int = 12):
    """Newest real trim events for the live activity feed."""
    threshold = _threshold_for_range(range)
    with db() as conn:
        rows = conn.execute(
            """SELECT c.id, c.compressed_at, c.model_used, c.request_source,
                      c.tokens_before, c.tokens_after,
                      (c.tokens_before - c.tokens_after) AS tokens_saved,
                      c.compression_method, c.algorithm_details,
                      COALESCE(s.repository, 'unknown repo') AS repository
               FROM compressions c LEFT JOIN sessions s ON s.id=c.session_id
               WHERE c.source='byok' AND c.compressed_at >= ?
               ORDER BY c.compressed_at DESC LIMIT ?""",
            (threshold, limit),
        ).fetchall()
    output = []
    for row in rows:
        item = dict(row)
        details = _safe_json(item.get("algorithm_details"))
        changes = details.get("changes") if isinstance(details.get("changes"), list) else []
        item["algorithm"] = (changes[0].get("method") if changes and isinstance(changes[0], dict) else item.get("compression_method") or "no-op")
        output.append(item)
    return output


@app.get("/api/session/current")
async def current_session():
    sid = get_or_create_session()
    with db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not row:
        return {"error": "no session"}
    return dict(row)


@app.get("/api/sessions")
async def list_sessions(limit: int = 30):
    return get_recent_sessions(limit)


@app.get("/api/session/{session_id}/quality")
async def session_quality(session_id: str):
    report = score_session(session_id)
    return report.to_dict()


@app.get("/api/session/{session_id}/turns")
async def session_turns(session_id: str):
    """Get conversation turns for a session."""
    with db() as conn:
        rows = conn.execute(
            """SELECT turn_index, user_message, assistant_response, 
                      tokens_in, tokens_out, model, timestamp
               FROM turns 
               WHERE session_id=?
               ORDER BY turn_index ASC""",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get full session details with turns."""
    with db() as conn:
        # Get session
        session_row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not session_row:
            return {"error": "session not found"}
        
        session = dict(session_row)
        
        # Get turns
        turn_rows = conn.execute(
            """SELECT turn_index, user_message, assistant_response, 
                      tokens_in, tokens_out, model, timestamp
               FROM turns 
               WHERE session_id=?
               ORDER BY turn_index ASC""",
            (session_id,),
        ).fetchall()
        session["turns"] = [dict(r) for r in turn_rows]
        
        # Get compressions
        comp_rows = conn.execute(
            """SELECT compressor, tokens_before, tokens_after, compressed_at
               FROM compressions 
               WHERE session_id=?
               ORDER BY compressed_at DESC""",
            (session_id,),
        ).fetchall()
        session["compressions"] = [dict(r) for r in comp_rows]
        
    return session


@app.get("/api/session/{session_id}/compressions")
async def session_compressions(session_id: str):
    with db() as conn:
        rows = conn.execute(
            """SELECT compressor, COUNT(*) as events,
                      SUM(tokens_before) as tokens_before,
                      SUM(tokens_after) as tokens_after,
                      SUM(tokens_before - tokens_after) as saved
               FROM compressions WHERE session_id=?
               GROUP BY compressor ORDER BY saved DESC""",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/session/{session_id}/compressions/detailed")
async def session_compressions_detailed(session_id: str, compressor: str = None):
    """Get individual compression events, optionally filtered by compressor."""
    with db() as conn:
        if compressor:
            rows = conn.execute(
                """SELECT compressor, tokens_before, tokens_after, compressed_at
                   FROM compressions 
                   WHERE session_id=? AND compressor=?
                   ORDER BY compressed_at DESC
                   LIMIT 100""",
                (session_id, compressor),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT compressor, tokens_before, tokens_after, compressed_at
                   FROM compressions 
                   WHERE session_id=?
                   ORDER BY compressed_at DESC
                   LIMIT 100""",
                (session_id,),
            ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/compressions/recent")
async def recent_compressions(session_id: str = None, range: str = "hour", limit: int = 50):
    """
    Get recent compressions with time range filter.
    range: 'hour', 'day', 'week', 'month', or 'all'
    """
    now = datetime.now(timezone.utc)
    if range == "hour":
        threshold = (now - timedelta(hours=1)).isoformat()
    elif range == "day":
        threshold = (now - timedelta(days=1)).isoformat()
    elif range == "week":
        threshold = (now - timedelta(weeks=1)).isoformat()
    elif range == "month":
        threshold = (now - timedelta(days=30)).isoformat()
    else:  # all
        threshold = "2000-01-01T00:00:00"

    with db() as conn:
        if session_id:
            rows = conn.execute(
                """SELECT
                       c.id, c.session_id, c.compressor,
                       c.tokens_before, c.tokens_after, c.compressed_at,
                       COALESCE(c.model_used, '') as model_used,
                       COALESCE(c.original_text, '') as original_text,
                       COALESCE(c.compressed_text, '') as compressed_text,
                       COALESCE(c.compression_method, c.compressor) as compression_method,
                       (c.tokens_before - c.tokens_after) as tokens_saved,
                       ROUND(100.0*(c.tokens_before-c.tokens_after)/NULLIF(c.tokens_before,0),1) as savings_pct
                   FROM compressions c
                   WHERE c.session_id=? AND c.compressed_at >= ?
                   ORDER BY c.compressed_at DESC
                   LIMIT ?""",
                (session_id, threshold, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT
                       c.id, c.session_id, c.compressor,
                       c.tokens_before, c.tokens_after, c.compressed_at,
                       COALESCE(c.model_used, '') as model_used,
                       COALESCE(c.original_text, '') as original_text,
                       COALESCE(c.compressed_text, '') as compressed_text,
                       COALESCE(c.compression_method, c.compressor) as compression_method,
                       (c.tokens_before - c.tokens_after) as tokens_saved,
                       ROUND(100.0*(c.tokens_before-c.tokens_after)/NULLIF(c.tokens_before,0),1) as savings_pct
                   FROM compressions c
                   WHERE c.compressed_at >= ?
                   ORDER BY c.compressed_at DESC
                   LIMIT ?""",
                (threshold, limit),
            ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/models/stats")
async def model_stats(range: str = "all"):
    """Get statistics by model."""
    now = datetime.now(timezone.utc)
    if range == "hour":
        threshold = (now - timedelta(hours=1)).isoformat()
    elif range == "day":
        threshold = (now - timedelta(days=1)).isoformat()
    elif range == "week":
        threshold = (now - timedelta(weeks=1)).isoformat()
    elif range == "month":
        threshold = (now - timedelta(days=30)).isoformat()
    else:
        threshold = "2000-01-01T00:00:00"
    
    with db() as conn:
        rows = conn.execute(
            """SELECT 
                   model_used,
                   COUNT(*) as compressions,
                   SUM(tokens_before) as tokens_before,
                   SUM(tokens_after) as tokens_after,
                   SUM(tokens_before - tokens_after) as tokens_saved,
                   ROUND(100.0 * SUM(tokens_before - tokens_after) / NULLIF(SUM(tokens_before), 0), 1) as savings_pct
               FROM compressions 
               WHERE compressed_at >= ?
               GROUP BY model_used
               ORDER BY tokens_saved DESC""",
            (threshold,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/activity/feed")
async def activity_feed(limit: int = 20):
    """Get real-time activity feed."""
    with db() as conn:
        rows = conn.execute(
            """SELECT 
                   c.compressor,
                   c.tokens_before,
                   c.tokens_after,
                   c.compressed_at,
                   c.model_used,
                   c.original_text,
                   c.compressed_text,
                   (c.tokens_before - c.tokens_after) as tokens_saved,
                   ROUND(100.0 * (c.tokens_before - c.tokens_after) / NULLIF(c.tokens_before, 0), 1) as savings_pct,
                   s.repository,
                   s.branch
               FROM compressions c
               LEFT JOIN sessions s ON c.session_id = s.id
               ORDER BY c.compressed_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/compression/methods")
async def compression_methods():
    """Get all available compression methods with descriptions."""
    methods = [
        {"id": "bash", "name": "Bash Output", "description": "Compresses command output, logs, and terminal text", "icon": "terminal", "color": "#01A982"},
        {"id": "search", "name": "Search Results", "description": "Compresses grep/find results to top hits", "icon": "search", "color": "#425563"},
        {"id": "json", "name": "JSON/Tables", "description": "Minimizes JSON and tabular data", "icon": "code", "color": "#5FCBEB"},
        {"id": "skeleton", "name": "Code Skeleton", "description": "Extracts code structure (signatures, imports)", "icon": "file-code", "color": "#7630EA"},
        {"id": "stopword", "name": "Stop Words", "description": "Removes filler words from text", "icon": "filter", "color": "#FF8300"},
        {"id": "prompt", "name": "Prompt Compression", "description": "Compresses system prompts and instructions", "icon": "message-square", "color": "#FFB81C"},
        {"id": "code", "name": "Code Context", "description": "U-shape recency for code files (40-75% savings)", "icon": "code", "color": "#01A982"},
        {"id": "conversation", "name": "Conversation", "description": "3-tier chat compression (50-70% savings)", "icon": "message-circle", "color": "#425563"},
        {"id": "log", "name": "Log Extractor", "description": "Extracts errors from logs (50-80% savings)", "icon": "alert-circle", "color": "#FF8300"},
        {"id": "image", "name": "Image Description", "description": "Templates for image descriptions (85-92% savings)", "icon": "image", "color": "#5FCBEB"},
        {"id": "architecture", "name": "Architecture", "description": "Component graph extraction (60-80% savings)", "icon": "box", "color": "#7630EA"},
        {"id": "semantic", "name": "Semantic Chunker", "description": "RAG-optimized context (50-85% savings)", "icon": "layers", "color": "#01A982"},
        {"id": "lingua", "name": "LLM Lingua", "description": "Self-information word pruning (30-60% savings)", "icon": "minimize-2", "color": "#425563"},
        {"id": "mcp", "name": "MCP Tools", "description": "Tool schema compression (60-90% savings)", "icon": "tool", "color": "#5FCBEB"},
        {"id": "universal", "name": "Universal", "description": "Auto-detects and routes to best algorithm", "icon": "zap", "color": "#FFB81C"},
    ]
    return methods


@app.get("/api/session/{session_id}/loops")
async def session_loops(session_id: str):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM loop_detections WHERE session_id=? ORDER BY detected_at DESC",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/session/{session_id}/archives")
async def session_archives(session_id: str):
    with db() as conn:
        rows = conn.execute(
            "SELECT archive_key, tool_name, char_count, summary, archived_at FROM archives WHERE session_id=?",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/session/{session_id}/checkpoints")
async def session_checkpoints(session_id: str):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM checkpoints WHERE session_id=? ORDER BY checkpoint_num DESC",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/savings")
async def global_savings():
    with db() as conn:
        row = conn.execute("SELECT SUM(tokens_saved) as total FROM sessions").fetchone()
    total = row["total"] or 0
    pricing = {
        "haiku": float(get_config("pricing.haiku_per_1m", "0.80")),
        "sonnet": float(get_config("pricing.sonnet_per_1m", "3.00")),
        "opus": float(get_config("pricing.opus_per_1m", "15.00")),
        "gpt4": float(get_config("pricing.gpt4_per_1m", "10.00")),
    }
    return {
        "tokens_saved": total,
        "savings": {k: round((total / 1_000_000) * v, 6) for k, v in pricing.items()},
    }


@app.get("/api/trends/daily")
async def daily_trends(days: int = 30):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with db() as conn:
        rows = conn.execute(
            """SELECT date(started_at) as day,
                      COUNT(*) as sessions,
                      SUM(tokens_saved) as saved,
                      AVG(CASE quality_grade
                          WHEN 'S' THEN 1.0 WHEN 'A' THEN 0.85 WHEN 'B' THEN 0.70
                          WHEN 'C' THEN 0.55 WHEN 'D' THEN 0.35 ELSE 0.0 END) as avg_score
               FROM sessions WHERE started_at >= ?
               GROUP BY day ORDER BY day""",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/compression/patterns")
async def compression_patterns():
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM compression_patterns ORDER BY tokens_saved_total DESC LIMIT 50"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/repositories")
async def list_repositories():
    """List all repositories with aggregated stats."""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT 
                COALESCE(s.repository, 'unknown') AS repository,
                COUNT(DISTINCT s.branch) as branch_count,
                COUNT(DISTINCT c.session_id) as conversation_count,
                COUNT(*) as request_count,
                COALESCE(SUM(c.tokens_before), 0) as tokens_before,
                COALESCE(SUM(c.tokens_after), 0) as tokens_after,
                COALESCE(SUM(c.tokens_before - c.tokens_after), 0) as tokens_saved,
                ROUND(100.0 * SUM(c.tokens_before - c.tokens_after) / NULLIF(SUM(c.tokens_before), 0), 2) as compression_rate,
                AVG(c.compression_score) as avg_score,
                MAX(c.compressed_at) as last_session,
                GROUP_CONCAT(DISTINCT c.model_used) as models
            FROM compressions c
            LEFT JOIN sessions s ON s.id = c.session_id
            WHERE c.source='byok'
            GROUP BY COALESCE(s.repository, 'unknown')
            ORDER BY last_session DESC
            """
        ).fetchall()
        
    repositories = []
    for row in rows:
        repo_dict = dict(row)
        
        score = repo_dict.get("avg_score") or 0
        if score >= 80: avg_grade = "A"
        elif score >= 60: avg_grade = "B"
        elif score >= 35: avg_grade = "C"
        elif score > 0: avg_grade = "D"
        else: avg_grade = "F"
        repo_dict["avg_grade"] = avg_grade
        repo_dict["dollars_saved"] = _dollars_saved(int(repo_dict.get("tokens_saved") or 0))
        repo_dict["models"] = [m for m in (repo_dict.get("models") or "").split(",") if m]
        repo_dict["total_tokens"] = (repo_dict.get("tokens_before") or 0)
        
        # Get branches for this repo
        with db() as conn2:
            branches = conn2.execute(
                """
                SELECT COALESCE(s.branch, 'unknown') as name,
                       COUNT(*) as requests,
                       COALESCE(SUM(c.tokens_before - c.tokens_after), 0) as tokens_saved
                FROM compressions c
                LEFT JOIN sessions s ON s.id = c.session_id
                WHERE COALESCE(s.repository, 'unknown') = ?
                GROUP BY COALESCE(s.branch, 'unknown')
                ORDER BY tokens_saved DESC
                """,
                (repo_dict['repository'],)
            ).fetchall()
        repo_dict['branches'] = [dict(b) for b in branches]
        repositories.append(repo_dict)
    
    return {"repositories": repositories}


@app.get("/api/config")
async def get_all_config():
    with db() as conn:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
    return {r["key"]: r["value"] for r in rows}


@app.put("/api/config/{key}")
async def set_config_api(key: str, body: dict):
    from TrimP.db import prune_expired_logs, set_config
    value = str(body.get("value", ""))
    if key == "logs.retention_months":
        try:
            value = str(max(0, min(120, int(value))))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Retention must be a whole number of months.")
    set_config(key, value)
    result = {"ok": True, "key": key, "value": value}
    if key == "logs.retention_months":
        result["pruned"] = prune_expired_logs()
    return result


@app.post("/api/test/trim")
async def test_trim(body: dict):
    """Measure a prompt with TrimP on or off without forwarding it upstream."""
    message = str(body.get("message") or "").strip()
    if not message:
        return {"ok": False, "error": "Enter a test message first."}
    requested_enabled = body.get("enabled")
    if requested_enabled is None:
        enabled = str(get_config("compression.enabled", "true")).lower() in {"1", "true", "yes", "on"}
    else:
        enabled = bool(requested_enabled)
    request_body = {
        "model": body.get("model") or "gpt-5-mini",
        "messages": [{"role": "user", "content": message}],
    }
    optimized, stats = test_optimizer.optimize_body(request_body, enabled=enabled)
    optimized_message = str(optimized.get("messages", [{}])[-1].get("content") or "")
    stopwords = {"about", "after", "before", "could", "every", "first", "from", "keep", "please", "same", "should", "that", "their", "there", "these", "this", "while", "with", "would"}
    before_words = {word for word in re.findall(r"[a-zA-Z]{5,}", message.lower()) if word not in stopwords}
    after_words = {word for word in re.findall(r"[a-zA-Z]{5,}", optimized_message.lower()) if word not in stopwords}
    preserved = len(before_words & after_words) / len(before_words) if before_words else 1.0
    reduction = stats.savings_pct / 100.0
    quality_score = max(0.0, min(1.0, (preserved * 0.55) + (min(1.0, reduction * 2) * 0.45)))
    grade = "A" if quality_score >= .9 else "B" if quality_score >= .78 else "C" if quality_score >= .62 else "D"
    return {
        "ok": True,
        "enabled": enabled,
        "repository": str(body.get("repository") or "unassigned"),
        "test_case": str(body.get("test_case") or "custom"),
        "model": request_body["model"],
        "message": message,
        "optimized_message": optimized_message,
        "stats": stats.as_dict(),
        "quality": {
            "score": round(quality_score * 100, 1),
            "grade": grade,
            "context_preservation": round(preserved * 100, 1),
            "conciseness": round((1 - reduction) * 100, 1),
            "compression_effectiveness": round(reduction * 100, 1),
            "structure_preserved": True,
            "note": "Preflight signals from the local request transformation; model answer quality requires an upstream A/B run.",
        },
        "calculation": {
            "estimator": "len(serialized request) / 4, minimum 1",
            "tokens_saved": "tokens_before - tokens_after",
            "reduction_pct": "tokens_saved / tokens_before * 100",
            "upstream_call": False,
        },
    }


@app.post("/api/database/clear")
async def clear_database(body: dict):
    """Delete telemetry while preserving TrimP configuration."""
    if str(body.get("confirmation", "")).strip() != "CLEAR DB":
        return {"ok": False, "error": "Type CLEAR DB to confirm."}
    tables = (
        "turns", "compressions", "sessions", "checkpoints", "quality_scores",
        "archives", "session_files", "model_routing", "token_budgets",
        "compression_patterns", "savings", "memory_audits", "loop_detections",
        "activity_modes", "copilot_agent_usage",
    )
    with db() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        for table in tables:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
        conn.execute("VACUUM")
        conn.execute("PRAGMA foreign_keys=ON")
    return {"ok": True, "cleared_tables": list(tables), "message": "Database telemetry cleared."}


# ──────────────────────── WebSocket live feed ────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(data)
            except Exception:
                self.active.remove(ws)


manager = ConnectionManager()


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await manager.connect(websocket)
    # Send initial state on connect
    try:
        with db() as conn:
            rows = conn.execute(
                """SELECT c.compressor, c.tokens_before, c.tokens_after,
                          c.compressed_at, c.session_id,
                          (c.tokens_before - c.tokens_after) as tokens_saved
                   FROM compressions c
                   ORDER BY c.compressed_at DESC LIMIT 30"""
            ).fetchall()
        await websocket.send_json({
            "type": "init",
            "compressions": [dict(r) for r in rows],
        })
    except Exception:
        pass
    try:
        import asyncio
        while True:
            await asyncio.sleep(2)
            # Push aggregate stats every 2s so the page stays live
            try:
                with db() as conn:
                    stats = conn.execute(
                        """SELECT COUNT(*) as total,
                                  COALESCE(SUM(tokens_before - tokens_after), 0) as saved
                           FROM compressions"""
                    ).fetchone()
                    latest = conn.execute(
                        """SELECT compressor, tokens_before, tokens_after, compressed_at,
                                  session_id,
                                  (tokens_before - tokens_after) as tokens_saved
                           FROM compressions ORDER BY compressed_at DESC LIMIT 1"""
                    ).fetchone()
                await websocket.send_json({
                    "type": "stats",
                    "total_compressions": stats["total"] if stats else 0,
                    "total_saved": stats["saved"] if stats else 0,
                    "latest": dict(latest) if latest else None,
                })
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ──────────────────────── SPA static files ───────────────────────────────

@app.get("/")
async def root():
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return HTMLResponse(_placeholder_html())


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")


def _placeholder_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>TrimP Dashboard</title>
  <style>
    body { font-family: monospace; background: #0d1117; color: #e6edf3; padding: 2rem; }
    h1 { color: #58a6ff; }
    a { color: #79c0ff; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 1rem; margin: 1rem 0; }
    .grade { font-size: 3rem; color: #3fb950; font-weight: bold; }
  </style>
</head>
<body>
  <h1>🔧 TrimP — Token Optimizer Dashboard</h1>
  <p>API is running. Build the React frontend with <code>TrimP dashboard --build</code></p>
  <div class="card">
    <h2>Quick Links</h2>
    <ul>
      <li><a href="/api/status">API Status</a></li>
      <li><a href="/api/session/current">Current Session</a></li>
      <li><a href="/api/savings">Savings Summary</a></li>
      <li><a href="/api/trends/daily">Daily Trends</a></li>
      <li><a href="/docs">API Docs (Swagger)</a></li>
    </ul>
  </div>
</body>
</html>"""


def launch(port: int = 7432, open_browser: bool = True, reload: bool = False) -> None:
    if open_browser:
        import threading
        def _open():
            import time; time.sleep(1.5)
            webbrowser.open(f"http://localhost:{port}")
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(
        "TrimP.dashboard.server:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        log_level="warning",
    )
