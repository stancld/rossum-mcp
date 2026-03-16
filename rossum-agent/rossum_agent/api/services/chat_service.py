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
    Persona,
)
from rossum_agent.storage import ChatData, ChatMetadata

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any, Literal

    from rossum_agent.storage import ChatStorage

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chat sessions.

    Wraps a ChatStorage backend to provide chat CRUD operations with proper
    data transformation to/from API schemas.
    """

    def __init__(self, storage: ChatStorage) -> None:
        self._storage = storage

    @property
    def storage(self) -> ChatStorage:
        """Get the underlying storage instance."""
        return self._storage

    def is_connected(self) -> bool:
        """Check if storage backend is connected."""
        return self._storage.is_connected()

    def create_chat(
        self,
        user_id: str | None,
        mcp_mode: Literal["read-only", "read-write"] = "read-only",
        persona: Persona = Persona.DEFAULT,
    ) -> ChatResponse:
        timestamp = dt.datetime.now(dt.UTC)
        timestamp_str = timestamp.strftime("%Y%m%d%H%M%S")
        unique_suffix = secrets.token_hex(4)
        chat_id = f"chat_{timestamp_str}_{unique_suffix}"

        initial_messages: list[dict[str, Any]] = []
        metadata = ChatMetadata(mcp_mode=mcp_mode, persona=persona)
        self._storage.save_chat(user_id, chat_id, initial_messages, metadata=metadata)

        logger.info(
            f"Created chat {chat_id} for user {user_id or 'shared'} with mcp_mode={mcp_mode}, persona={persona}"
        )
        return ChatResponse(chat_id=chat_id, created_at=timestamp)

    def list_chats(self, user_id: str | None, limit: int = 50, offset: int = 0) -> ChatListResponse:
        all_chats = self._storage.list_all_chats(user_id)

        paginated = all_chats[offset : offset + limit]
        chats = [
            ChatSummary(
                chat_id=chat["chat_id"],
                timestamp=chat["timestamp"],
                message_count=chat["message_count"],
                first_message=chat["first_message"],
                preview=chat.get("preview"),
                summary=chat.get("summary"),
            )
            for chat in paginated
        ]

        return ChatListResponse(chats=chats, total=len(all_chats), limit=limit, offset=offset)

    def get_chat(self, user_id: str | None, chat_id: str) -> ChatDetail | None:
        if (chat_data := self._storage.load_chat(user_id, chat_id)) is None:
            return None

        messages = []
        for msg in chat_data.messages:
            msg_type = msg.get("type")
            role = msg.get("role")

            if msg_type == "task_step":
                task_content = msg.get("task", "")
                messages.append(Message(role="user", content=task_content, feedback=msg.get("feedback")))
            elif msg_type == "memory_step":
                text = msg.get("text")
                if text:
                    messages.append(Message(role="assistant", content=text, feedback=msg.get("feedback")))
            elif role in ("user", "assistant"):
                messages.append(Message(role=role, content=msg.get("content", ""), feedback=msg.get("feedback")))

        files_data = self._storage.list_files(chat_id)
        files = [FileInfo(filename=f["filename"], size=f["size"], timestamp=f["timestamp"]) for f in files_data]

        timestamp_str = chat_id.split("_")[1]
        created_at = dt.datetime.strptime(timestamp_str, "%Y%m%d%H%M%S").replace(tzinfo=dt.UTC)

        return ChatDetail(chat_id=chat_id, messages=messages, created_at=created_at, files=files)

    def delete_chat(self, user_id: str | None, chat_id: str) -> bool:
        self._storage.delete_all_files(chat_id)
        deleted = self._storage.delete_chat(user_id, chat_id)
        logger.info(f"Deleted chat {chat_id} for user {user_id or 'shared'}: {deleted}")
        return deleted

    def chat_exists(self, user_id: str | None, chat_id: str) -> bool:
        return self._storage.chat_exists(user_id, chat_id)

    def get_messages(self, user_id: str | None, chat_id: str) -> list[dict[str, Any]] | None:
        if (chat_data := self._storage.load_chat(user_id, chat_id)) is None:
            return None
        return chat_data.messages

    def get_chat_data(self, user_id: str | None, chat_id: str) -> ChatData | None:
        return self._storage.load_chat(user_id, chat_id)

    def save_messages(
        self,
        user_id: str | None,
        chat_id: str,
        messages: list[dict[str, Any]],
        output_dir: Path | None = None,
        metadata: ChatMetadata | None = None,
    ) -> bool:
        return self._storage.save_chat(user_id, chat_id, messages, output_dir, metadata)

    def save_feedback(self, user_id: str | None, chat_id: str, turn_index: int, is_positive: bool) -> bool:
        return self._storage.save_feedback(user_id, chat_id, turn_index, is_positive)

    def get_feedback(self, user_id: str | None, chat_id: str) -> dict[int, bool]:
        return self._storage.get_feedback(user_id, chat_id)

    def delete_feedback(self, user_id: str | None, chat_id: str, turn_index: int) -> bool:
        return self._storage.delete_feedback(user_id, chat_id, turn_index)
