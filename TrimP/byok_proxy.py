"""
BYOK (Bring Your Own Key) proxy for GitHub Copilot CLI integration.

This module provides an OpenAI-compatible API endpoint that:
1. Accepts requests from Copilot CLI (configured for BYOK mode)
2. Compresses the context using TrimP algorithms
3. Forwards compressed requests to GitHub Copilot API
4. Returns responses back to Copilot CLI
"""

import json
import httpx
import logging
import sqlite3
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from TrimP.chat_optimizer import ChatPayloadOptimizer
from TrimP.copilot_auth import (
    build_copilot_upstream_url,
    copilot_request_headers,
    get_copilot_api_token,
)
from TrimP.db import DB_PATH as SHARED_DB_PATH, get_connection
from TrimP.model_utils import MODEL_ALIASES, normalize_copilot_model
from TrimP.secret_redaction import redact_secrets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")
optimizer = ChatPayloadOptimizer()

# Database path: keep BYOK stats in the same DB as dashboard/CLI/proxy.
DB_PATH = str(SHARED_DB_PATH)
CONTEXT_PATH = Path.home() / ".trimp" / "proxy_context.json"
COPILOT_LOG_DIR = Path.home() / ".copilot" / "logs"

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _detect_repo(cwd: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
        if out:
            return out.rstrip("/").split("/")[-1].replace(".git", "")
    except Exception:
        pass
    return Path(cwd).name if cwd else "unknown"


def _detect_branch(cwd: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
        return out or "unknown"
    except Exception:
        return "unknown"


def _workspace_context() -> dict[str, str]:
    env_cwd = os.environ.get("TRIMP_WORKSPACE_CWD", "").strip()
    if env_cwd:
        cwd = env_cwd
        return {"cwd": cwd, "repository": _detect_repo(cwd), "branch": _detect_branch(cwd)}
    try:
        payload = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
        cwd = str(payload.get("cwd") or "").strip()
        if cwd:
            return {
                "cwd": cwd,
                "repository": str(payload.get("repository") or _detect_repo(cwd)),
                "branch": str(payload.get("branch") or _detect_branch(cwd)),
            }
    except Exception:
        pass
    cwd = os.getcwd()
    return {"cwd": cwd, "repository": _detect_repo(cwd), "branch": _detect_branch(cwd)}


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        if "content" in content:
            return _message_text(content["content"])
        return ""
    if isinstance(content, list):
        parts = []
        for item in content:
            text = _message_text(item)
            if text:
                parts.append(text)
        return "\n".join(parts)
    return ""


def _extract_user_prompt(body: dict[str, Any]) -> str:
    messages = body.get("messages")
    if isinstance(messages, list):
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                text = _message_text(msg.get("content"))
                if text.strip():
                    return text.strip()
    input_value = body.get("input")
    if isinstance(input_value, str):
        return input_value.strip()
    if isinstance(input_value, list):
        for item in reversed(input_value):
            if isinstance(item, dict) and item.get("role") == "user":
                text = _message_text(item.get("content"))
                if text.strip():
                    return text.strip()
        return _message_text(input_value).strip()
    return ""


def _extract_assistant_text(result: dict[str, Any]) -> str:
    choices = result.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(msg, dict):
            return _message_text(msg.get("content")).strip()
    output = result.get("output")
    if isinstance(output, list):
        texts = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                texts.append(_message_text(content))
        return "\n".join(t for t in texts if t).strip()
    return ""


def _conversation_label(prompt: str) -> str:
    clean = " ".join((prompt or "").split())
    if not clean:
        return "Copilot request"
    return clean[:80] + ("..." if len(clean) > 80 else "")


def _json_dumps(value: Any, limit: int | None = None) -> str:
    try:
        text = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        text = str(value)
    if limit and len(text) > limit:
        return text[:limit] + f"... [truncated {len(text) - limit} chars]"
    return text


def _collect_debug_log_excerpt(lines: int = 120) -> str:
    try:
        files = sorted(
            COPILOT_LOG_DIR.glob("process-*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except Exception:
        return ""
    if not files:
        return ""
    selected = files[0]
    try:
        content = selected.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return ""
    useful = [
        (line[:700] + "..." if len(line) > 700 else line)
        for line in content[-lines:]
        if "base64," not in line
        and "data:image" not in line
        and any(
            needle in line.lower()
            for needle in (
                "custom provider",
                "completion request",
                "sending request",
                "compactionprocessor",
                "tokens",
                "model",
                "mcp",
                "context",
                "file",
                "workspace",
            )
        )
    ]
    excerpt = "\n".join(useful[-lines:])
    return f"{selected.name}\n{excerpt}" if excerpt else selected.name


def _score_compression(tokens_before: int, tokens_after: int, changes: list[dict[str, Any]]) -> tuple[float, str, list[str]]:
    saved = max(0, tokens_before - tokens_after)
    ratio = saved / tokens_before if tokens_before else 0.0
    changed_paths = len(changes)
    tool_savings = sum(
        int(c.get("tokens_saved") or 0)
        for c in changes
        if "tool" in str(c.get("method", "")).lower()
    )
    score = min(100.0, ratio * 100.0 + min(20, changed_paths * 1.5) + (10 if tool_savings > saved * 0.5 and saved else 0))
    if ratio >= 0.35:
        grade = "A"
    elif ratio >= 0.20:
        grade = "B"
    elif ratio >= 0.08:
        grade = "C"
    elif ratio > 0:
        grade = "D"
    else:
        grade = "F"
    tips: list[str] = []
    if ratio < 0.08:
        tips.append("Most of this request was protected prompt/history or already concise text; biggest gains need tool-output or file-context compression.")
    if changed_paths == 0:
        tips.append("No field crossed the compression threshold. Send large logs, command output, or file excerpts through tool/context fields to unlock savings.")
    if tokens_before > 30000 and ratio < 0.20:
        tips.append("Large request with low reduction: enable targeted summarization for old chat history and repeated file context.")
    if tool_savings:
        tips.append("Tool-output compression is working. Keep routing command outputs through TrimP wrapper/hooks.")
    if not tips:
        tips.append("Compression looks healthy for this request. Monitor answer quality before making it more aggressive.")
    return round(score, 2), grade, tips


def _usage_from_response(result: dict[str, Any]) -> dict[str, Any]:
    usage = {}
    if isinstance(result.get("usage"), dict):
        usage["usage"] = result["usage"]
    if isinstance(result.get("copilot_usage"), dict):
        usage["copilot_usage"] = result["copilot_usage"]
    return usage


def log_to_database(
    session_id: str,
    model: str,
    original_tokens: int,
    compressed_tokens: int,
    compression_ratio: float,
    algorithm_details: str | None = None,
    user_prompt: str | None = None,
    optimized_prompt: str | None = None,
    assistant_response: str | None = None,
    request_body: dict[str, Any] | None = None,
    optimized_body: dict[str, Any] | None = None,
    response_body: dict[str, Any] | None = None,
    actual_usage: dict[str, Any] | None = None,
    request_source: str = "copilot-cli-proxy",
    workspace_context: dict[str, str] | None = None,
    debug_log_excerpt: str | None = None,
    record_source: str = "byok",
):
    """Log compression stats to the database."""
    conn = None
    try:
        get_connection()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        context = dict(workspace_context or _workspace_context())
        cwd = str(context.get("cwd") or "").strip()
        context = {
            "cwd": cwd or os.getcwd(),
            "repository": str(context.get("repository") or _detect_repo(cwd)),
            "branch": str(context.get("branch") or _detect_branch(cwd)),
        }
        # Scrub likely secrets (API keys, tokens, passwords) before anything
        # else touches this data. Bodies/prompts/logs can contain whatever
        # the user pasted into chat or a tool ran, and this DB has no
        # encryption at rest, so this is the only line of defense against a
        # leaked secret sitting in plaintext in ~/.trimp/TrimP.db.
        user_prompt = redact_secrets(user_prompt) if user_prompt else user_prompt
        optimized_prompt = redact_secrets(optimized_prompt) if optimized_prompt else optimized_prompt
        assistant_response = redact_secrets(assistant_response) if assistant_response else assistant_response
        request_body = redact_secrets(request_body) if request_body else request_body
        optimized_body = redact_secrets(optimized_body) if optimized_body else optimized_body
        response_body = redact_secrets(response_body) if response_body else response_body

        now = _now_iso()
        saved = original_tokens - compressed_tokens
        label = _conversation_label(user_prompt or "")
        try:
            details = json.loads(algorithm_details) if algorithm_details else {}
        except Exception:
            details = {}
        changes = details.get("changes") if isinstance(details.get("changes"), list) else []
        score, grade, tips = _score_compression(original_tokens, compressed_tokens, changes)
        debug_excerpt = debug_log_excerpt if debug_log_excerpt is not None else _collect_debug_log_excerpt()
        debug_excerpt = redact_secrets(debug_excerpt) if debug_excerpt else debug_excerpt

        # Check if session exists
        cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
        if not cursor.fetchone():
            # Create new session
            cursor.execute("""
                INSERT INTO sessions (id, started_at, ended_at, cwd, repository, branch, model, status, label)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?)
            """, (
                session_id,
                now,
                now,
                context["cwd"],
                context["repository"],
                context["branch"],
                model,
                label,
            ))
        
        # Update token counts
        cursor.execute("""
            UPDATE sessions 
            SET total_tokens_in = total_tokens_in + ?,
                total_tokens_out = total_tokens_out + ?,
                tokens_saved = tokens_saved + ?,
                ended_at = ?,
                status = 'completed',
                cwd = ?,
                repository = ?,
                branch = ?,
                model = ?,
                label = ?
            WHERE id = ?
        """, (
            original_tokens,
            compressed_tokens,
            saved,
            now,
            context["cwd"],
            context["repository"],
            context["branch"],
            model,
            label,
            session_id,
        ))

        turn_row = cursor.execute(
            "SELECT COALESCE(MAX(turn_index), -1) + 1 AS next_turn FROM turns WHERE session_id=?",
            (session_id,),
        ).fetchone()
        turn_index = int(turn_row[0] if turn_row else 0)
        cursor.execute("""
            INSERT INTO turns
                (session_id, turn_index, user_message, assistant_response,
                 tokens_in, tokens_out, tokens_saved, model, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            turn_index,
            user_prompt or "",
            assistant_response or "",
            original_tokens,
            compressed_tokens,
            saved,
            model,
            now,
        ))
        turn_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO compressions
                (session_id, turn_id, compressor, tokens_before, tokens_after,
                 compressed_at, model_used, original_text, compressed_text,
                 compression_method, source, algorithm_details, request_body,
                 optimized_body, response_body, request_source, debug_log_excerpt,
                 actual_usage, compression_score, compression_grade, recommendations)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            turn_id,
            "byok_proxy",
            original_tokens,
            compressed_tokens,
            now,
            model,
            user_prompt or "",
            optimized_prompt or "",
            "chat_payload",
            record_source,
            algorithm_details,
            _json_dumps(request_body, limit=1_000_000),
            _json_dumps(optimized_body, limit=1_000_000),
            _json_dumps(response_body, limit=1_000_000),
            request_source,
            debug_excerpt,
            _json_dumps(actual_usage or {}),
            score,
            grade,
            _json_dumps(tips),
        ))
        
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to log to database: {e}")
    finally:
        if conn is not None:
            conn.close()


@router.post("/TrimP/trace")
async def record_external_trace(request: Request):
    """Accept a full trace from a localhost-only transport bridge."""
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(status_code=403, detail="Trace ingestion is localhost-only")

    payload = await request.json()
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    original_tokens = int(stats.get("tokens_before") or 0)
    compressed_tokens = int(stats.get("tokens_after") or original_tokens)
    if original_tokens < 0 or compressed_tokens < 0:
        raise HTTPException(status_code=400, detail="Invalid token counts")

    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        session_id = f"external-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    model = normalize_copilot_model(payload.get("model"))
    request_body = payload.get("request_body")
    optimized_body = payload.get("optimized_body")
    response_body = payload.get("response_body")
    workspace = payload.get("workspace_context")

    log_to_database(
        session_id=session_id[:180],
        model=model,
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        compression_ratio=(original_tokens - compressed_tokens) / original_tokens
        if original_tokens
        else 0.0,
        algorithm_details=json.dumps(stats, separators=(",", ":"), ensure_ascii=False),
        user_prompt=str(payload.get("user_prompt") or ""),
        optimized_prompt=str(payload.get("optimized_prompt") or ""),
        assistant_response=str(payload.get("assistant_response") or ""),
        request_body=request_body if isinstance(request_body, dict) else {},
        optimized_body=optimized_body if isinstance(optimized_body, dict) else {},
        response_body=response_body if isinstance(response_body, dict) else {},
        actual_usage=payload.get("actual_usage")
        if isinstance(payload.get("actual_usage"), dict)
        else {},
        request_source=str(payload.get("request_source") or "external-proxy")[:80],
        workspace_context=workspace if isinstance(workspace, dict) else None,
        debug_log_excerpt=str(payload.get("debug_log_excerpt") or "")[:20_000],
        record_source="byok",
    )
    return {
        "status": "recorded",
        "session_id": session_id,
        "tokens_saved": max(0, original_tokens - compressed_tokens),
    }


@router.post("/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible chat completions endpoint for GitHub Copilot BYOK mode.
    
    Accepts requests from Copilot CLI, compresses context, and forwards to GitHub.
    """
    try:
        # Get request body
        body = await request.json()
        
        # Get GitHub Copilot credentials
        try:
            token_details = await get_copilot_api_token()
        except RuntimeError as e:
            logger.error(f"Auth error: {e}")
            raise HTTPException(status_code=401, detail=str(e))
        
        # Extract messages
        model = normalize_copilot_model(body.get("model", "claude-sonnet-4.6"))
        body["model"] = model
        if not body.get("messages"):
            raise HTTPException(status_code=400, detail="No messages provided")
        
        # Get or generate session ID
        session_id = os.environ.get('COPILOT_AGENT_SESSION_ID', f"byok-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
        
        original_body = json.loads(json.dumps(body))
        user_prompt = _extract_user_prompt(body)
        # Compress the full chat body, including user/tool text. System prompts are opt-in.
        body, stats = optimizer.optimize_body(body)
        optimized_prompt = _extract_user_prompt(body)
        original_tokens = stats.tokens_before
        compressed_tokens = stats.tokens_after
        
        logger.info(
            f"Compressed {original_tokens} → {compressed_tokens} tokens "
            f"({stats.savings_pct:.1f}% reduction)"
        )
        
        # Forward to GitHub Copilot API
        headers = copilot_request_headers(token_details.token)
        upstream_url = build_copilot_upstream_url(token_details.api_url, "/v1/chat/completions")
        logger.info("Forwarding to GitHub Copilot API %s with model=%s", upstream_url, model)
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Determine if streaming or not
            is_streaming = body.get("stream", False)
            
            if is_streaming:
                # Stream response
                response = await client.post(
                    upstream_url,
                    json=body,
                    headers=headers,
                    timeout=60.0
                )
                log_to_database(
                    session_id,
                    model,
                    original_tokens,
                    compressed_tokens,
                    stats.savings_pct / 100.0,
                    json.dumps(stats.as_dict(), separators=(",", ":"), ensure_ascii=False),
                    user_prompt=user_prompt,
                    optimized_prompt=optimized_prompt,
                    assistant_response="(streaming response)",
                    request_body=original_body,
                    optimized_body=body,
                    response_body={"stream": True, "status_code": response.status_code},
                    actual_usage={},
                )
                
                return StreamingResponse(
                    response.iter_bytes(),
                    media_type="text/event-stream",
                    headers={
                        **dict(response.headers),
                        "x-TrimP-tokens-before": str(stats.tokens_before),
                        "x-TrimP-tokens-after": str(stats.tokens_after),
                        "x-TrimP-tokens-saved": str(stats.tokens_saved),
                        "x-TrimP-savings-pct": f"{stats.savings_pct:.2f}",
                    }
                )
            else:
                # Regular response
                response = await client.post(
                    upstream_url,
                    json=body,
                    headers=headers
                )
                
                response.raise_for_status()
                result = response.json()
                assistant_text = _extract_assistant_text(result)
                actual_usage = _usage_from_response(result)
                log_to_database(
                    session_id,
                    model,
                    original_tokens,
                    compressed_tokens,
                    stats.savings_pct / 100.0,
                    json.dumps(stats.as_dict(), separators=(",", ":"), ensure_ascii=False),
                    user_prompt=user_prompt,
                    optimized_prompt=optimized_prompt,
                    assistant_response=assistant_text,
                    request_body=original_body,
                    optimized_body=body,
                    response_body=result,
                    actual_usage=actual_usage,
                )
                
                # Add compression stats to response metadata
                if "usage" in result:
                    result["usage"]["original_prompt_tokens"] = original_tokens
                    result["usage"]["TrimP_prompt_tokens_after"] = compressed_tokens
                    result["usage"]["TrimP_tokens_saved"] = stats.tokens_saved
                    result["usage"]["compression_ratio"] = stats.savings_pct / 100.0
                result["TrimP"] = stats.as_dict()
                
                return JSONResponse(result)
                
    except httpx.HTTPStatusError as e:
        logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"GitHub API error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/responses")
async def responses(request: Request):
    """OpenAI Responses-compatible endpoint for Copilot BYOK mode."""
    try:
        body = await request.json()
        try:
            token_details = await get_copilot_api_token()
        except RuntimeError as e:
            logger.error(f"Auth error: {e}")
            raise HTTPException(status_code=401, detail=str(e))

        model = normalize_copilot_model(body.get("model", "gpt-5.4"))
        body["model"] = model
        session_id = os.environ.get(
            "COPILOT_AGENT_SESSION_ID", f"byok-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        )
        original_body = json.loads(json.dumps(body))
        user_prompt = _extract_user_prompt(body)
        body, stats = optimizer.optimize_body(body)
        optimized_prompt = _extract_user_prompt(body)
        logger.info(
            f"Compressed responses body {stats.tokens_before} → {stats.tokens_after} tokens "
            f"({stats.savings_pct:.1f}% reduction)"
        )
        headers = copilot_request_headers(token_details.token)
        upstream_url = build_copilot_upstream_url(token_details.api_url, "/v1/responses")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(upstream_url, json=body, headers=headers)
            response.raise_for_status()
            result = response.json()
            assistant_text = _extract_assistant_text(result)
            actual_usage = _usage_from_response(result)
            log_to_database(
                session_id,
                model,
                stats.tokens_before,
                stats.tokens_after,
                stats.savings_pct / 100.0,
                json.dumps(stats.as_dict(), separators=(",", ":"), ensure_ascii=False),
                user_prompt=user_prompt,
                optimized_prompt=optimized_prompt,
                assistant_response=assistant_text,
                request_body=original_body,
                optimized_body=body,
                response_body=result,
                actual_usage=actual_usage,
                request_source="copilot-cli-proxy-responses",
            )
            result["TrimP"] = stats.as_dict()
            return JSONResponse(result)
    except httpx.HTTPStatusError as e:
        logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"GitHub API error: {e.response.text}",
        )
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models():
    """List available models (for compatibility)."""
    return {
        "data": [
            {"id": "claude-sonnet-4.6", "object": "model"},
            {"id": "claude-sonnet-5", "object": "model"},
            {"id": "claude-haiku-4.5", "object": "model"},
            {"id": "claude-opus-4.8", "object": "model"},
            {"id": "gpt-5-mini", "object": "model"},
            {"id": "gpt-5.3-codex", "object": "model"},
            {"id": "gpt-5.4", "object": "model"},
            {"id": "gpt-5.4-mini", "object": "model"},
            {"id": "gpt-5.5", "object": "model"},
            {"id": "gpt-5.6-sol", "object": "model"},
            {"id": "gpt-5.6-terra", "object": "model"},
            {"id": "gpt-5.6-luna", "object": "model"},
            {"id": "gemini-3.1-pro", "object": "model"},
            {"id": "gemini-3.5-flash", "object": "model"},
        ]
    }


@router.get("/health")
async def health():
    """Health check endpoint."""
    try:
        token = await get_copilot_api_token()
        return {"status": "ok", "auth": "configured", "api_url": token.api_url, "source": token.source}
    except RuntimeError:
        return {"status": "ok", "auth": "missing"}


@router.post("/TrimP/measure")
async def measure(request: Request):
    """Return before/after optimization stats without forwarding upstream."""
    body = await request.json()
    optimized, stats = optimizer.optimize_body(body)
    return {"TrimP": stats.as_dict(), "optimized": optimized}


@router.get("/TrimP/stats")
async def stats():
    """Aggregate BYOK compression events."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT COUNT(*) AS requests,
                   COALESCE(SUM(tokens_before), 0) AS before,
                   COALESCE(SUM(tokens_after), 0) AS after
            FROM compressions
            WHERE source='byok'
        """).fetchone()
    finally:
        conn.close()
    before = int(row["before"] if row else 0)
    after = int(row["after"] if row else 0)
    saved = max(0, before - after)
    return {
        "requests": int(row["requests"] if row else 0),
        "tokens_before": before,
        "tokens_after": after,
        "tokens_saved": saved,
        "savings_pct": round(saved / before * 100.0, 2) if before else 0.0,
    }
