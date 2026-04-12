"""Integration tests for API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from rossum_agent.agent.models import FinalAnswerStep, ReasoningStep
from rossum_agent.api.main import app
from rossum_agent.api.models.schemas import (
    ChatDetail,
    ChatListResponse,
    ChatResponse,
    ChatSummary,
    Message,
    StreamDoneEvent,
)
from rossum_agent.change_tracking.models import ConfigCommit, EntityChange
from rossum_agent.storage import ChatData, ChatMetadata

from .conftest import create_mock_httpx_client


@pytest.fixture
def mock_valkey_connection():
    """Create a mock ValkeyConnection for change tracking."""
    return MagicMock()


@pytest.fixture
def client(mock_chat_service, mock_agent_service, mock_file_service, mock_valkey_connection):
    """Create test client with mocked services injected via app.state."""
    app.state.chat_service = mock_chat_service
    app.state.agent_service = mock_agent_service
    app.state.file_service = mock_file_service
    app.state.valkey_connection = mock_valkey_connection

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


class TestHealthEndpoint:
    """Tests for /api/v1/health endpoint."""

    def test_health_healthy(self, client, mock_chat_service):
        """Test health check when storage is connected."""
        mock_chat_service.is_connected.return_value = True

        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["storage_connected"] is True
        assert "version" in data

    def test_health_unhealthy(self, client, mock_chat_service):
        """Test health check when storage is disconnected."""
        mock_chat_service.is_connected.return_value = False

        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["storage_connected"] is False

    def test_health_includes_storage_backend(self, client, mock_chat_service):
        """Test health check includes storage_backend field."""
        mock_chat_service.is_connected.return_value = True

        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["storage_backend"] == "postgres"


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
        assert call_kwargs.kwargs["persona"] == "default"

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
        assert call_kwargs.kwargs["persona"] == "default"

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_create_chat_respects_persona_from_request(self, mock_httpx, client, mock_chat_service, valid_headers):
        """Test creating a chat respects persona from request body."""
        mock_httpx.return_value = create_mock_httpx_client()

        now = datetime.now(UTC)
        mock_chat_service.create_chat.return_value = ChatResponse(chat_id="chat_123", created_at=now)

        response = client.post("/api/v1/chats", headers=valid_headers, json={"persona": "cautious"})

        assert response.status_code == 201
        mock_chat_service.create_chat.assert_called_once()
        call_kwargs = mock_chat_service.create_chat.call_args
        assert call_kwargs.kwargs["persona"] == "cautious"

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
        mock_chat_service.get_chat_data.return_value = None

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

        mock_chat_service.get_chat_data.return_value = ChatData(
            messages=[], metadata=ChatMetadata(mcp_mode="read-only")
        )
        mock_chat_service.save_messages.return_value = True

        async def mock_run_agent(*args, **kwargs):
            yield ReasoningStep(step_number=1, reasoning="Processing...")
            yield FinalAnswerStep(step_number=1, final_answer="Done!")
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
        assert '"type":"start"' in content
        assert '"type":"finish"' in content
        assert '"type":"data-final-answer"' in content
        assert "data: [DONE]" in content

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_send_message_preserves_mcp_mode_metadata(
        self, mock_httpx, client, mock_chat_service, mock_agent_service, valid_headers
    ):
        """Test that send message preserves metadata across messages."""
        mock_httpx.return_value = create_mock_httpx_client()

        original_metadata = ChatMetadata(mcp_mode="read-write", persona="default")
        mock_chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=original_metadata)
        mock_chat_service.save_messages.return_value = True

        async def mock_run_agent(*args, **kwargs):
            yield FinalAnswerStep(step_number=1, final_answer="Done!")
            yield StreamDoneEvent(total_steps=1, input_tokens=100, output_tokens=50)

        mock_agent_service.run_agent = mock_run_agent
        mock_agent_service.build_updated_history.return_value = []

        response = client.post("/api/v1/chats/chat_123/messages", headers=valid_headers, json={"content": "Hello"})

        assert response.status_code == 200

        mock_chat_service.save_messages.assert_called_once()
        call_kwargs = mock_chat_service.save_messages.call_args.kwargs
        assert call_kwargs["metadata"] is original_metadata
        assert call_kwargs["metadata"].mcp_mode == "read-write"
        assert call_kwargs["metadata"].persona == "default"

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_send_message_uses_message_level_mcp_mode(
        self, mock_httpx, client, mock_chat_service, mock_agent_service, valid_headers, mock_run_agent_factory
    ):
        """Test that per-message mcp_mode overrides chat's mcp_mode."""
        mock_httpx.return_value = create_mock_httpx_client()

        original_metadata = ChatMetadata(mcp_mode="read-only")
        mock_chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=original_metadata)
        mock_chat_service.save_messages.return_value = True

        run_agent_calls, mock_run_agent = mock_run_agent_factory()
        mock_agent_service.run_agent = mock_run_agent
        mock_agent_service.build_updated_history.return_value = []

        response = client.post(
            "/api/v1/chats/chat_123/messages",
            headers=valid_headers,
            json={"content": "Hello", "mcp_mode": "read-write"},
        )

        assert response.status_code == 200
        _ = response.text  # Consume streaming response

        assert len(run_agent_calls) == 1
        assert run_agent_calls[0]["mcp_mode"] == "read-write"

        mock_chat_service.save_messages.assert_called_once()
        save_kwargs = mock_chat_service.save_messages.call_args.kwargs
        assert save_kwargs["metadata"].mcp_mode == "read-write"

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_send_message_uses_message_level_persona(
        self, mock_httpx, client, mock_chat_service, mock_agent_service, valid_headers, mock_run_agent_factory
    ):
        """Test that per-message persona overrides chat persona."""
        mock_httpx.return_value = create_mock_httpx_client()

        original_metadata = ChatMetadata(mcp_mode="read-only", persona="default")
        mock_chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=original_metadata)
        mock_chat_service.save_messages.return_value = True

        run_agent_calls, mock_run_agent = mock_run_agent_factory()
        mock_agent_service.run_agent = mock_run_agent
        mock_agent_service.build_updated_history.return_value = []

        response = client.post(
            "/api/v1/chats/chat_123/messages",
            headers=valid_headers,
            json={"content": "Hello", "persona": "cautious"},
        )

        assert response.status_code == 200
        _ = response.text

        assert len(run_agent_calls) == 1
        assert run_agent_calls[0]["persona"] == "cautious"

        mock_chat_service.save_messages.assert_called_once()
        save_kwargs = mock_chat_service.save_messages.call_args.kwargs
        assert save_kwargs["metadata"].persona == "cautious"

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_send_message_falls_back_to_chat_persona(
        self, mock_httpx, client, mock_chat_service, mock_agent_service, valid_headers, mock_run_agent_factory
    ):
        """Test that message without persona uses chat persona."""
        mock_httpx.return_value = create_mock_httpx_client()

        original_metadata = ChatMetadata(mcp_mode="read-write", persona="cautious")
        mock_chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=original_metadata)
        mock_chat_service.save_messages.return_value = True

        run_agent_calls, mock_run_agent = mock_run_agent_factory()
        mock_agent_service.run_agent = mock_run_agent
        mock_agent_service.build_updated_history.return_value = []

        response = client.post(
            "/api/v1/chats/chat_123/messages",
            headers=valid_headers,
            json={"content": "Hello"},
        )

        assert response.status_code == 200
        _ = response.text

        assert len(run_agent_calls) == 1
        assert run_agent_calls[0]["persona"] == "cautious"

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_send_message_falls_back_to_chat_mcp_mode(
        self, mock_httpx, client, mock_chat_service, mock_agent_service, valid_headers, mock_run_agent_factory
    ):
        """Test that message without mcp_mode uses chat's mcp_mode."""
        mock_httpx.return_value = create_mock_httpx_client()

        original_metadata = ChatMetadata(mcp_mode="read-write")
        mock_chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=original_metadata)
        mock_chat_service.save_messages.return_value = True

        run_agent_calls, mock_run_agent = mock_run_agent_factory()
        mock_agent_service.run_agent = mock_run_agent
        mock_agent_service.build_updated_history.return_value = []

        response = client.post(
            "/api/v1/chats/chat_123/messages",
            headers=valid_headers,
            json={"content": "Hello"},
        )

        assert response.status_code == 200
        _ = response.text  # Consume streaming response

        assert len(run_agent_calls) == 1
        assert run_agent_calls[0]["mcp_mode"] == "read-write"


