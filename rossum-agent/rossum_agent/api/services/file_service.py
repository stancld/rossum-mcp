"""File service for managing chat session files."""

from __future__ import annotations

import mimetypes
from typing import TYPE_CHECKING

from rossum_agent.api.models.schemas import FileInfo

if TYPE_CHECKING:
    from rossum_agent.postgres_storage import PostgresStorage


class FileService:
    """Wraps storage file operations with MIME type detection."""

    def __init__(self, storage: PostgresStorage) -> None:
        self._storage = storage

    @property
    def storage(self) -> PostgresStorage:
        return self._storage

    def list_files(self, chat_id: str) -> list[FileInfo]:
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
        if (content := self._storage.load_file(chat_id, filename)) is None:
            return None
        return content, self._guess_mime_type(filename)

    def _guess_mime_type(self, filename: str) -> str:
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"
