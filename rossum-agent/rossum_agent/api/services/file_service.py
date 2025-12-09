"""File service for managing chat session files."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from rossum_agent.api.models.schemas import FileInfo
from rossum_agent.redis_storage import RedisStorage

logger = logging.getLogger(__name__)


class FileService:
    """Service for managing files associated with chat sessions.

    Wraps RedisStorage file operations with proper validation and
    data transformation to/from API schemas.
    """

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

    ALLOWED_MIME_TYPES = {
        "text/html",
        "text/plain",
        "text/csv",
        "application/json",
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/svg+xml",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

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

    def upload_file(self, chat_id: str, filename: str, content: bytes) -> FileInfo | None:
        """Upload a file to a chat session.

        Args:
            chat_id: Chat session identifier.
            filename: Name for the uploaded file.
            content: File content as bytes.

        Returns:
            FileInfo if uploaded successfully, None otherwise.
        """
        if len(content) > self.MAX_FILE_SIZE:
            raise ValueError(f"File size {len(content)} exceeds maximum allowed size {self.MAX_FILE_SIZE}")

        mime_type = self._guess_mime_type(filename)
        if mime_type not in self.ALLOWED_MIME_TYPES:
            raise ValueError(
                f"MIME type {mime_type} is not allowed. Allowed types: {', '.join(sorted(self.ALLOWED_MIME_TYPES))}"
            )

        sanitized_filename = self._sanitize_filename(filename)

        success = self._storage.save_file(chat_id=chat_id, file_path=Path(sanitized_filename), content=content)

        if not success:
            return None

        for f in self._storage.list_files(chat_id):
            if f["filename"] == sanitized_filename:
                return FileInfo(filename=f["filename"], size=f["size"], timestamp=f["timestamp"], mime_type=mime_type)

        return FileInfo(filename=sanitized_filename, size=len(content), timestamp="", mime_type=mime_type)

    def delete_file(self, chat_id: str, filename: str) -> bool:
        """Delete a file from a chat session.

        Args:
            chat_id: Chat session identifier.
            filename: Name of the file to delete.

        Returns:
            True if deleted, False otherwise.
        """
        return self._storage.delete_file(chat_id, filename)

    def file_exists(self, chat_id: str, filename: str) -> bool:
        """Check if a file exists in a chat session.

        Args:
            chat_id: Chat session identifier.
            filename: Name of the file.
        """
        return self._storage.load_file(chat_id, filename) is not None

    def _guess_mime_type(self, filename: str) -> str:
        """Guess MIME type from filename."""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage.

        Removes path components and dangerous characters.
        """
        name = Path(filename).name

        name = name.replace("..", "").replace("/", "_").replace("\\", "_").replace("\x00", "")

        if not name or name.startswith("."):
            name = f"file_{name}"

        return name