class TestListChatCommitsEndpoint:
    """Tests for GET /api/v1/chats/{chat_id}/commits endpoint."""

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_chat_not_found(self, mock_httpx, client, mock_chat_service, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.get_chat_data.return_value = None

        response = client.get("/api/v1/chats/chat_missing/commits", headers=valid_headers)

        assert response.status_code == 404

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_no_commits(self, mock_httpx, client, mock_chat_service, mock_valkey_connection, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=ChatMetadata())
        mock_valkey_connection.is_connected.return_value = False

        response = client.get("/api/v1/chats/chat_123/commits", headers=valid_headers)

        assert response.status_code == 200
        assert response.json() == {"commits": []}

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_with_commits(self, mock_httpx, client, mock_chat_service, mock_valkey_connection, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()

        metadata = ChatMetadata(config_commits=["abc123"])
        mock_chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=metadata)
        mock_valkey_connection.is_connected.return_value = True

        commit = ConfigCommit(
            hash="abc123",
            chat_id="chat_123",
            timestamp=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
            message="Updated queue settings",
            user_request="Change queue",
            environment="https://api.rossum.ai",
            changes=[
                EntityChange(
                    entity_type="queue",
                    entity_id="123",
                    entity_name="My Queue",
                    operation="update",
                    before={},
                    after={},
                )
            ],
        )
        mock_commit_store = MagicMock()
        mock_commit_store.get_commit.return_value = commit

        with patch("rossum_agent.api.routes.chats.CommitStore", return_value=mock_commit_store):
            response = client.get("/api/v1/chats/chat_123/commits", headers=valid_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["commits"]) == 1
        c = data["commits"][0]
        assert c["hash"] == "abc123"
        assert c["message"] == "Updated queue settings"
        assert c["user_request"] == "Change queue"
        assert len(c["changes"]) == 1
        assert c["changes"][0] == {
            "entity_type": "queue",
            "entity_id": "123",
            "entity_name": "My Queue",
            "operation": "update",
        }

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_expired_commit_skipped(
        self, mock_httpx, client, mock_chat_service, mock_valkey_connection, valid_headers
    ):
        mock_httpx.return_value = create_mock_httpx_client()

        metadata = ChatMetadata(config_commits=["expired"])
        mock_chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=metadata)
        mock_valkey_connection.is_connected.return_value = True

        mock_commit_store = MagicMock()
        mock_commit_store.get_commit.return_value = None

        with patch("rossum_agent.api.routes.chats.CommitStore", return_value=mock_commit_store):
            response = client.get("/api/v1/chats/chat_123/commits", headers=valid_headers)

        assert response.status_code == 200
        assert response.json() == {"commits": []}


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


