"""Integration tests for file API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from rossum_agent.api.main import app, mount_test_frontend
from rossum_agent.api.models.schemas import FileInfo
from rossum_agent.api.routes import chats, files, health, messages


@pytest.fixture
def mock_chat_service():
    """Create a mock ChatService."""
    return MagicMock()


@pytest.fixture
def mock_file_service():
    """Create a mock FileService."""
    return MagicMock()


@pytest.fixture
def mock_agent_service():
    """Create a mock AgentService."""
    return MagicMock()


@pytest.fixture
def client(mock_chat_service, mock_file_service, mock_agent_service):
    """Create test client with mocked services."""
    health.set_chat_service_getter(lambda: mock_chat_service)
    chats.set_chat_service_getter(lambda: mock_chat_service)
    messages.set_chat_service_getter(lambda: mock_chat_service)
    messages.set_agent_service_getter(lambda: mock_agent_service)
    files.set_chat_service_getter(lambda: mock_chat_service)
    files.set_file_service_getter(lambda: mock_file_service)

    mount_test_frontend()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def valid_headers():
    """Valid authentication headers."""
    return {"X-Rossum-Token": "test_token", "X-Rossum-Api-Url": "https://api.rossum.ai"}


def mock_httpx_success():
    """Helper to create mocked httpx client for successful auth."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": 12345}

    mock_async_client = AsyncMock()
    mock_async_client.get = AsyncMock(return_value=mock_response)
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=None)
    return mock_async_client


class TestListFilesEndpoint:
    """Tests for GET /api/v1/chats/{chat_id}/files endpoint."""

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_list_files_success(self, mock_httpx, client, mock_chat_service, mock_file_service, valid_headers):
        """Test listing files successfully."""
        mock_httpx.return_value = mock_httpx_success()

        mock_chat_service.chat_exists.return_value = True
        mock_file_service.list_files.return_value = [
            FileInfo(filename="chart.html", size=1234, timestamp="2024-12-09T14:30:00Z", mime_type="text/html"),
            FileInfo(filename="data.csv", size=567, timestamp="2024-12-09T14:35:00Z", mime_type="text/csv"),
        ]

        response = client.get("/api/v1/chats/chat_123/files", headers=valid_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["files"]) == 2
        assert data["files"][0]["filename"] == "chart.html"
        assert data["files"][1]["filename"] == "data.csv"

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_list_files_empty(self, mock_httpx, client, mock_chat_service, mock_file_service, valid_headers):
        """Test listing files when chat has no files."""
        mock_httpx.return_value = mock_httpx_success()

        mock_chat_service.chat_exists.return_value = True
        mock_file_service.list_files.return_value = []

        response = client.get("/api/v1/chats/chat_123/files", headers=valid_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["files"] == []

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_list_files_chat_not_found(self, mock_httpx, client, mock_chat_service, mock_file_service, valid_headers):
        """Test listing files for non-existent chat."""
        mock_httpx.return_value = mock_httpx_success()

        mock_chat_service.chat_exists.return_value = False

        response = client.get("/api/v1/chats/chat_nonexistent/files", headers=valid_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestDownloadFileEndpoint:
    """Tests for GET /api/v1/chats/{chat_id}/files/{filename} endpoint."""

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_download_file_success(self, mock_httpx, client, mock_chat_service, mock_file_service, valid_headers):
        """Test downloading a file successfully."""
        mock_httpx.return_value = mock_httpx_success()

        mock_chat_service.chat_exists.return_value = True
        mock_file_service.get_file.return_value = (b"<html>content</html>", "text/html")

        response = client.get("/api/v1/chats/chat_123/files/chart.html", headers=valid_headers)

        assert response.status_code == 200
        assert response.content == b"<html>content</html>"
        assert "text/html" in response.headers["content-type"]
        assert 'attachment; filename="chart.html"' in response.headers["content-disposition"]

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_download_file_not_found(self, mock_httpx, client, mock_chat_service, mock_file_service, valid_headers):
        """Test downloading a non-existent file."""
        mock_httpx.return_value = mock_httpx_success()

        mock_chat_service.chat_exists.return_value = True
        mock_file_service.get_file.return_value = None

        response = client.get("/api/v1/chats/chat_123/files/missing.html", headers=valid_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_download_file_chat_not_found(
        self, mock_httpx, client, mock_chat_service, mock_file_service, valid_headers
    ):
        """Test downloading a file from non-existent chat."""
        mock_httpx.return_value = mock_httpx_success()

        mock_chat_service.chat_exists.return_value = False

        response = client.get("/api/v1/chats/chat_nonexistent/files/test.html", headers=valid_headers)

        assert response.status_code == 404
        assert "Chat" in response.json()["detail"]


class TestTestClientEndpoint:
    """Tests for /test-client endpoint."""

    def test_test_client_serves_index(self, client, mock_chat_service, mock_file_service, mock_agent_service):
        """Test that /test-client serves the index.html."""
        response = client.get("/test-client")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Rossum Agent" in response.text

    def test_test_client_static_css(self, client, mock_chat_service, mock_file_service, mock_agent_service):
        """Test that static CSS is accessible."""
        response = client.get("/test-client/styles.css")

        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_test_client_static_js(self, client, mock_chat_service, mock_file_service, mock_agent_service):
        """Test that static JS is accessible."""
        response = client.get("/test-client/app.js")

        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]
