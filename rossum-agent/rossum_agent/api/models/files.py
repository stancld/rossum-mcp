"""File-related Pydantic models."""

from __future__ import annotations

from pydantic import BaseModel


class FileInfo(BaseModel):
    """Information about a generated file."""

    filename: str
    size: int
    timestamp: str


class FilesListResponse(BaseModel):
    """Response containing list of generated files."""

    chat_id: str
    files: list[FileInfo]
