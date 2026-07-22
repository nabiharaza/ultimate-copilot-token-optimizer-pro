"""
Compression proxy — intercepts Copilot CLI API calls and applies compression.

Architecture:
1. Proxy server listens on localhost:8765 (configurable)
2. Copilot CLI sends requests to the proxy (via ANTHROPIC_BASE_URL or similar)
3. Proxy applies compression to messages
4. Proxy forwards to real API
5. Proxy records metrics in TrimP DB
6. Proxy returns response to Copilot CLI

Usage:
    TrimP proxy start [--port 8765] [--upstream anthropic|openai|azure]
    
    Then set environment variable:
    export ANTHROPIC_BASE_URL="http://localhost:8765"
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from rich.console import Console

from TrimP.chat_optimizer import ChatPayloadOptimizer
from TrimP.compression import (
    ActivityMode,
    ArchiveManager,
    BashCompressor,
    DeltaCompressor,
    JsonTableCompressor,
    LoopDetector,
    SearchCompressor,
    SkeletonCompressor,
    StructuralAuditor,
    VerbosityNudger,
)
from TrimP.db import db, get_config, now_iso
from TrimP.session import get_or_create_session, record_turn

console = Console()

# Upstream API endpoints
UPSTREAMS = {
    "github-copilot": "https://api.githubcopilot.com",
    "github-enterprise": "https://api.github.com",  # Will be customized per installation
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com",
    "azure": get_config("proxy.azure_endpoint", "https://api.openai.azure.com"),
}


class CompressionProxy:
    """Compression middleware proxy for Copilot CLI."""

    def __init__(self, upstream: str = "anthropic", port: int = 8765):
        self.upstream_base = UPSTREAMS.get(upstream, upstream)
        self.port = port
        self.app = FastAPI(title="TrimP Compression Proxy")
        self.session_id = get_or_create_session()
        
        # Initialize compressors
        self.bash = BashCompressor()
        self.search = SearchCompressor()
        self.json_table = JsonTableCompressor()
        self.delta = DeltaCompressor(self.session_id)
        self.skeleton = SkeletonCompressor()
        self.archive = ArchiveManager(self.session_id)
        self.verbosity = VerbosityNudger()
        self.loop = LoopDetector(self.session_id)
        self.activity = ActivityMode(self.session_id)
        self.chat_optimizer = ChatPayloadOptimizer()
        self.last_stats: dict[str, Any] | None = None
        
        self.delta.load_from_db()
        
        self._setup_routes()

    def _setup_routes(self):
        @self.app.post("/v1/messages")
        @self.app.post("/v1/chat/completions")
        async def proxy_completion(request: Request):
            return await self._handle_completion(request)

        @self.app.get("/TrimP/status")
        async def proxy_status():
            return {
                "status": "running",
                "session_id": self.session_id,
                "upstream": self.upstream_base,
                "port": self.port,
                "compressions_enabled": self._enabled_compressions(),
                "last_request": self.last_stats,
            }

        @self.app.get("/health")
        @self.app.get("/v1/health")
        async def health():
            return {"status": "ok", "service": "TrimP-proxy", "session_id": self.session_id}

        @self.app.get("/TrimP/stats")
        async def proxy_stats():
            return self._aggregate_stats()

        @self.app.post("/TrimP/measure")
        @self.app.post("/v1/TrimP/measure")
        async def proxy_measure(request: Request):
            body = await request.json()
            optimized, stats = self.chat_optimizer.optimize_body(body)
            return {"TrimP": stats.as_dict(), "optimized": optimized}

        @self.app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
        async def proxy_all(request: Request, path: str):
            return await self._proxy_passthrough(request, path)

    async def _handle_completion(self, request: Request):
        """Main compression logic — intercepts completion requests."""
        start = time.time()
        body = await request.json()
        original_messages = body.get("messages", [])
        body, stats = self.chat_optimizer.optimize_body(body)
        tokens_before = stats.tokens_before
        tokens_after = stats.tokens_after
        tokens_saved = stats.tokens_saved
        self.last_stats = stats.as_dict()
        
        # Record compression event
        self._record_compression(
            "proxy_request",
            tokens_before,
            tokens_after,
            original_text=json.dumps(stats.as_dict(), separators=(",", ":"))[:500],
            compressed_text="",
            method="chat_payload",
        )
        
        # Forward to upstream
        console.print(f"[cyan]→[/cyan] Forwarding request to {self.upstream_base}")
        console.print(
            f"   Tokens: {tokens_before:,} → {tokens_after:,} "
            f"([green]-{tokens_saved:,} / {stats.savings_pct:.1f}%[/green])"
        )
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            upstream_url = f"{self.upstream_base}{request.url.path}"
            headers = dict(request.headers)
            headers.pop("host", None)
            
            try:
                response = await client.post(
                    upstream_url,
                    json=body,
                    headers=headers,
                )
                
                # Check if streaming
                if "text/event-stream" in response.headers.get("content-type", ""):
                    return StreamingResponse(
                        self._stream_and_analyze(response),
                        media_type="text/event-stream",
                        headers=self._response_headers(response.headers, stats),
                    )
                
                resp_data = response.json()
                
                # Analyze response verbosity
                if "content" in resp_data:
                    content = resp_data["content"]
                    if isinstance(content, list) and len(content) > 0:
                        text = content[0].get("text", "")
                        verbosity_report = self.verbosity.analyze(text)
                        if verbosity_report.nudge:
                            console.print(f"[yellow]{verbosity_report.nudge}[/yellow]")
                
                # Record turn
                elapsed = time.time() - start
                record_turn(
                    self.session_id,
                    turn_index=self._get_turn_count(),
                    user_message=str(original_messages[-1] if original_messages else ""),
                    assistant_response=str(resp_data.get("content", "")),
                    tokens_in=tokens_after,
                    tokens_out=resp_data.get("usage", {}).get("output_tokens", 0),
                    tokens_saved=tokens_saved,
                )
                
                console.print(f"[green]✓[/green] Response received in {elapsed:.1f}s")
                
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=self._response_headers(response.headers, stats),
                )
            
            except Exception as e:
                console.print(f"[red]✗ Proxy error: {e}[/red]")
                return Response(
                    content=json.dumps({"error": str(e)}),
                    status_code=500,
                )

    async def _compress_tool_result(self, part: dict) -> tuple[dict, int]:
        """Compress a tool result part."""
        content = part.get("content", "")
        tool_name = part.get("tool_use_id", "unknown")
        
        tokens_before = self._estimate_tokens(content)
        compressed = content
        saved = 0
        
        # Try bash compression
        if any(pattern in content for pattern in ["PASSED", "FAILED", "npm", "pip", "git", "docker"]):
            compressed, saved = self.bash.compress(content)
            self._record_compression("bash", tokens_before, self._estimate_tokens(compressed),
                                     content, compressed, "bash")
        
        # Try search compression
        elif content.count("\n") > 50 and (":" in content or "match" in content.lower()):
            compressed, saved = self.search.compress(content)
            self._record_compression("search", tokens_before, self._estimate_tokens(compressed),
                                     content, compressed, "search")
        
        # Try JSON compression
        elif content.strip().startswith(("{", "[")):
            compressed, saved = self.json_table.compress_json(content)
            self._record_compression("json", tokens_before, self._estimate_tokens(compressed),
                                     content, compressed, "json")
        
        # Archive if still large
        if len(compressed) > 4096:
            compressed, arch_saved = self.archive.maybe_archive(compressed, tool_name)
            saved += arch_saved
            if arch_saved > 0:
                self._record_compression("archive", tokens_before, self._estimate_tokens(compressed),
                                         "", compressed, "archive")
        
        part["content"] = compressed
        return part, saved

    async def _compress_user_message(self, content: str) -> tuple[str, int]:
        """Compress a user message."""
        tokens_before = self._estimate_tokens(content)
        
        # Detect activity mode
        mode_result = self.activity.detect(content)
        if mode_result.confidence > 0.3:
            console.print(f"[dim]Activity: {mode_result.mode} ({mode_result.confidence:.0%})[/dim]")
        
        # No compression on user messages (preserve intent)
        return content, 0

    async def _stream_and_analyze(self, response: httpx.Response):
        """Stream response and analyze chunks."""
        buffer = ""
        async for chunk in response.aiter_bytes():
            buffer += chunk.decode("utf-8", errors="ignore")
            yield chunk
        
        # Analyze complete response
        if buffer:
            verbosity_report = self.verbosity.analyze(buffer)
            if verbosity_report.score > 0.4:
                console.print(f"[yellow]Verbosity: {verbosity_report.grade} ({verbosity_report.score:.0%})[/yellow]")

    async def _proxy_passthrough(self, request: Request, path: str):
        """Pass through non-completion requests."""
        async with httpx.AsyncClient() as client:
            upstream_url = f"{self.upstream_base}/{path}"
            headers = dict(request.headers)
            headers.pop("host", None)
            
            response = await client.request(
                method=request.method,
                url=upstream_url,
                headers=headers,
                content=await request.body(),
            )
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

    def _estimate_tokens(self, text: str) -> int:
        from TrimP.tokenization import count_tokens

        return count_tokens(str(text)).tokens

    def _response_headers(self, upstream_headers: Any, stats) -> dict[str, str]:
        headers = dict(upstream_headers)
        headers["x-TrimP-tokens-before"] = str(stats.tokens_before)
        headers["x-TrimP-tokens-after"] = str(stats.tokens_after)
        headers["x-TrimP-tokens-saved"] = str(stats.tokens_saved)
        headers["x-TrimP-savings-pct"] = f"{stats.savings_pct:.2f}"
        return headers

    def _aggregate_stats(self) -> dict[str, Any]:
        with db() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS count,
                          COALESCE(SUM(tokens_before), 0) AS before,
                          COALESCE(SUM(tokens_after), 0) AS after
                   FROM compressions
                   WHERE session_id=? AND compressor='proxy_request'""",
                (self.session_id,),
            ).fetchone()
        before = int(row["before"] if row else 0)
        after = int(row["after"] if row else 0)
        saved = max(0, before - after)
        return {
            "session_id": self.session_id,
            "requests": int(row["count"] if row else 0),
            "tokens_before": before,
            "tokens_after": after,
            "tokens_saved": saved,
            "savings_pct": round(saved / before * 100.0, 2) if before else 0.0,
            "last_request": self.last_stats,
        }

    def _record_compression(
        self,
        compressor: str,
        before: int,
        after: int,
        original_text: str = "",
        compressed_text: str = "",
        method: str = "",
    ):
        """Record a compression event with full metadata for the live monitor."""
        import os
        model = os.environ.get("COPILOT_MODEL", "")
        ts = now_iso()
        with db() as conn:
            conn.execute(
                """INSERT INTO compressions
                   (session_id, compressor, tokens_before, tokens_after,
                    compressed_at, model_used, original_text, compressed_text,
                    compression_method, source)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    self.session_id, compressor, before, after, ts,
                    model,
                    original_text[:500] if original_text else "",
                    compressed_text[:500] if compressed_text else "",
                    method or compressor,
                    "proxy",
                ),
            )
        # Non-blocking push to live dashboard WebSocket clients
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._ws_broadcast(compressor, before, after, ts))
        except Exception:
            pass

    async def _ws_broadcast(self, compressor: str, before: int, after: int, ts: str):
        """Push new compression event to all connected WebSocket clients."""
        try:
            from TrimP.dashboard.server import manager
            saved = before - after
            await manager.broadcast({
                "type": "compression",
                "compressor": compressor,
                "tokens_before": before,
                "tokens_after": after,
                "tokens_saved": saved,
                "savings_pct": round(saved / before * 100, 1) if before else 0,
                "compressed_at": ts,
                "session_id": self.session_id,
            })
        except Exception:
            pass

    def _get_turn_count(self) -> int:
        with db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM turns WHERE session_id=?",
                (self.session_id,),
            ).fetchone()
        return row["c"] if row else 0

    def _enabled_compressions(self) -> list[str]:
        features = [
            "bash", "search", "json", "delta", "skeleton",
            "archive", "verbosity", "structural", "loop_detect",
        ]
        return [f for f in features if get_config(f"compression.{f}.enabled", "true") == "true"]


def start_proxy(upstream: str = "anthropic", port: int = 8765, host: str = "127.0.0.1") -> None:
    """Start the compression proxy server.

    Binds to localhost by default since this proxy forwards Copilot/model
    API traffic (including request/response bodies) and should not be
    reachable from other machines on the network. Pass host="0.0.0.0"
    explicitly if LAN access is genuinely needed.
    """
    import uvicorn

    console.print(f"[bold cyan]🔧 TrimP Compression Proxy[/bold cyan]")
    console.print(f"   Listening: [bold]http://{host}:{port}[/bold]")
    console.print(f"   Upstream: [bold]{UPSTREAMS.get(upstream, upstream)}[/bold]")
    console.print(f"   Session: {get_or_create_session()[:16]}...")
    console.print()
    console.print("Set environment variable:")
    if upstream == "anthropic":
        console.print(f"   [bold]export ANTHROPIC_BASE_URL=http://localhost:{port}[/bold]")
    elif upstream == "openai":
        console.print(f"   [bold]export OPENAI_BASE_URL=http://localhost:{port}[/bold]")
    console.print()
    console.print("Press Ctrl+C to stop")
    console.print()
    
    proxy = CompressionProxy(upstream=upstream, port=port)
    uvicorn.run(proxy.app, host=host, port=port, log_level="warning")
