"""File management endpoints for chat sessions."""

from __future__ import annotations

import re
from collections.abc import Callable  # noqa: TC003 - Required at runtime for service getter type hints
from pathlib import Path
from typing import Annotated  # noqa: TC003 - Required at runtime for FastAPI dependency injection

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from rossum_agent.api.dependencies import RossumCredentials, get_validated_credentials
from rossum_agent.api.models.schemas import FileListResponse
from rossum_agent.api.services.chat_service import (
    ChatService,  # noqa: TC001 - Required at runtime for FastAPI Depends()
)
from rossum_agent.api.services.file_service import (
    FileService,  # noqa: TC001 - Required at runtime for FastAPI Depends()
)

router = APIRouter(prefix="/chats/{chat_id}/files", tags=["files"])

_get_chat_service: Callable[[], ChatService] | None = None
_get_file_service: Callable[[], FileService] | None = None


def set_chat_service_getter(getter: Callable[[], ChatService]) -> None:
    """Set the chat service getter function."""
    global _get_chat_service
    _get_chat_service = getter


def set_file_service_getter(getter: Callable[[], FileService]) -> None:
    """Set the file service getter function."""
    global _get_file_service
    _get_file_service = getter


def get_chat_service_dep() -> ChatService:
    """Dependency function for chat service."""
    if _get_chat_service is None:
        raise RuntimeError("Chat service getter not configured")
    return _get_chat_service()


def get_file_service_dep() -> FileService:
    """Dependency function for file service."""
    if _get_file_service is None:
        raise RuntimeError("File service getter not configured")
    return _get_file_service()


@router.get("", response_model=FileListResponse)
async def list_files(
    chat_id: str,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)] = None,  # type: ignore[assignment]
    chat_service: Annotated[ChatService, Depends(get_chat_service_dep)] = None,  # type: ignore[assignment]
    file_service: Annotated[FileService, Depends(get_file_service_dep)] = None,  # type: ignore[assignment]
) -> FileListResponse:
    """List all files for a chat session."""
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    files = file_service.list_files(chat_id)
    return FileListResponse(files=files, total=len(files))


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and header injection.

    - Normalizes Windows backslash separators to forward slashes
    - Extracts only the base filename (no directory traversal)
    - Removes control characters, newlines, quotes, and backslashes (header injection prevention)
    - Rejects directory-only names like ".." or "."
    - Limits length to prevent DoS
    """
    normalized = filename.replace("\\", "/")
    safe_name = Path(normalized).name
    safe_name = re.sub(r'[\x00-\x1f\x7f"\\]', "", safe_name)
    if safe_name in ("", ".", ".."):
        return ""
    return safe_name[:255]


@router.get("/{filename:path}")
async def download_file(
    chat_id: str,
    filename: str,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)] = None,  # type: ignore[assignment]
    chat_service: Annotated[ChatService, Depends(get_chat_service_dep)] = None,  # type: ignore[assignment]
    file_service: Annotated[FileService, Depends(get_file_service_dep)] = None,  # type: ignore[assignment]
) -> Response:
    """Download a file from a chat session."""
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    safe_filename = _sanitize_filename(filename)
    if not safe_filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")

    result = file_service.get_file(chat_id, safe_filename)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"File {safe_filename} not found in chat {chat_id}"
        )

    content, mime_type = result
    return Response(
        content=content,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )
