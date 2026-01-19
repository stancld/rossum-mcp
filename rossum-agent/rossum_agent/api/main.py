"""FastAPI application entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from rossum_agent.api.routes import chats, files, health, messages
from rossum_agent.api.services.agent_service import AgentService
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.api.services.file_service import FileService

logger = logging.getLogger(__name__)

MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10 MB (supports image uploads)

limiter = Limiter(key_func=get_remote_address)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_SIZE:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": f"Request body too large. Maximum size is {MAX_REQUEST_SIZE // 1024} KB."},
            )
        return await call_next(request)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


app = FastAPI(
    title="Rossum Agent API",
    description="REST API for Rossum Agent - AI-powered document processing assistant",
    version="0.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(RequestSizeLimitMiddleware)


def _build_cors_origin_regex() -> str:
    """Build CORS origin regex including any additional allowed hosts."""
    patterns = [r".*\.rossum\.app"]
    additional_hosts = os.environ.get("ADDITIONAL_ALLOWED_ROSSUM_HOSTS", "")
    if additional_hosts:
        patterns.extend(p.strip() for p in additional_hosts.split(",") if p.strip())
    return rf"https://({'|'.join(patterns)})"


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://elis.rossum.ai",
        "https://elis.develop.r8.lol",
    ],
    allow_origin_regex=_build_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes (default: 1)")

    args = parser.parse_args()

    try:
        import uvicorn  # noqa: PLC0415
    except ImportError:
        print("Error: uvicorn is required. Install with: uv pip install 'rossum-agent[api]'")
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
