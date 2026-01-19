"""Request models for Rossum Agent API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CreateChatRequest(BaseModel):
    """Request body for creating a new chat session."""

    mcp_mode: Literal["read-only", "read-write"] = "read-only"


class ImageContent(BaseModel):
    """Image content in a message."""

    type: Literal["image"] = "image"
    media_type: Literal["image/jpeg", "image/png", "image/gif", "image/webp"]
    data: str = Field(..., description="Base64-encoded image data")


class DocumentContent(BaseModel):
    """Document content in a message."""

    type: Literal["document"] = "document"
    media_type: Literal["application/pdf"] = "application/pdf"
    data: str = Field(..., description="Base64-encoded document data")
    filename: str = Field(..., description="Original filename of the document")


class MessageRequest(BaseModel):
    """Request body for sending a message."""

    content: str = Field(..., min_length=1, max_length=50000, description="Text content of the message")
    images: list[ImageContent] | None = Field(
        default=None,
        max_length=5,
        description="Optional list of images (max 5) to include with the message",
    )
    documents: list[DocumentContent] | None = Field(
        default=None,
        max_length=5,
        description="Optional list of PDF documents (max 5) to include with the message",
    )
    rossum_url: str | None = Field(default=None, description="Optional Rossum app URL for context")
