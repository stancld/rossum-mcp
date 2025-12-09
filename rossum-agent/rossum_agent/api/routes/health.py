"""Health check endpoint."""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003 - Required at runtime for service getter type hints
from typing import Annotated  # noqa: TC003 - Required at runtime for FastAPI dependency injection

from fastapi import APIRouter, Depends

from rossum_agent.api.models.schemas import HealthResponse
from rossum_agent.api.services.chat_service import (
    ChatService,  # noqa: TC001 - Required at runtime for FastAPI Depends()
)

router = APIRouter(tags=["health"])

VERSION = "0.2.0"

_get_chat_service: Callable[[], ChatService] | None = None


def set_chat_service_getter(getter: Callable[[], ChatService]) -> None:
    """Set the chat service getter function."""
    global _get_chat_service
    _get_chat_service = getter


def get_chat_service_dep() -> ChatService:
    """Dependency function for chat service."""
    if _get_chat_service is None:
        raise RuntimeError("Chat service getter not configured")
    return _get_chat_service()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    chat_service: Annotated[ChatService, Depends(get_chat_service_dep)],
) -> HealthResponse:
    """Check API health and dependencies.

    Returns:
        HealthResponse with status and dependency states.
    """
    redis_connected = chat_service.is_connected()

    return HealthResponse(
        status="healthy" if redis_connected else "unhealthy", redis_connected=redis_connected, version=VERSION
    )
