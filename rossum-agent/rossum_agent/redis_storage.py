"""Redis-based chat persistence."""

from __future__ import annotations

import base64
import datetime as dt
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import redis

logger = logging.getLogger(__name__)


def extract_text_from_content(content: str | list[dict[str, Any]] | None) -> str:
    """Extract text from message content which can be a string or multimodal list.

    Args:
        content: Message content - either a string or list of content blocks.

    Returns:
        Extracted text as a string.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return " ".join(text_parts)
    return ""


def get_commit_sha() -> str | None:
    """Get the current git commit SHA.

    Returns:
        Short commit SHA or None if not in a git repository.
    """
    try:
        git_executable = shutil.which("git")
        if not git_executable:
            return None
        result = subprocess.run(
            [git_executable, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        logger.debug("Failed to get git commit SHA")
    return None


@dataclass
class ChatMetadata:
    """Metadata for a chat session."""

    commit_sha: str | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tool_calls: int = 0
    total_steps: int = 0
    mcp_mode: str = "read-only"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "commit_sha": self.commit_sha,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tool_calls": self.total_tool_calls,
            "total_steps": self.total_steps,
            "mcp_mode": self.mcp_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatMetadata:
        """Create from dictionary."""
        return cls(
            commit_sha=data.get("commit_sha"),
            total_input_tokens=data.get("total_input_tokens", 0),
            total_output_tokens=data.get("total_output_tokens", 0),
            total_tool_calls=data.get("total_tool_calls", 0),
            total_steps=data.get("total_steps", 0),
            mcp_mode=data.get("mcp_mode", "read-only"),
        )


@dataclass
class ChatData:
    """Data structure for chat storage results."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    output_dir: str | None = None
    metadata: ChatMetadata = field(default_factory=ChatMetadata)


