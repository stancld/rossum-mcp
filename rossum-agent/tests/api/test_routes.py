"""Integration tests for API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from rossum_agent.api.main import app
from rossum_agent.api.models.schemas import (
    ChatDetail,
    ChatListResponse,
    ChatResponse,
    ChatSummary,
    Message,
    StepEvent,
    StreamDoneEvent,
)
from rossum_agent.api.routes import chats, files, health, messages
from rossum_agent.api.routes.chats import get_chat_service_dep as chats_get_chat_service_dep
from rossum_agent.api.routes.health import get_chat_service_dep as health_get_chat_service_dep

from .conftest import create_mock_httpx_client


@pytest.fixture
def client(mock_chat_service, mock_agent_service):
    """Create test client with mocked services."""
    health.set_chat_service_getter(lambda: mock_chat_service)
    chats.set_chat_service_getter(lambda: mock_chat_service)
    messages.set_chat_service_getter(lambda: mock_chat_service)
    messages.set_agent_service_getter(lambda: mock_agent_service)
    files.set_chat_service_getter(lambda: mock_chat_service)

    with TestClient(app) as client:
        yield client


class TestHealthEndpoint:
    """Tests for /api/v1/health endpoint."""

    def test_health_healthy(self, client, mock_chat_service):
        """Test health check when Redis is connected."""
        mock_chat_service.is_connected.return_value = True

        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["redis_connected"] is True
        assert "version" in data

    def test_health_unhealthy(self, client, mock_chat_service):
        """Test health check when Redis is disconnected."""
        mock_chat_service.is_connected.return_value = False

        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["redis_connected"] is False


class TestCreateChatEndpoint:
    """Tests for POST /api/v1/chats endpoint."""

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_create_chat_success(self, mock_httpx, client, mock_chat_service, valid_headers):
        """Test creating a chat successfully."""
        mock_httpx.return_value = create_mock_httpx_client()

        now = datetime.now(UTC)
        mock_chat_service.create_chat.return_value = ChatResponse(chat_id="chat_123", created_at=now)

        response = client.post("/api/v1/chats", headers=valid_headers, json={})

        assert response.status_code == 201
        data = response.json()
        assert data["chat_id"] == "chat_123"
        assert "created_at" in data

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_create_chat_respects_mcp_mode_from_request(self, mock_httpx, client, mock_chat_service, valid_headers):
        """Test creating a chat respects mcp_mode from request body."""
        mock_httpx.return_value = create_mock_httpx_client()

        now = datetime.now(UTC)
        mock_chat_service.create_chat.return_value = ChatResponse(chat_id="chat_123", created_at=now)

        response = client.post("/api/v1/chats", headers=valid_headers, json={"mcp_mode": "read-write"})

        assert response.status_code == 201
        mock_chat_service.create_chat.assert_called_once()
        call_kwargs = mock_chat_service.create_chat.call_args
        assert call_kwargs.kwargs["mcp_mode"] == "read-write"

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_create_chat_defaults_to_read_only_mode(self, mock_httpx, client, mock_chat_service, valid_headers):
        """Test creating a chat defaults to read-only mode when not specified."""
        mock_httpx.return_value = create_mock_httpx_client()

        now = datetime.now(UTC)
        mock_chat_service.create_chat.return_value = ChatResponse(chat_id="chat_123", created_at=now)

        response = client.post("/api/v1/chats", headers=valid_headers)

        assert response.status_code == 201
        mock_chat_service.create_chat.assert_called_once()
        call_kwargs = mock_chat_service.create_chat.call_args
        assert call_kwargs.kwargs["mcp_mode"] == "read-only"

    def test_create_chat_missing_token(self, client, mock_chat_service):
        """Test creating a chat without token."""
        response = client.post("/api/v1/chats", headers={"X-Rossum-Api-Url": "https://api.rossum.ai"}, json={})

        assert response.status_code == 422

    def test_create_chat_missing_api_url(self, client, mock_chat_service):
        """Test creating a chat without API URL."""
        response = client.post("/api/v1/chats", headers={"X-Rossum-Token": "test_token"}, json={})

        assert response.status_code == 422

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_create_chat_invalid_token(self, mock_httpx, client, mock_chat_service, valid_headers):
        """Test creating a chat with invalid token."""
        mock_httpx.return_value = create_mock_httpx_client(status_code=401)

        response = client.post("/api/v1/chats", headers=valid_headers, json={})

        assert response.status_code == 401
        assert "Invalid Rossum API token" in response.json()["detail"]


class TestListChatsEndpoint:
    """Tests for GET /api/v1/chats endpoint."""

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_list_chats_empty(self, mock_httpx, client, mock_chat_service, valid_headers):
        """Test listing chats when empty."""
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.list_chats.return_value = ChatListResponse(chats=[], total=0, limit=50, offset=0)

        response = client.get("/api/v1/chats", headers=valid_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["chats"] == []
        assert data["total"] == 0

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_list_chats_with_results(self, mock_httpx, client, mock_chat_service, valid_headers):
        """Test listing chats with results."""
        mock_httpx.return_value = create_mock_httpx_client()

        mock_chat_service.list_chats.return_value = ChatListResponse(
            chats=[
                ChatSummary(chat_id="chat_1", timestamp=1702132252, message_count=5, first_message="Hello"),
            ],
            total=1,
            limit=50,
            offset=0,
        )

        response = client.get("/api/v1/chats", headers=valid_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["chats"]) == 1
        assert data["chats"][0]["chat_id"] == "chat_1"

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_list_chats_pagination(self, mock_httpx, client, mock_chat_service, valid_headers):
        """Test listing chats with pagination params."""
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.list_chats.return_value = ChatListResponse(chats=[], total=0, limit=10, offset=5)

        response = client.get("/api/v1/chats?limit=10&offset=5", headers=valid_headers)

        assert response.status_code == 200
        mock_chat_service.list_chats.assert_called_once()
        call_kwargs = mock_chat_service.list_chats.call_args.kwargs
        assert call_kwargs["limit"] == 10
        assert call_kwargs["offset"] == 5


class TestGetChatEndpoint:
    """Tests for GET /api/v1/chats/{chat_id} endpoint."""

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_get_chat_success(self, mock_httpx, client, mock_chat_service, valid_headers):
        """Test getting a chat successfully."""
        mock_httpx.return_value = create_mock_httpx_client()

        now = datetime.now(UTC)
        mock_chat_service.get_chat.return_value = ChatDetail(
            chat_id="chat_123", messages=[Message(role="user", content="Hello")], created_at=now, files=[]
        )

        response = client.get("/api/v1/chats/chat_123", headers=valid_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["chat_id"] == "chat_123"
        assert len(data["messages"]) == 1

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_get_chat_not_found(self, mock_httpx, client, mock_chat_service, valid_headers):
        """Test getting a non-existent chat."""
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.get_chat.return_value = None

        response = client.get("/api/v1/chats/chat_nonexistent", headers=valid_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestDeleteChatEndpoint:
    """Tests for DELETE /api/v1/chats/{chat_id} endpoint."""

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_delete_chat_success(self, mock_httpx, client, mock_chat_service, valid_headers):
        """Test deleting a chat successfully."""
        mock_httpx.return_value = create_mock_httpx_client()

        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.delete_chat.return_value = True

        response = client.delete("/api/v1/chats/chat_123", headers=valid_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_delete_chat_not_found(self, mock_httpx, client, mock_chat_service, valid_headers):
        """Test deleting a non-existent chat."""
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = False

        response = client.delete("/api/v1/chats/chat_nonexistent", headers=valid_headers)

        assert response.status_code == 404


class TestSendMessageEndpoint:
    """Tests for POST /api/v1/chats/{chat_id}/messages endpoint."""

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_send_message_chat_not_found(
        self, mock_httpx, client, mock_chat_service, mock_agent_service, valid_headers
    ):
        """Test sending message to non-existent chat."""
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = False

        response = client.post(
            "/api/v1/chats/chat_nonexistent/messages", headers=valid_headers, json={"content": "Hello"}
        )

        assert response.status_code == 404

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_send_message_empty_content(
        self, mock_httpx, client, mock_chat_service, mock_agent_service, valid_headers
    ):
        """Test sending message with empty content."""
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True

        response = client.post("/api/v1/chats/chat_123/messages", headers=valid_headers, json={"content": ""})

        assert response.status_code == 422

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_send_message_streaming_response(
        self, mock_httpx, client, mock_chat_service, mock_agent_service, valid_headers
    ):
        """Test that send message returns streaming response."""
        mock_httpx.return_value = create_mock_httpx_client()

        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.get_messages.return_value = []
        mock_chat_service.save_messages.return_value = True

        async def mock_run_agent(*args, **kwargs):
            yield StepEvent(type="thinking", step_number=1, content="Processing...")
            yield StepEvent(type="final_answer", step_number=1, content="Done!", is_final=True)
            yield StreamDoneEvent(total_steps=1, input_tokens=100, output_tokens=50)

        mock_agent_service.run_agent = mock_run_agent
        mock_agent_service.build_updated_history.return_value = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Done!"},
        ]

        response = client.post("/api/v1/chats/chat_123/messages", headers=valid_headers, json={"content": "Hello"})

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        content = response.text
        assert "event: step" in content
        assert "event: done" in content


class TestOpenAPIDocumentation:
    """Tests for OpenAPI documentation endpoints."""

    def test_openapi_json(self, client, mock_chat_service, mock_agent_service):
        """Test OpenAPI JSON is accessible."""
        response = client.get("/api/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert data["info"]["title"] == "Rossum Agent API"

    def test_docs_endpoint(self, client, mock_chat_service, mock_agent_service):
        """Test Swagger UI is accessible."""
        response = client.get("/api/docs")

        assert response.status_code == 200

    def test_redoc_endpoint(self, client, mock_chat_service, mock_agent_service):
        """Test ReDoc is accessible."""
        response = client.get("/api/redoc")

        assert response.status_code == 200


class TestServiceGetterDeps:
    """Tests for service getter dependency functions.

    Note: The autouse fixture reset_route_service_getters handles resetting
    the service getter state before and after each test.
    """

    def test_chats_get_chat_service_dep_raises_when_not_configured(self):
        """Test that chats get_chat_service_dep raises RuntimeError when not configured."""
        with pytest.raises(RuntimeError, match="Chat service getter not configured"):
            chats_get_chat_service_dep()

    def test_health_get_chat_service_dep_raises_when_not_configured(self):
        """Test that health get_chat_service_dep raises RuntimeError when not configured."""
        with pytest.raises(RuntimeError, match="Chat service getter not configured"):
            health_get_chat_service_dep()
