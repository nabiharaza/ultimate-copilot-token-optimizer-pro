#!/usr/bin/env python3
"""
TrimP IntelliJ/PyCharm Proxy — GitHub Copilot Chat compression proxy.

This proxy intercepts GitHub Copilot Chat API requests from IntelliJ/PyCharm,
compresses the context using TrimP algorithms, forwards to GitHub Copilot API,
and returns the response.

Configuration for IntelliJ/PyCharm:
1. Start this proxy: python3 TrimP_intellij_proxy.py --port 8765
2. In PyCharm: Settings -> Appearance & Behavior -> System Settings -> HTTP Proxy
   - Manual proxy configuration: HTTP, Host: localhost, Port: 8765
   - Check "Use this proxy server for all protocols"
3. Add exception for localhost/127.0.0.1 if needed
4. Restart PyCharm

Alternative: Set environment variables before starting PyCharm:
  export HTTP_PROXY=http://localhost:8765
  export HTTPS_PROXY=http://localhost:8765
  pycharm

The proxy will:
- Intercept requests to api.githubcopilot.com/chat/completions
- Compress messages using TrimP algorithms
- Forward to GitHub Copilot API
- Return compressed response
- Log savings to TrimP dashboard
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

# Add parent directory to path for TrimP imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from TrimP.chat_optimizer import ChatPayloadOptimizer
from TrimP.compression import (
    BashCompressor,
    SearchCompressor,
    JsonTableCompressor,
    SkeletonCompressor,
    StopWordRemover,
    PromptCompressor,
)
from TrimP.db import db, get_connection, now_iso
from TrimP.session import get_or_create_session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("TrimP-intellij-proxy")

# GitHub Copilot API endpoints
GITHUB_COPILOT_API = "https://api.githubcopilot.com"
GITHUB_COPILOT_CHAT_COMPLETIONS = f"{GITHUB_COPILOT_API}/chat/completions"
GITHUB_COPILOT_MODELS = f"{GITHUB_COPILOT_API}/models"

# Integration ID for IntelliJ (may differ from VS Code's "vscode-chat")
INTEGRATION_ID = os.environ.get("COPILOT_INTEGRATION_ID", "intellij-chat")

# Token from environment or GitHub CLI
GITHUB_TOKEN = os.environ.get("GITHUB_COPILOT_TOKEN") or os.environ.get("GH_TOKEN")


class IntelliJProxy:
    """Proxy server for GitHub Copilot Chat in IntelliJ/PyCharm."""

    def __init__(self, port: int = 8765, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        self.app = FastAPI(title="TrimP IntelliJ Proxy")
        self.session_id = get_or_create_session()
        self.chat_optimizer = ChatPayloadOptimizer()
        self.compressors = {
            "bash": BashCompressor(),
            "search": SearchCompressor(),
            "json": JsonTableCompressor(),
            "skeleton": SkeletonCompressor(),
            "stopword": StopWordRemover(),
            "prompt": PromptCompressor(),
        }
        self.request_count = 0
        self.total_tokens_saved = 0
        self._setup_routes()

    def _setup_routes(self):
        @self.app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
        async def proxy(request: Request, path: str):
            return await self._handle_request(request, path)

        @self.app.get("/health")
        async def health():
            return {
                "status": "ok",
                "service": "TrimP-intellij-proxy",
                "session_id": self.session_id[:16] + "...",
                "requests_processed": self.request_count,
                "total_tokens_saved": self.total_tokens_saved,
            }

        @self.app.get("/TrimP/stats")
        async def stats():
            return self._get_stats()

    async def _handle_request(self, request: Request, path: str) -> Response:
        """Handle incoming request - intercept Copilot chat completions."""
        self.request_count += 1
        start_time = time.time()

        # Get request body
        body = await request.body()
        headers = dict(request.headers)

        # Check if this is a chat completions request to GitHub Copilot
        is_copilot_chat = self._is_copilot_chat_request(request, path, headers)

        if is_copilot_chat:
            return await self._handle_copilot_chat(request, path, body, headers, start_time)
        else:
            # Pass through for all other requests
            return await self._passthrough(request, path, body, headers)

    def _is_copilot_chat_request(self, request: Request, path: str, headers: Dict) -> bool:
        """Check if request is a GitHub Copilot chat completion."""
        # Check host header or target
        host = headers.get("host", "").lower()
        if "githubcopilot.com" in host:
            return "/chat/completions" in path or request.url.path.endswith("/chat/completions")
        # Also check if it's a request to our proxy for chat completions
        if path == "chat/completions" or path == "v1/chat/completions":
            return True
        return False

    async def _handle_copilot_chat(
        self,
        request: Request,
        path: str,
        body: bytes,
        headers: Dict,
        start_time: float
    ) -> Response:
        """Handle Copilot chat completion request with compression."""
        try:
            # Parse request body
            try:
                request_data = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in request body, passing through")
                return await self._passthrough(request, path, body, headers)

            # Extract messages
            messages = request_data.get("messages", [])
            if not messages:
                logger.warning("No messages in request, passing through")
                return await self._passthrough(request, path, body, headers)

            # Get model
            model = request_data.get("model", "gpt-4")

            # Compress the messages
            original_tokens = self._estimate_tokens(json.dumps(request_data))
            compressed_data, compression_stats = self._compress_chat_request(request_data)
            compressed_tokens = self._estimate_tokens(json.dumps(compressed_data))
            tokens_saved = original_tokens - compressed_tokens

            self.total_tokens_saved += tokens_saved

            logger.info(
                f"Compressed Copilot request: {original_tokens} -> {compressed_tokens} tokens "
                f"({tokens_saved} saved, {compression_stats.get('savings_pct', 0):.1f}%)"
            )

            # Prepare headers for upstream
            upstream_headers = self._prepare_upstream_headers(headers)

            # Forward to GitHub Copilot API
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Check if streaming
                is_streaming = compressed_data.get("stream", False)

                if is_streaming:
                    return await self._stream_response(
                        client, compressed_data, upstream_headers,
                        original_tokens, compressed_tokens, tokens_saved, compression_stats
                    )
                else:
                    return await self._regular_response(
                        client, compressed_data, upstream_headers,
                        original_tokens, compressed_tokens, tokens_saved, compression_stats
                    )

        except Exception as e:
            logger.error(f"Error handling Copilot chat request: {e}", exc_info=True)
            # Fall back to pass-through
            return await self._passthrough(request, path, body, headers)

    def _compress_chat_request(self, request_data: Dict) -> tuple[Dict, Dict]:
        """Compress chat request using TrimP algorithms."""
        # Use the chat optimizer for comprehensive compression
        optimized, stats = self.chat_optimizer.optimize_body(request_data)

        # Also apply specific compression to tool outputs if present
        optimized = self._compress_tool_outputs(optimized)

        return optimized, stats.as_dict()

    def _compress_tool_outputs(self, data: Dict) -> Dict:
        """Apply additional compression to tool outputs in messages."""
        messages = data.get("messages", [])
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                # Handle content parts (tool results, etc.)
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "tool_result":
                        tool_content = part.get("content", "")
                        if isinstance(tool_content, str) and len(tool_content) > 500:
                            # Try to detect content type and compress
                            compressed = self._compress_by_type(tool_content)
                            if compressed != tool_content:
                                part["content"] = compressed
        return data

    def _compress_by_type(self, text: str) -> str:
        """Compress text based on detected content type."""
        text_lower = text.lower()

        # Detect content type and apply appropriate compressor
        if any(kw in text_lower for kw in ["traceback", "error", "exception", "failed", "passed", "npm", "pip", "pytest", "cargo", "go build", "maven", "gradle"]):
            return self.compressors["bash"].compress(text)[0]
        elif text.count("\n") > 50 and (":" in text or "match" in text_lower):
            return self.compressors["search"].compress(text)[0]
        elif text.strip().startswith(("{", "[")):
            return self.compressors["json"].compress_json(text)[0]
        elif len(text) > 1000:
            return self.compressors["skeleton"].compress(text)[0]
        return text

    def _prepare_upstream_headers(self, headers: Dict) -> Dict:
        """Prepare headers for upstream GitHub Copilot API."""
        upstream_headers = {}

        # Copy relevant headers
        for key in ["authorization", "content-type", "accept", "user-agent", "copilot-integration-id"]:
            if key in headers:
                upstream_headers[key] = headers[key]

        # Ensure required headers
        if "authorization" not in upstream_headers:
            # Try to get token from environment
            token = GITHUB_TOKEN or os.environ.get("GITHUB_TOKEN")
            if token:
                upstream_headers["authorization"] = f"Bearer {token}"

        if "copilot-integration-id" not in upstream_headers:
            upstream_headers["copilot-integration-id"] = INTEGRATION_ID

        upstream_headers["content-type"] = "application/json"
        upstream_headers["accept"] = "application/json"

        return upstream_headers

    async def _stream_response(
        self,
        client: httpx.AsyncClient,
        data: Dict,
        headers: Dict,
        orig_tokens: int,
        comp_tokens: int,
        saved: int,
        stats: Dict
    ) -> StreamingResponse:
        """Handle streaming response from Copilot API."""
        upstream_url = GITHUB_COPILOT_CHAT_COMPLETIONS

        async def generate():
            async with client.stream("POST", upstream_url, json=data, headers=headers) as response:
                # Log compression stats
                self._log_compression(orig_tokens, comp_tokens, saved, stats)

                async for chunk in response.aiter_bytes():
                    yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "X-TRIMP-Tokens-Before": str(orig_tokens),
                "X-TRIMP-Tokens-After": str(comp_tokens),
                "X-TRIMP-Tokens-Saved": str(saved),
                "X-TRIMP-Savings-Pct": f"{stats.get('savings_pct', 0):.1f}",
            }
        )

    async def _regular_response(
        self,
        client: httpx.AsyncClient,
        data: Dict,
        headers: Dict,
        orig_tokens: int,
        comp_tokens: int,
        saved: int,
        stats: Dict
    ) -> JSONResponse:
        """Handle regular (non-streaming) response."""
        upstream_url = GITHUB_COPILOT_CHAT_COMPLETIONS

        response = await client.post(upstream_url, json=data, headers=headers)
        response.raise_for_status()
        result = response.json()

        # Log compression stats
        self._log_compression(orig_tokens, comp_tokens, saved, stats)

        # Add TrimP metadata to response
        if "usage" in result:
            result["usage"]["TrimP_original_tokens"] = orig_tokens
            result["usage"]["TrimP_compressed_tokens"] = comp_tokens
            result["usage"]["TrimP_tokens_saved"] = saved
            result["usage"]["TrimP_savings_pct"] = stats.get("savings_pct", 0)
        result["TrimP"] = stats

        return JSONResponse(
            content=result,
            headers={
                "X-TRIMP-Tokens-Before": str(orig_tokens),
                "X-TRIMP-Tokens-After": str(comp_tokens),
                "X-TRIMP-Tokens-Saved": str(saved),
                "X-TRIMP-Savings-Pct": f"{stats.get('savings_pct', 0):.1f}",
            }
        )

    async def _passthrough(
        self,
        request: Request,
        path: str,
        body: bytes,
        headers: Dict
    ) -> Response:
        """Pass through request to original destination."""
        # Determine upstream URL
        host = headers.get("host", "api.githubcopilot.com")
        if not host.startswith("http"):
            upstream_url = f"https://{host}/{path}"
        else:
            upstream_url = f"{host}/{path}"

        # Prepare headers
        upstream_headers = {k: v for k, v in headers.items() if k.lower() not in ["host", "content-length"]}

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.request(
                method=request.method,
                url=upstream_url,
                content=body,
                headers=upstream_headers,
            )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type"),
        )

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough: 4 chars per token)."""
        return max(1, len(text) // 4)

    def _log_compression(self, orig: int, comp: int, saved: int, stats: Dict):
        """Log compression event to database."""
        try:
            get_connection()
            with db() as conn:
                conn.execute(
                    """INSERT INTO compressions
                       (session_id, compressor, tokens_before, tokens_after, compressed_at,
                        model_used, original_text, compressed_text, compression_method, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        self.session_id,
                        "intellij_proxy",
                        orig,
                        comp,
                        now_iso(),
                        "github-copilot-chat",
                        "",
                        "",
                        "chat_payload",
                        "intellij",
                    ),
                )
        except Exception as e:
            logger.warning(f"Failed to log compression: {e}")

    def _get_stats(self) -> Dict:
        """Get proxy statistics."""
        return {
            "session_id": self.session_id,
            "requests_processed": self.request_count,
            "total_tokens_saved": self.total_tokens_saved,
            "proxy_running": True,
        }

    def run(self):
        """Run the proxy server."""
        logger.info(f"Starting TrimP IntelliJ/PyCharm proxy on {self.host}:{self.port}")
        logger.info(f"Session ID: {self.session_id}")
        logger.info(f"GitHub Copilot API: {GITHUB_COPILOT_API}")
        logger.info(f"Integration ID: {INTEGRATION_ID}")
        logger.info("")
        logger.info("Configure PyCharm/IntelliJ:")
        logger.info(f"  Settings -> HTTP Proxy -> Manual: HTTP, localhost:{self.port}")
        logger.info("  OR set environment variables:")
        logger.info(f"    export HTTP_PROXY=http://localhost:{self.port}")
        logger.info(f"    export HTTPS_PROXY=http://localhost:{self.port}")
        logger.info("")
        logger.info("Dashboard: http://localhost:7432 (run 'TrimP dashboard' separately)")

        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="TrimP IntelliJ/PyCharm Proxy for GitHub Copilot Chat")
    parser.add_argument("--port", "-p", type=int, default=8765, help="Proxy port (default: 8765)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--integration-id", type=str, default=INTEGRATION_ID, help="Copilot integration ID")

    args = parser.parse_args()

    # Override integration ID if provided
    global INTEGRATION_ID
    INTEGRATION_ID = args.integration_id

    proxy = IntelliJProxy(port=args.port, host=args.host)
    proxy.run()


if __name__ == "__main__":
    main()