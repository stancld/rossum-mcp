"""FastAPI application entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from rossum_agent.api.routes import chats, files, health, messages
from rossum_agent.api.services.agent_service import AgentService
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.api.services.file_service import FileService

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Rossum Agent API",
    description="REST API for Rossum Agent - AI-powered document processing assistant",
    version="0.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

_chat_service: ChatService | None = None
_agent_service: AgentService | None = None
_file_service: FileService | None = None


def get_chat_service() -> ChatService:
    """Get the shared ChatService instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


def get_agent_service() -> AgentService:
    """Get the shared AgentService instance."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


def get_file_service() -> FileService:
    """Get the shared FileService instance."""
    global _file_service
    if _file_service is None:
        _file_service = FileService(get_chat_service().storage)
    return _file_service


health.set_chat_service_getter(get_chat_service)
chats.set_chat_service_getter(get_chat_service)
messages.set_chat_service_getter(get_chat_service)
messages.set_agent_service_getter(get_agent_service)
files.set_chat_service_getter(get_chat_service)
files.set_file_service_getter(get_file_service)

app.include_router(health.router, prefix="/api/v1")
app.include_router(chats.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")

STATIC_DIR = Path(__file__).parent / "static"
ASSETS_DIR = Path(__file__).parent.parent / "assets"


@app.get("/test-client")
async def test_client_index() -> FileResponse:
    """Serve the test client HTML page."""
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/test-client/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/test-client", StaticFiles(directory=STATIC_DIR), name="test-client-static")


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize services on startup."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger.info("Rossum Agent API starting up...")

    chat_service = get_chat_service()
    if chat_service.is_connected():
        logger.info("Redis connection established")
    else:
        logger.warning("Redis connection failed - some features may not work")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on shutdown."""
    logger.info("Rossum Agent API shutting down...")
    if _chat_service is not None:
        _chat_service.storage.close()


def main() -> None:
    """CLI entry point for the API server."""
    parser = argparse.ArgumentParser(description="Run the Rossum Agent API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes (default: 1)")

    args = parser.parse_args()

    try:
        import uvicorn  # noqa: PLC0415
    except ImportError:
        print("Error: uvicorn is required. Install with: pip install 'rossum-agent[api]'")
        sys.exit(1)

    uvicorn.run(
        "rossum_agent.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
    )


if __name__ == "__main__":
    main()
