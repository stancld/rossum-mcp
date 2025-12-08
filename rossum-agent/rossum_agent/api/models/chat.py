"""Chat-related Pydantic models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ChatCreateRequest(BaseModel):
    """Request to create a new chat session."""

    api_token: str
    api_base_url: str
    mcp_mode: Literal["read-only", "read-write"] = "read-only"


class ChatCreateResponse(BaseModel):
    """Response after creating a chat session."""

    chat_id: str


class ChatMessage(BaseModel):
    """A single chat message."""

    role: Literal["user", "assistant"]
    content: str


class ChatHistoryResponse(BaseModel):
    """Response containing chat history."""

    chat_id: str
    messages: list[ChatMessage]
