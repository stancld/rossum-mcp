"""FastAPI application entry point."""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
import threading
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
import uvicorn
from fastapi import FastAPI, Request, status
from gunicorn.app.base import BaseApplication
from rossum_mcp.logging_config import LogFormat, LogLevel, setup_logging

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.types import ASGIApp, Receive, Scope, Send

    from rossum_agent.postgres_storage import PostgresStorage

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from rossum_agent import __version__
from rossum_agent.api.routes import chats, commands, files, health, messages, slack
from rossum_agent.api.services.agent_service.service import AgentService
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.api.services.file_service import FileService
from rossum_agent.api.shutdown import shutdown_state
from rossum_agent.postgres_storage import PostgresStorage
from rossum_agent.valkey_client import ValkeyConnection

logger = structlog.get_logger(__name__)

MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10 MB (supports image uploads)

GUNICORN_TIMEOUT = 120
GUNICORN_GRACEFUL_TIMEOUT = 660  # 11 min — allow long SSE streams to complete on SIGTERM
GUNICORN_KEEPALIVE = 5
UVICORN_GRACEFUL_SHUTDOWN_TIMEOUT = 660

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


class GracefulShutdownMiddleware:
    """ASGI middleware that rejects new requests during graceful shutdown.

    Allows in-flight requests (including SSE streams) to complete. Health
    endpoint stays accessible for K8s readiness probes.

    Implemented as raw ASGI middleware (not BaseHTTPMiddleware) so that the
    active-request counter covers the full lifetime of streaming responses.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if shutdown_state.shutting_down and scope["path"] != "/api/v1/health":
            response = JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Server is shutting down"},
            )
            await response(scope, receive, send)
            return

        shutdown_state.active_requests += 1
        try:
            await self.app(scope, receive, send)
        finally:
            shutdown_state.active_requests -= 1


def _install_sigterm_handler(app: FastAPI) -> None:
    """Register a SIGTERM handler for graceful shutdown.

    On first SIGTERM: set the shutting-down flag (middleware starts returning
    503) and start a drain watcher that terminates the process once all
    in-flight requests complete.

    The handler removes itself so a second SIGTERM falls through to the
    default (immediate termination), acting as a force-quit escape hatch.
    """
    loop = asyncio.get_running_loop()

    def _on_sigterm():
        logger.info(
            f"SIGTERM received — entering graceful shutdown, {shutdown_state.active_requests} request(s) in flight"
        )
        shutdown_state.shutting_down = True
        # Remove our handler; second SIGTERM will terminate immediately (SIG_DFL)
        loop.remove_signal_handler(signal.SIGTERM)
        shutdown_state.drain_task = asyncio.ensure_future(_drain_and_shutdown())

    if threading.current_thread() is threading.main_thread():
        loop.add_signal_handler(signal.SIGTERM, _on_sigterm)


async def _drain_and_shutdown() -> None:
    """Wait for in-flight requests to complete, then trigger uvicorn shutdown.

    Uses SIGINT (not SIGTERM) because our SIGTERM handler replaced uvicorn's.
    SIGINT still reaches uvicorn's handler, ensuring proper lifespan teardown.
    """
    max_wait = 600  # 10 min
    elapsed = 0
    while shutdown_state.active_requests > 0 and elapsed < max_wait:
        logger.info(f"Graceful shutdown: waiting for {shutdown_state.active_requests} active request(s)")
        await asyncio.sleep(5)
        elapsed += 5
    if shutdown_state.active_requests > 0:
        logger.warning(
            f"Drain timeout ({max_wait}s) reached with {shutdown_state.active_requests} active request(s), forcing shutdown"
        )
    else:
        logger.info("All active requests completed, shutting down")
    os.kill(os.getpid(), signal.SIGINT)


def _create_storage() -> PostgresStorage:
    """Create the PostgreSQL chat storage backend."""
    storage = PostgresStorage()
    storage.initialize()
    return storage


def _init_services(app: FastAPI) -> None:
    """Initialize services and store them in app.state.

    Skips initialization if services are already set (e.g., during testing).
    """
    if not hasattr(app.state, "chat_service"):
        storage = _create_storage()
        app.state.chat_service = ChatService(storage=storage)
    if not hasattr(app.state, "agent_service"):
        app.state.agent_service = AgentService()
    if not hasattr(app.state, "file_service"):
        app.state.file_service = FileService(storage=app.state.chat_service.storage)
    if not hasattr(app.state, "valkey_connection"):
        app.state.valkey_connection = ValkeyConnection()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan context manager for startup and shutdown events."""
    setup_logging(
        log_level=LogLevel(os.environ.get("ROSSUM_AGENT_LOG_LEVEL", "INFO").upper()),
        log_format=LogFormat(os.environ.get("ROSSUM_AGENT_LOG_FORMAT", "console").lower()),
    )
    logger.info("Rossum Agent API starting up...")

    shutdown_state.shutting_down = False
    shutdown_state.active_requests = 0

    _init_services(app)
    _install_sigterm_handler(app)

    if app.state.chat_service.is_connected():
        logger.info("Chat storage (postgres) connection established")
    else:
        logger.warning("Chat storage (postgres) connection failed - some features may not work")

    yield

    logger.info("Rossum Agent API shutting down...")
    app.state.chat_service.storage.close()


