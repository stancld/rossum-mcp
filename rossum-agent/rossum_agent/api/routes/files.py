"""File management endpoints for chat sessions."""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003 - Required at runtime for service getter type hints
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
    """List all files for a chat session.

    Args:
        chat_id: Chat session identifier.
        credentials: Validated Rossum credentials.
        chat_service: Chat service instance.
        file_service: File service instance.

    Returns:
        FileListResponse with list of files and total count.

    Raises:
        HTTPException: If chat not found.
    """
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    files = file_service.list_files(chat_id)
    return FileListResponse(files=files, total=len(files))


@router.get("/{filename}")
async def download_file(
    chat_id: str,
    filename: str,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)] = None,  # type: ignore[assignment]
    chat_service: Annotated[ChatService, Depends(get_chat_service_dep)] = None,  # type: ignore[assignment]
    file_service: Annotated[FileService, Depends(get_file_service_dep)] = None,  # type: ignore[assignment]
) -> Response:
    """Download a file from a chat session.

    Args:
        chat_id: Chat session identifier.
        filename: Name of the file to download.
        credentials: Validated Rossum credentials.
        chat_service: Chat service instance.
        file_service: File service instance.

    Returns:
        File content with appropriate MIME type.

    Raises:
        HTTPException: If chat or file not found.
    """
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    result = file_service.get_file(chat_id, filename)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"File {filename} not found in chat {chat_id}"
        )

    content, mime_type = result
    return Response(
        content=content,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
