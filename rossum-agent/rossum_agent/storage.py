"""Storage protocol and shared data types for chat persistence backends."""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from rossum_agent.api.models.schemas import Persona

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any, Literal

STORAGE_BACKEND_ENV = "CHAT_STORAGE_BACKEND"
DEFAULT_STORAGE_BACKEND = "postgres"
CHAT_ID_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"


def get_storage_backend() -> str:
    """Return the configured storage backend name."""
    return os.getenv(STORAGE_BACKEND_ENV, DEFAULT_STORAGE_BACKEND)


def extract_text_from_content(content: str | list[dict[str, Any]] | None) -> str:
    """Extract text from message content which can be a string or multimodal list."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def _preview_from_first_msg(msg: dict[str, Any] | None) -> str:
    """Extract preview text from a single message dict."""
    if not msg:
        return ""
    if msg.get("type") == "task_step":
        return msg.get("task", "")
    if msg.get("role") == "user":
        return extract_text_from_content(msg.get("content"))
    return ""


def _extract_first_user_text(messages: list[dict[str, Any]]) -> str:
    """Extract text from the first user message, handling both legacy and task_step formats."""
    for msg in messages:
        if text := _preview_from_first_msg(msg):
            return text
    return ""


@dataclass
class ChatMetadata:
    """Metadata for a chat session."""

    commit_sha: str | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tool_calls: int = 0
    total_steps: int = 0
    mcp_mode: Literal["read-only", "read-write"] = "read-only"
    persona: Persona = Persona.DEFAULT
    config_commits: list[str] = field(default_factory=list)
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "commit_sha": self.commit_sha,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tool_calls": self.total_tool_calls,
            "total_steps": self.total_steps,
            "mcp_mode": self.mcp_mode,
            "persona": self.persona,
            "config_commits": self.config_commits,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatMetadata:
        return cls(
            commit_sha=data.get("commit_sha"),
            total_input_tokens=data.get("total_input_tokens", 0),
            total_output_tokens=data.get("total_output_tokens", 0),
            total_tool_calls=data.get("total_tool_calls", 0),
            total_steps=data.get("total_steps", 0),
            mcp_mode=data.get("mcp_mode", "read-only"),
            persona=Persona(data.get("persona", "default")),
            config_commits=data.get("config_commits", []),
            summary=data.get("summary"),
        )


@dataclass
class ChatData:
    """Data structure for chat storage results."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    output_dir: str | None = None
    metadata: ChatMetadata = field(default_factory=ChatMetadata)


def _build_chat_list_item(
    chat_id: str,
    message_count: int,
    first_message_preview: str,
    metadata: ChatMetadata,
) -> dict[str, Any]:
    """Build a standardized chat list item dict from common fields."""
    timestamp_str = chat_id.split("_")[1]
    timestamp = int(dt.datetime.strptime(timestamp_str, CHAT_ID_TIMESTAMP_FORMAT).timestamp())
    preview = first_message_preview[:100]
    return {
        "chat_id": chat_id,
        "timestamp": timestamp,
        "message_count": message_count,
        "first_message": preview,
        "preview": preview or None,
        "commit_sha": metadata.commit_sha,
        "total_input_tokens": metadata.total_input_tokens,
        "total_output_tokens": metadata.total_output_tokens,
        "total_tool_calls": metadata.total_tool_calls,
        "total_steps": metadata.total_steps,
        "summary": metadata.summary,
    }


@runtime_checkable
class ChatStorage(Protocol):
    """Protocol defining the interface for chat persistence backends."""

    def save_chat(
        self,
        user_id: str | None,
        chat_id: str,
        messages: list[dict[str, Any]],
        output_dir: str | Path | None = None,
        metadata: ChatMetadata | None = None,
    ) -> bool: ...

    def load_chat(self, user_id: str | None, chat_id: str, output_dir: Path | None = None) -> ChatData | None: ...

    def delete_chat(self, user_id: str | None, chat_id: str) -> bool: ...

    def chat_exists(self, user_id: str | None, chat_id: str) -> bool: ...

    def is_connected(self) -> bool: ...

    def list_all_chats(self, user_id: str | None = None) -> list[dict[str, Any]]: ...

    def save_file(self, chat_id: str, file_path: Path | str, content: bytes | None = None) -> bool: ...

    def load_file(self, chat_id: str, filename: str) -> bytes | None: ...

    def list_files(self, chat_id: str) -> list[dict[str, Any]]: ...

    def delete_file(self, chat_id: str, filename: str) -> bool: ...

    def delete_all_files(self, chat_id: str) -> int: ...

    def save_all_files(self, chat_id: str, output_dir: Path) -> int: ...

    def load_all_files(self, chat_id: str, output_dir: Path) -> int: ...

    def save_feedback(self, user_id: str | None, chat_id: str, turn_index: int, is_positive: bool) -> bool: ...

    def get_feedback(self, user_id: str | None, chat_id: str) -> dict[int, bool]: ...

    def delete_feedback(self, user_id: str | None, chat_id: str, turn_index: int) -> bool: ...

    def delete_all_feedback(self, user_id: str | None, chat_id: str) -> bool: ...

    def close(self) -> None: ...