app = FastAPI(
    title="Rossum Agent API",
    description="AI agent for Rossum document processing. Debug hooks, deploy configs, and automate workflows conversationally.",
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(GracefulShutdownMiddleware)


def _build_cors_origin_regex() -> str:
    """Build CORS origin regex including any additional allowed hosts."""
    patterns = [r".*\.rossum\.(app|ai)"]
    additional_hosts = os.environ.get("ADDITIONAL_ALLOWED_ROSSUM_HOSTS", "")
    if additional_hosts:
        patterns.extend(p.strip() for p in additional_hosts.split(",") if p.strip())
    return rf"https://({'|'.join(patterns)})"


_cors_origins = [
    "https://elis.rossum.ai",
    "https://elis.develop.r8.lol",
]
if os.environ.get("ROSSUM_AGENT_DEVELOP"):
    _cors_origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_build_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(chats.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(commands.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(slack.router, prefix="/api/v1")


def _run_uvicorn(args: argparse.Namespace) -> None:
    uvicorn.run(
        "rossum_agent.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        ws="wsproto",
        timeout_graceful_shutdown=UVICORN_GRACEFUL_SHUTDOWN_TIMEOUT,
    )


def _run_gunicorn(args: argparse.Namespace) -> None:
    """Run the server with gunicorn using UvicornWorker."""
    if args.reload:
        print("Error: --reload is not supported with gunicorn. Use uvicorn for development.")
        sys.exit(1)

    class StandaloneApplication(BaseApplication):
        def __init__(self, app_uri: str, options: dict | None = None):
            self.app_uri = app_uri
            self.options = options or {}
            super().__init__()

        def load_config(self) -> None:
            for key, value in self.options.items():
                if key in self.cfg.settings and value is not None:  # ty: ignore[unresolved-attribute]
                    self.cfg.set(key.lower(), value)  # ty: ignore[unresolved-attribute]

        def load(self):
            return self.app_uri

    options = {
        "bind": f"{args.host}:{args.port}",
        "workers": args.workers,
        "worker_class": "uvicorn_worker.UvicornWorker",
        "timeout": GUNICORN_TIMEOUT,
        "graceful_timeout": GUNICORN_GRACEFUL_TIMEOUT,
        "keepalive": GUNICORN_KEEPALIVE,
    }

    StandaloneApplication("rossum_agent.api.main:app", options).run()


def main() -> None:
    """CLI entry point for the API server."""
    parser = argparse.ArgumentParser(description="Run the Rossum Agent API server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes (default: 1)")
    parser.add_argument(
        "--server",
        choices=["uvicorn", "gunicorn"],
        default="uvicorn",
        help="Server backend to use (default: uvicorn)",
    )

    args = parser.parse_args()

    if args.server == "gunicorn":
        _run_gunicorn(args)
    else:
        _run_uvicorn(args)


if __name__ == "__main__":
    main()