class RedisStorage:
    """Redis storage for chat conversations."""

    def __init__(self, host: str | None = None, port: int | None = None, ttl_days: int = 30) -> None:
        """Initialize Redis storage.

        Args:
            host: Redis host (defaults to REDIS_HOST env var or 'localhost')
            port: Redis port (defaults to REDIS_PORT env var or 6379)
            ttl_days: Time-to-live for chat data in days (default: 30)
        """
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = int(port if port is not None else int(os.getenv("REDIS_PORT", "6379")))
        self.ttl = dt.timedelta(days=ttl_days)
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.Redis(
                host=self.host, port=self.port, decode_responses=False, socket_connect_timeout=5
            )
        return self._client

    def save_chat(
        self,
        user_id: str | None,
        chat_id: str,
        messages: list[dict[str, Any]],
        output_dir: str | Path | None = None,
        metadata: ChatMetadata | None = None,
    ) -> bool:
        try:
            key = self._get_chat_key(user_id, chat_id)
            payload = {
                "messages": messages,
                "output_dir": str(output_dir) if output_dir else None,
                "metadata": metadata.to_dict() if metadata else ChatMetadata().to_dict(),
            }
            value = json.dumps(payload).encode("utf-8")
            self.client.setex(key, self.ttl, value)

            files_saved = 0
            if output_dir:
                output_path = Path(output_dir) if isinstance(output_dir, str) else output_dir
                files_saved = self.save_all_files(chat_id, output_path)

            logger.info(
                f"Saved chat {chat_id} to Redis "
                f"(messages={len(messages)}, user: {user_id or 'shared'}, files={files_saved})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save chat {chat_id}: {e}", exc_info=True)
            return False

    def load_chat(self, user_id: str | None, chat_id: str, output_dir: Path | None = None) -> ChatData | None:
        """Load chat from Redis and restore files to output directory.

        Args:
            user_id: Optional user identifier
            chat_id: Chat identifier
            output_dir: Directory to restore files to. If None, a new temp directory is created.

        Returns:
            ChatData containing messages, output_dir, and metadata, or None if chat not found
        """
        try:
            key = self._get_chat_key(user_id, chat_id)
            value = self.client.get(key)
            if value is None:
                logger.info(f"Chat {chat_id} not found in Redis (user: {user_id or 'shared'})")
                return None

            data = json.loads(cast("bytes", value).decode("utf-8"))
            messages = data if isinstance(data, list) else data.get("messages", [])
            stored_output_dir = data.get("output_dir") if isinstance(data, dict) else None
            metadata_dict = data.get("metadata", {}) if isinstance(data, dict) else {}
            metadata = ChatMetadata.from_dict(metadata_dict)

            files_loaded = 0
            if output_dir:
                files_loaded = self.load_all_files(chat_id, output_dir)

            logger.info(
                f"Loaded chat {chat_id} from Redis "
                f"({len(messages)} messages, {files_loaded} files, user: {user_id or 'shared'})"
            )
            return ChatData(messages=messages, output_dir=stored_output_dir, metadata=metadata)
        except Exception as e:
            logger.error(f"Failed to load chat {chat_id}: {e}", exc_info=True)
            return None

    def delete_chat(self, user_id: str | None, chat_id: str) -> bool:
        try:
            key = self._get_chat_key(user_id, chat_id)
            deleted = self.client.delete(key)
            logger.info(f"Deleted chat {chat_id} from Redis (deleted={deleted}, user: {user_id or 'shared'})")
            return bool(deleted)
        except Exception as e:
            logger.error(f"Failed to delete chat {chat_id}: {e}", exc_info=True)
            return False

    def chat_exists(self, user_id: str | None, chat_id: str) -> bool:
        try:
            key = self._get_chat_key(user_id, chat_id)
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Failed to check if chat {chat_id} exists: {e}", exc_info=True)
            return False

    def is_connected(self) -> bool:
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    def _get_chat_key(self, user_id: str | None, chat_id: str) -> str:
        """Generate Redis key for a chat.

        Args:
            user_id: Optional user identifier
            chat_id: Chat identifier

        Returns:
            Redis key string
        """
        if user_id:
            return f"user:{user_id}:chat:{chat_id}"
        return f"chat:{chat_id}"

    def _get_chat_pattern(self, user_id: str | None = None) -> str:
        """Generate Redis key pattern for listing chats.

        Args:
            user_id: Optional user identifier

        Returns:
            Redis key pattern string
        """
        if user_id:
            return f"user:{user_id}:chat:*"
        return "chat:*"

    def list_all_chats(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """List all chat conversations with metadata.

        Args:
            user_id: Optional user ID to filter chats (None = all chats or shared chats)

        Returns:
            List of dicts with chat_id, timestamp, message_count, first_message,
            and metadata (commit_sha, total_input_tokens, total_output_tokens,
            total_tool_calls, total_steps)
        """
        try:
            pattern = self._get_chat_pattern(user_id)
            keys = cast("list[bytes]", self.client.keys(pattern.encode("utf-8")))
            chats = []

            for key in keys:
                key_str = key.decode("utf-8")
                chat_id = key_str.replace(f"user:{user_id}:chat:", "") if user_id else key_str.replace("chat:", "")

                chat_data = self.load_chat(user_id, chat_id)

                if chat_data:
                    messages = chat_data.messages
                    timestamp_str = chat_id.split("_")[1]
                    timestamp = int(dt.datetime.strptime(timestamp_str, "%Y%m%d%H%M%S").timestamp())
                    first_message_content = messages[0].get("content") if messages else None
                    first_message = extract_text_from_content(first_message_content)
                    first_user_content = next(
                        (m.get("content") for m in messages if m.get("role") == "user"),
                        None,
                    )
                    first_user = extract_text_from_content(first_user_content)
                    preview = first_user[:100] if first_user else None

                    chats.append(
                        {
                            "chat_id": chat_id,
                            "timestamp": timestamp,
                            "message_count": len(messages),
                            "first_message": first_message[:100],
                            "preview": preview,
                            "commit_sha": chat_data.metadata.commit_sha,
                            "total_input_tokens": chat_data.metadata.total_input_tokens,
                            "total_output_tokens": chat_data.metadata.total_output_tokens,
                            "total_tool_calls": chat_data.metadata.total_tool_calls,
                            "total_steps": chat_data.metadata.total_steps,
                        }
                    )

            chats.sort(key=lambda x: x["timestamp"], reverse=True)
            logger.info(f"Found {len(chats)} chats in Redis (user: {user_id or 'shared'})")
            return chats
        except Exception as e:
            logger.error(f"Failed to list chats: {e}", exc_info=True)
            return []

    def save_file(self, chat_id: str, file_path: Path | str, content: bytes | None = None) -> bool:
        """Save a file to Redis associated with a chat session.

        Args:
            chat_id: Chat session ID
            file_path: Path to the file (or filename)
            content: Optional file content as bytes. If not provided, reads from file_path

        Returns:
            True if successful, False otherwise
        """
        try:
            if isinstance(file_path, str):
                file_path = Path(file_path)

            filename = file_path.name
            key = f"file:{chat_id}:{filename}"

            if content is None:
                if not file_path.exists():
                    logger.error(f"File not found: {file_path}")
                    return False
                content = file_path.read_bytes()

            # Store file with metadata
            metadata = {
                "filename": filename,
                "size": len(content),
                "timestamp": dt.datetime.now(dt.UTC).isoformat(),
                "content": base64.b64encode(content).decode("utf-8"),
            }

            value = json.dumps(metadata).encode("utf-8")
            self.client.setex(key, self.ttl, value)
            logger.info(f"Saved file {filename} for chat {chat_id} to Redis ({len(content)} bytes)")
            return True
        except Exception as e:
            logger.error(f"Failed to save file {filename} for chat {chat_id}: {e}", exc_info=True)
            return False

    def load_file(self, chat_id: str, filename: str) -> bytes | None:
        """Load a file from Redis for a chat session.

        Args:
            chat_id: Chat session ID
            filename: Name of the file to load

        Returns:
            File content as bytes, or None if not found
        """
        try:
            key = f"file:{chat_id}:{filename}"
            value = self.client.get(key)
            if value is None:
                logger.info(f"File {filename} not found for chat {chat_id}")
                return None

            metadata: dict[str, Any] = json.loads(cast("bytes", value).decode("utf-8"))
            content = base64.b64decode(metadata["content"])
            logger.info(f"Loaded file {filename} for chat {chat_id} ({len(content)} bytes)")
            return content
        except Exception as e:
            logger.error(f"Failed to load file {filename} for chat {chat_id}: {e}", exc_info=True)
            return None

    def list_files(self, chat_id: str) -> list[dict[str, Any]]:
        """List all files for a chat session.

        Args:
            chat_id: Chat session ID

        Returns:
            List of dicts with filename, size, and timestamp
        """
        try:
            pattern = f"file:{chat_id}:*"
            keys = cast("list[bytes]", self.client.keys(pattern.encode("utf-8")))
            files = []

            for key in keys:
                key_str = key.decode("utf-8")
                filename = key_str.split(":")[-1]
                value = self.client.get(key)
                if value:
                    metadata: dict[str, Any] = json.loads(cast("bytes", value).decode("utf-8"))
                    files.append(
                        {
                            "filename": filename,
                            "size": metadata.get("size", 0),
                            "timestamp": metadata.get("timestamp", ""),
                        }
                    )

            logger.info(f"Found {len(files)} files for chat {chat_id}")
            return files
        except Exception as e:
            logger.error(f"Failed to list files for chat {chat_id}: {e}", exc_info=True)
            return []

    def delete_file(self, chat_id: str, filename: str) -> bool:
        """Delete a file from Redis for a chat session.

        Args:
            chat_id: Chat session ID
            filename: Name of the file to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            key = f"file:{chat_id}:{filename}"
            deleted = self.client.delete(key)
            logger.info(f"Deleted file {filename} for chat {chat_id} (deleted={deleted})")
            return bool(deleted)
        except Exception as e:
            logger.error(f"Failed to delete file {filename} for chat {chat_id}: {e}", exc_info=True)
            return False

    def delete_all_files(self, chat_id: str) -> int:
        """Delete all files for a chat session.

        Args:
            chat_id: Chat session ID

        Returns:
            Number of files deleted
        """
        try:
            pattern = f"file:{chat_id}:*"
            keys = cast("list[bytes]", self.client.keys(pattern.encode("utf-8")))
            if not keys:
                logger.info(f"No files to delete for chat {chat_id}")
                return 0

            deleted = cast("int", self.client.delete(*keys))
            logger.info(f"Deleted {deleted} files for chat {chat_id}")
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete files for chat {chat_id}: {e}", exc_info=True)
            return 0

    def save_all_files(self, chat_id: str, output_dir: Path) -> int:
        """Save all files from output directory to Redis.

        Args:
            chat_id: Chat session ID
            output_dir: Directory containing files to save

        Returns:
            Number of files saved successfully
        """
        saved_count = 0
        try:
            if not output_dir.exists() or not output_dir.is_dir():
                logger.warning(f"Output directory does not exist: {output_dir}")
                return 0

            files = [f for f in output_dir.iterdir() if f.is_file()]
            for file_path in files:
                if self.save_file(chat_id, file_path):
                    saved_count += 1

            logger.info(f"Saved {saved_count}/{len(files)} files for chat {chat_id} to Redis")
            return saved_count
        except Exception as e:
            logger.error(f"Failed to save files for chat {chat_id}: {e}", exc_info=True)
            return saved_count

    def load_all_files(self, chat_id: str, output_dir: Path) -> int:
        """Load all files from Redis to output directory.

        Args:
            chat_id: Chat session ID
            output_dir: Directory where files will be restored

        Returns:
            Number of files loaded successfully
        """
        loaded_count = 0
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            files = self.list_files(chat_id)

            for file_info in files:
                filename = file_info["filename"]
                content = self.load_file(chat_id, filename)
                if content:
                    file_path = output_dir / filename
                    file_path.write_bytes(content)
                    loaded_count += 1

            logger.info(f"Loaded {loaded_count}/{len(files)} files for chat {chat_id} from Redis")
            return loaded_count
        except Exception as e:
            logger.error(f"Failed to load files for chat {chat_id}: {e}", exc_info=True)
            return loaded_count

    def close(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("Closed Redis connection")
