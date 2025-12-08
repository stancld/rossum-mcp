"""WebSocket message Pydantic models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Error response for WebSocket."""

    type: Literal["error"] = "error"
    message: str


class CompleteResponse(BaseModel):
    """Completion response for WebSocket."""

    type: Literal["complete"] = "complete"
    chat_id: str


class WSPromptMessage(BaseModel):
    """WebSocket message containing a user prompt."""

    type: Literal["prompt"]
    content: str


class WSConfigMessage(BaseModel):
    """WebSocket message for initial configuration."""

    type: Literal["config"]
    api_token: str
    api_base_url: str
    mcp_mode: Literal["read-only", "read-write"] = "read-only"