class TestServiceDependencies:
    """Tests for service dependency functions."""

    def test_services_not_initialized_error(self):
        """Test that accessing services without initialization raises RuntimeError."""
        from rossum_agent.api.dependencies import get_agent_service, get_chat_service, get_file_service
        from starlette.datastructures import State

        mock_request = MagicMock()
        mock_request.app = MagicMock()
        mock_request.app.state = State()

        with pytest.raises(RuntimeError, match="Chat service not initialized"):
            get_chat_service(mock_request)

        with pytest.raises(RuntimeError, match="Agent service not initialized"):
            get_agent_service(mock_request)

        with pytest.raises(RuntimeError, match="File service not initialized"):
            get_file_service(mock_request)

    def test_get_valkey_connection_not_initialized_error(self):
        """Test that accessing valkey_connection without initialization raises RuntimeError."""
        from rossum_agent.api.dependencies import get_valkey_connection
        from starlette.datastructures import State

        mock_request = MagicMock()
        mock_request.app = MagicMock()
        mock_request.app.state = State()

        with pytest.raises(RuntimeError, match="Valkey connection not initialized"):
            get_valkey_connection(mock_request)

    def test_get_valkey_connection_returns_instance(self):
        """Test that get_valkey_connection returns the valkey_connection from app state."""
        from rossum_agent.api.dependencies import get_valkey_connection
        from starlette.datastructures import State

        mock_valkey = MagicMock()
        mock_request = MagicMock()
        mock_request.app = MagicMock()
        mock_request.app.state = State()
        mock_request.app.state.valkey_connection = mock_valkey

        result = get_valkey_connection(mock_request)
        assert result is mock_valkey
