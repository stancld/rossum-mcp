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


class TestUploadFile:
    """Tests for FileService.upload_file."""

    def test_upload_file_success(self, file_service, mock_storage):
        """Test uploading a file successfully."""
        mock_storage.save_file.return_value = True
        mock_storage.list_files.return_value = [
            {"filename": "test.html", "size": 100, "timestamp": "2024-12-09T14:30:00Z"}
        ]

        result = file_service.upload_file(chat_id="chat_123", filename="test.html", content=b"<html></html>")

        assert result is not None
        assert result.filename == "test.html"
        assert result.mime_type == "text/html"

    def test_upload_file_too_large(self, file_service, mock_storage):
        """Test uploading a file that exceeds size limit."""
        large_content = b"x" * (FileService.MAX_FILE_SIZE + 1)

        with pytest.raises(ValueError) as exc_info:
            file_service.upload_file(chat_id="chat_123", filename="large.txt", content=large_content)

        assert "exceeds maximum" in str(exc_info.value)

    def test_upload_file_disallowed_type(self, file_service, mock_storage):
        """Test uploading a file with disallowed MIME type."""
        with pytest.raises(ValueError) as exc_info:
            file_service.upload_file(chat_id="chat_123", filename="script.exe", content=b"binary content")

        assert "not allowed" in str(exc_info.value)

    def test_upload_file_storage_failure(self, file_service, mock_storage):
        """Test upload failure from storage."""
        mock_storage.save_file.return_value = False

        result = file_service.upload_file(chat_id="chat_123", filename="test.html", content=b"<html></html>")

        assert result is None


class TestDeleteFile:
    """Tests for FileService.delete_file."""

    def test_delete_file_success(self, file_service, mock_storage):
        """Test deleting a file successfully."""
        mock_storage.delete_file.return_value = True

        result = file_service.delete_file("chat_123", "test.html")

        assert result is True
        mock_storage.delete_file.assert_called_once_with("chat_123", "test.html")

    def test_delete_file_not_found(self, file_service, mock_storage):
        """Test deleting a non-existent file."""
        mock_storage.delete_file.return_value = False

        result = file_service.delete_file("chat_123", "missing.html")

        assert result is False


class TestFileExists:
    """Tests for FileService.file_exists."""

    def test_file_exists_true(self, file_service, mock_storage):
        """Test checking if file exists when it does."""
        mock_storage.load_file.return_value = b"content"

        result = file_service.file_exists("chat_123", "test.html")

        assert result is True

    def test_file_exists_false(self, file_service, mock_storage):
        """Test checking if file exists when it doesn't."""
        mock_storage.load_file.return_value = None

        result = file_service.file_exists("chat_123", "missing.html")

        assert result is False


class TestSanitizeFilename:
    """Tests for FileService._sanitize_filename."""

    def test_sanitize_simple_filename(self, file_service):
        """Test sanitizing a simple filename."""
        result = file_service._sanitize_filename("test.html")

        assert result == "test.html"

    def test_sanitize_path_traversal(self, file_service):
        """Test sanitizing path traversal attempts."""
        result = file_service._sanitize_filename("../../../etc/passwd")

        assert ".." not in result
        assert "/" not in result

    def test_sanitize_absolute_path(self, file_service):
        """Test sanitizing absolute paths."""
        result = file_service._sanitize_filename("/etc/passwd")

        assert result == "passwd"

    def test_sanitize_windows_path(self, file_service):
        """Test sanitizing Windows paths."""
        result = file_service._sanitize_filename("C:\\Windows\\test.txt")

        assert "\\" not in result

    def test_sanitize_hidden_file(self, file_service):
        """Test sanitizing hidden files."""
        result = file_service._sanitize_filename(".hidden")

        assert not result.startswith(".")

    def test_sanitize_null_bytes(self, file_service):
        """Test sanitizing null bytes."""
        result = file_service._sanitize_filename("test\x00.html")

        assert "\x00" not in result
