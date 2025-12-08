"""REST API routes for rossum-agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

from rossum_agent.api.models import (
    ChatCreateRequest,
    ChatCreateResponse,
    ChatHistoryResponse,
    ChatMessage,
    FileInfo,
    FilesListResponse,
)
from rossum_agent.api.session import SessionManager  # noqa: TC001
from rossum_agent.redis_storage import RedisStorage  # noqa: TC001
from rossum_agent.utils import is_valid_chat_id

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@router.post("/api/chat", response_model=ChatCreateResponse)
async def create_chat(request: Request, body: ChatCreateRequest) -> ChatCreateResponse:
    """Create a new chat session."""
    session_manager: SessionManager = request.app.state.session_manager
    session = await session_manager.create_session(
        api_token=body.api_token,
        api_base_url=body.api_base_url,
        mcp_mode=body.mcp_mode,
    )
    return ChatCreateResponse(chat_id=session.chat_id)


@router.get("/api/chat/{chat_id}", response_model=ChatHistoryResponse)
async def get_chat_history(request: Request, chat_id: str) -> ChatHistoryResponse:
    """Get chat history for a session."""
    if not is_valid_chat_id(chat_id):
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    session_manager: SessionManager = request.app.state.session_manager
    session = await session_manager.get_session(chat_id)

    if session:
        messages = [
            ChatMessage(role=cast("Literal['user', 'assistant']", m["role"]), content=m["content"])
            for m in session.messages
        ]
        return ChatHistoryResponse(chat_id=chat_id, messages=messages)

    # Try loading from Redis
    storage: RedisStorage = request.app.state.storage
    if storage.is_connected():
        result = storage.load_chat(None, chat_id, None)
        if result:
            stored_messages, _ = result
            messages = [ChatMessage(role=m["role"], content=m["content"]) for m in stored_messages]
            return ChatHistoryResponse(chat_id=chat_id, messages=messages)

    raise HTTPException(status_code=404, detail="Chat not found")


@router.delete("/api/chat/{chat_id}")
async def delete_chat(request: Request, chat_id: str) -> dict[str, bool]:
    """Delete a chat session."""
    if not is_valid_chat_id(chat_id):
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    session_manager: SessionManager = request.app.state.session_manager
    await session_manager.remove_session(chat_id)

    storage: RedisStorage = request.app.state.storage
    if storage.is_connected():
        storage.delete_chat(None, chat_id)
        storage.delete_all_files(chat_id)

    return {"deleted": True}


@router.get("/api/chat/{chat_id}/files", response_model=FilesListResponse)
async def list_files(request: Request, chat_id: str) -> FilesListResponse:
    """List generated files for a chat session."""
    if not is_valid_chat_id(chat_id):
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    storage: RedisStorage = request.app.state.storage
    files_info = storage.list_files(chat_id)

    files = [
        FileInfo(
            filename=f["filename"],
            size=f.get("size", 0),
            timestamp=f.get("timestamp", ""),
        )
        for f in files_info
    ]

    return FilesListResponse(chat_id=chat_id, files=files)


@router.get("/api/chat/{chat_id}/files/{filename}")
async def download_file(request: Request, chat_id: str, filename: str) -> Response:
    """Download a generated file."""
    if not is_valid_chat_id(chat_id):
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    storage: RedisStorage = request.app.state.storage
    content = storage.load_file(chat_id, filename)

    if content is None:
        raise HTTPException(status_code=404, detail="File not found")

    # Determine content type based on extension
    ext = Path(filename).suffix.lower()
    content_types = {
        ".json": "application/json",
        ".csv": "text/csv",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".html": "text/html",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".pdf": "application/pdf",
    }
    content_type = content_types.get(ext, "application/octet-stream")

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/chats")
async def list_chats(request: Request, user_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """List all chat sessions."""
    storage: RedisStorage = request.app.state.storage
    if not storage.is_connected():
        return {"chats": []}

    chats = storage.list_all_chats(user_id)
    return {"chats": chats}


def get_index_route(static_dir: Path) -> APIRouter:
    """Create a router for serving the index.html."""
    index_router = APIRouter()

    @index_router.get("/")
    async def root() -> FileResponse:
        """Serve the test UI."""
        index_path = static_dir / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="Test UI not found")
        return FileResponse(index_path)

    return index_router
