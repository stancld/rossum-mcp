"""FastAPI application setup for rossum-agent.

Usage:
    uvicorn rossum_agent.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from rossum_agent.api.routes import get_index_route
from rossum_agent.api.routes import router as rest_router
from rossum_agent.api.session import SessionManager
from rossum_agent.api.websocket import router as ws_router
from rossum_agent.redis_storage import RedisStorage

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting rossum-agent API server")
    storage = RedisStorage()
    app.state.storage = storage
    app.state.session_manager = SessionManager(storage)
    yield
    # Shutdown
    logger.info("Shutting down rossum-agent API server")
    storage.close()


app = FastAPI(
    title="Rossum Agent API",
    description="HTTP/WebSocket API for Rossum document processing agent",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(rest_router)
app.include_router(ws_router)

# Serve static files (test UI)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(get_index_route(STATIC_DIR))


def main() -> None:
    """Run the API server."""
    import uvicorn  # noqa: PLC0415

    uvicorn.run(
        "rossum_agent.api:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=os.getenv("API_RELOAD", "false").lower() == "true",
    )


if __name__ == "__main__":
    main()
