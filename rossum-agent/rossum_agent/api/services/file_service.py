"""File service for managing chat session files."""

from __future__ import annotations

import mimetypes

from rossum_agent.api.models.schemas import FileInfo
from rossum_agent.redis_storage import RedisStorage


class FileService:
    """Service for managing files associated with chat sessions.

    Wraps RedisStorage file operations with proper validation and
    data transformation to/from API schemas.
    """

    def __init__(self, redis_storage: RedisStorage | None = None) -> None:
        self._storage = redis_storage or RedisStorage()

    @property
    def storage(self) -> RedisStorage:
        """Get the underlying RedisStorage instance."""
        return self._storage

    def list_files(self, chat_id: str) -> list[FileInfo]:
        """List all files for a chat session.

        Args:
            chat_id: Chat session identifier.

        Returns:
            List of FileInfo objects with file metadata.
        """
        files_data = self._storage.list_files(chat_id)
        return [
            FileInfo(
                filename=f["filename"],
                size=f["size"],
                timestamp=f["timestamp"],
                mime_type=self._guess_mime_type(f["filename"]),
            )
            for f in files_data
        ]

    def get_file(self, chat_id: str, filename: str) -> tuple[bytes, str] | None:
        """Get file content and MIME type.

        Args:
            chat_id: Chat session identifier.
            filename: Name of the file.

        Returns:
            Tuple of (content bytes, mime_type) or None if not found.
        """
        if (content := self._storage.load_file(chat_id, filename)) is None:
            return None

        mime_type = self._guess_mime_type(filename)
        return content, mime_type

    def _guess_mime_type(self, filename: str) -> str:
        """Guess MIME type from filename."""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"
