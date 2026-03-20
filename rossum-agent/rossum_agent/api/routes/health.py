"""Health check endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from rossum_agent.api.dependencies import get_chat_service
from rossum_agent.api.models.schemas import HealthResponse
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.api.shutdown import shutdown_state

router = APIRouter(tags=["health"])

VERSION = "0.2.0"


@router.get("/health", response_model=HealthResponse)
async def health_check(
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> JSONResponse:
    """Check API health and dependencies."""
    storage_connected = chat_service.is_connected()

    if shutdown_state.shutting_down:
        health_status = "shutting_down"
    elif storage_connected:
        health_status = "healthy"
    else:
        health_status = "unhealthy"

    body = HealthResponse(
        status=health_status,
        storage_connected=storage_connected,
        storage_backend="postgres",
        version=VERSION,
    )

    status_code = 503 if shutdown_state.shutting_down else 200
    return JSONResponse(content=body.model_dump(), status_code=status_code)
