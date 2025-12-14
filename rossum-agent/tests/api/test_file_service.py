"""Tests for FileService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from rossum_agent.api.models.schemas import FileInfo
from rossum_agent.api.services.file_service import FileService


@pytest.fixture
def mock_storage():
    """Create a mock RedisStorage."""
    return MagicMock()


@pytest.fixture
def file_service(mock_storage):
    """Create FileService with mock storage."""
    return FileService(redis_storage=mock_storage)


class TestListFiles:
    """Tests for FileService.list_files."""

    def test_list_files_empty(self, file_service, mock_storage):
        """Test listing files when none exist."""
        mock_storage.list_files.return_value = []

        result = file_service.list_files("chat_123")

        assert result == []
        mock_storage.list_files.assert_called_once_with("chat_123")

    def test_list_files_with_results(self, file_service, mock_storage):
        """Test listing files with results."""
        mock_storage.list_files.return_value = [
            {"filename": "chart.html", "size": 1234, "timestamp": "2024-12-09T14:30:00Z"},
            {"filename": "data.csv", "size": 567, "timestamp": "2024-12-09T14:35:00Z"},
        ]

        result = file_service.list_files("chat_123")

        assert len(result) == 2
        assert isinstance(result[0], FileInfo)
        assert result[0].filename == "chart.html"
        assert result[0].size == 1234
        assert result[0].mime_type == "text/html"
        assert result[1].filename == "data.csv"
        assert result[1].mime_type == "text/csv"


class TestGetFile:
    """Tests for FileService.get_file."""

    def test_get_file_success(self, file_service, mock_storage):
        """Test getting a file successfully."""
        mock_storage.load_file.return_value = b"<html>content</html>"

        result = file_service.get_file("chat_123", "chart.html")

        assert result is not None
        content, mime_type = result
        assert content == b"<html>content</html>"
        assert mime_type == "text/html"
        mock_storage.load_file.assert_called_once_with("chat_123", "chart.html")

    def test_get_file_not_found(self, file_service, mock_storage):
        """Test getting a non-existent file."""
        mock_storage.load_file.return_value = None

        result = file_service.get_file("chat_123", "missing.html")

        assert result is None

    def test_get_file_mime_type_detection(self, file_service, mock_storage):
        """Test MIME type detection for various file types."""
        mock_storage.load_file.return_value = b"content"

        test_cases = [
            ("file.html", "text/html"),
            ("file.json", "application/json"),
            ("file.csv", "text/csv"),
            ("file.png", "image/png"),
            ("file.pdf", "application/pdf"),
            ("file.unknown", "application/octet-stream"),
        ]

        for filename, expected_mime in test_cases:
            result = file_service.get_file("chat_123", filename)
            assert result is not None
            _, mime_type = result
            assert mime_type == expected_mime, f"Failed for {filename}"
