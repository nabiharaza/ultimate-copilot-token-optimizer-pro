"""
Standalone BYOK proxy server for GitHub Copilot CLI integration.

Usage:
    python3 byok_server.py [--port 8765]
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
import uvicorn

from TrimP.byok_proxy import router as byok_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="TrimP BYOK Proxy",
    description="GitHub Copilot BYOK proxy with context compression",
    version="1.0.0"
)

# Add BYOK routes
app.include_router(byok_router)

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "TrimP-byok-proxy",
        "status": "running",
        "endpoints": {
            "chat": "/v1/chat/completions",
            "models": "/v1/models",
            "health": "/v1/health"
        }
    }


def main():
    parser = argparse.ArgumentParser(description="TrimP BYOK Proxy Server")
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to run the proxy on (default: 8765)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    
    args = parser.parse_args()
    
    logger.info(f"🚀 Starting TrimP BYOK proxy on {args.host}:{args.port}")
    logger.info(f"📊 Dashboard: http://localhost:7432")
    logger.info(f"🔧 Configure Copilot CLI with: export COPILOT_PROVIDER_URL=http://localhost:{args.port}/v1")
    
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
