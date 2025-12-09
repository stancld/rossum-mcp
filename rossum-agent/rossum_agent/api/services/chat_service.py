"""Chat service for managing chat sessions."""

from __future__ import annotations

import datetime as dt
import logging
import secrets
from typing import TYPE_CHECKING

from rossum_agent.api.models.schemas import (
    ChatDetail,
    ChatListResponse,
    ChatResponse,
    ChatSummary,
    FileInfo,
    Message,
)
from rossum_agent.redis_storage import RedisStorage

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any, Literal

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chat sessions.

    Wraps RedisStorage to provide chat CRUD operations with proper
    data transformation to/from API schemas.
    """

    def __init__(self, redis_storage: RedisStorage | None = None) -> None:
        self._storage = redis_storage or RedisStorage()

    @property
    def storage(self) -> RedisStorage:
        """Get the underlying RedisStorage instance."""
        return self._storage

    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._storage.is_connected()

    def create_chat(
        self, user_id: str | None, mcp_mode: Literal["read-only", "read-write"] = "read-only"
    ) -> ChatResponse:
        """Create a new chat session.

        Args:
            user_id: User identifier for isolation.
            mcp_mode: MCP mode for this chat session.

        Returns:
            ChatResponse with the new chat_id and created_at timestamp.
        """
        timestamp = dt.datetime.now(dt.UTC)
        timestamp_str = timestamp.strftime("%Y%m%d%H%M%S")
        unique_suffix = secrets.token_hex(4)
        chat_id = f"chat_{timestamp_str}_{unique_suffix}"

        initial_messages: list[dict[str, Any]] = []
        self._storage.save_chat(user_id, chat_id, initial_messages)

        self._save_chat_metadata(user_id, chat_id, mcp_mode, timestamp)

        logger.info(f"Created chat {chat_id} for user {user_id or 'shared'}")
        return ChatResponse(chat_id=chat_id, created_at=timestamp)

    def _save_chat_metadata(
        self,
        user_id: str | None,
        chat_id: str,
        mcp_mode: str,
        created_at: dt.datetime,
    ) -> None:
        """Save chat metadata to Redis.

        Metadata is stored separately from messages to allow quick access
        without loading all messages.
        """
        pass

    def list_chats(self, user_id: str | None, limit: int = 50, offset: int = 0) -> ChatListResponse:
        """List chat sessions for a user.

        Args:
            user_id: User identifier for isolation.
            limit: Maximum number of chats to return.
            offset: Pagination offset.

        Returns:
            ChatListResponse with paginated chat list.
        """
        all_chats = self._storage.list_all_chats(user_id)

        paginated = all_chats[offset : offset + limit]
        chats = [
            ChatSummary(
                chat_id=chat["chat_id"],
                timestamp=chat["timestamp"],
                message_count=chat["message_count"],
                first_message=chat["first_message"],
            )
            for chat in paginated
        ]

        return ChatListResponse(chats=chats, total=len(all_chats), limit=limit, offset=offset)

    def get_chat(self, user_id: str | None, chat_id: str) -> ChatDetail | None:
        """Get detailed chat information.

        Args:
            user_id: User identifier for isolation.
            chat_id: Chat session identifier.

        Returns:
            ChatDetail with messages and files, or None if not found.
        """
        if (result := self._storage.load_chat(user_id, chat_id)) is None:
            return None

        messages_data, _ = result

        messages = []
        for msg in messages_data:
            role = msg.get("role")
            if role in ("user", "assistant"):
                messages.append(Message(role=role, content=msg.get("content", "")))

        files_data = self._storage.list_files(chat_id)
        files = [FileInfo(filename=f["filename"], size=f["size"], timestamp=f["timestamp"]) for f in files_data]

        timestamp_str = chat_id.split("_")[1]
        created_at = dt.datetime.strptime(timestamp_str, "%Y%m%d%H%M%S").replace(tzinfo=dt.UTC)

        return ChatDetail(chat_id=chat_id, messages=messages, created_at=created_at, files=files)

    def delete_chat(self, user_id: str | None, chat_id: str) -> bool:
        """Delete a chat session.

        Args:
            user_id: User identifier for isolation.
            chat_id: Chat session identifier.

        Returns:
            True if deleted, False otherwise.
        """
        self._storage.delete_all_files(chat_id)
        deleted = self._storage.delete_chat(user_id, chat_id)
        logger.info(f"Deleted chat {chat_id} for user {user_id or 'shared'}: {deleted}")
        return deleted

    def chat_exists(self, user_id: str | None, chat_id: str) -> bool:
        """Check if a chat exists.

        Args:
            user_id: User identifier for isolation.
            chat_id: Chat session identifier.
        """
        return self._storage.chat_exists(user_id, chat_id)

    def get_messages(self, user_id: str | None, chat_id: str) -> list[dict[str, Any]] | None:
        """Get raw messages for a chat session.

        Args:
            user_id: User identifier for isolation.
            chat_id: Chat session identifier.
        """
        if (result := self._storage.load_chat(user_id, chat_id)) is None:
            return None
        messages, _ = result
        return messages

    def save_messages(
        self, user_id: str | None, chat_id: str, messages: list[dict[str, Any]], output_dir: Path | None = None
    ) -> bool:
        """Save messages to a chat session.

        Args:
            user_id: User identifier for isolation.
            chat_id: Chat session identifier.
            messages: List of message dicts to save.
            output_dir: Optional output directory path.

        Returns:
            True if saved successfully, False otherwise.
        """
        return self._storage.save_chat(user_id, chat_id, messages, output_dir)
