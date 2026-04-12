"""Integration tests for slash command interception in the messages endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from rossum_agent.agent.models import FinalAnswerStep
from rossum_agent.api.main import app
from rossum_agent.api.models.schemas import StreamDoneEvent
from rossum_agent.chat_models import ChatData, ChatMetadata

from .conftest import create_mock_httpx_client


@pytest.fixture
def client(mock_chat_service, mock_agent_service, mock_file_service):
    app.state.chat_service = mock_chat_service
    app.state.agent_service = mock_agent_service
    app.state.file_service = mock_file_service

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


class TestSlashCommandInterception:
    @patch("rossum_agent.api.routes.helpers.ValkeyConnection")
    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_list_commands_returns_sse(
        self, mock_httpx, mock_valkey_connection, client, mock_chat_service, mock_agent_service, valid_headers
    ):
        """Slash commands return SSE events without invoking the agent."""
        mock_httpx.return_value = create_mock_httpx_client()
        mock_valkey_connection.return_value.is_connected.return_value = False

        mock_chat_service.get_chat_data.return_value = ChatData(
            messages=[], metadata=ChatMetadata(mcp_mode="read-only")
        )

        response = client.post(
            "/api/v1/chats/chat_123/messages",
            headers=valid_headers,
            json={"content": "/list-commands"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        content = response.text
        assert '"type":"start"' in content
        assert '"type":"text-delta"' in content
        assert "/list-commands" in content
        assert '"type":"finish"' in content
        assert "data: [DONE]" in content

        # Agent should NOT have been called
        mock_agent_service.run_agent.assert_not_called()

    @patch("rossum_agent.api.routes.messages.get_commit_store")
    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_list_commands_does_not_initialize_commit_store(
        self, mock_httpx, mock_get_commit_store, client, mock_chat_service, valid_headers
    ):
        """List commands should work without touching commit store/Valkey."""
        mock_httpx.return_value = create_mock_httpx_client()
        mock_get_commit_store.side_effect = AssertionError("should not be called")

        mock_chat_service.get_chat_data.return_value = ChatData(
            messages=[], metadata=ChatMetadata(mcp_mode="read-only")
        )

        response = client.post(
            "/api/v1/chats/chat_123/messages",
            headers=valid_headers,
            json={"content": "/list-commands"},
        )

        assert response.status_code == 200
        assert "/list-commands" in response.text
        mock_get_commit_store.assert_not_called()

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_regular_message_still_goes_to_agent(
        self, mock_httpx, client, mock_chat_service, mock_agent_service, valid_headers
    ):
        """Non-command messages are handled by the agent as usual."""
        mock_httpx.return_value = create_mock_httpx_client()

        mock_chat_service.get_chat_data.return_value = ChatData(
            messages=[], metadata=ChatMetadata(mcp_mode="read-only")
        )
        mock_chat_service.save_messages.return_value = True

        async def mock_run_agent(*args, **kwargs):
            yield FinalAnswerStep(step_number=1, final_answer="Hello!")
            yield StreamDoneEvent(total_steps=1, input_tokens=100, output_tokens=50)

        mock_agent_service.run_agent = mock_run_agent
        mock_agent_service.build_updated_history.return_value = []

        response = client.post(
            "/api/v1/chats/chat_123/messages",
            headers=valid_headers,
            json={"content": "Hello, what can you do?"},
        )

        assert response.status_code == 200
        content = response.text
        assert "Hello!" in content

    @patch("rossum_agent.api.routes.helpers.ValkeyConnection")
    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_unknown_command_returns_error(
        self, mock_httpx, mock_valkey_connection, client, mock_chat_service, mock_agent_service, valid_headers
    ):
        """Unknown commands return an error message, not sent to agent."""
        mock_httpx.return_value = create_mock_httpx_client()
        mock_valkey_connection.return_value.is_connected.return_value = False

        mock_chat_service.get_chat_data.return_value = ChatData(
            messages=[], metadata=ChatMetadata(mcp_mode="read-only")
        )

        response = client.post(
            "/api/v1/chats/chat_123/messages",
            headers=valid_headers,
            json={"content": "/nonexistent"},
        )

        assert response.status_code == 200
        content = response.text
        assert "Unknown command" in content
        assert "/list-commands" in content

        mock_agent_service.run_agent.assert_not_called()

    @patch("rossum_agent.api.routes.helpers.ValkeyConnection")
    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_command_does_not_save_to_history(
        self, mock_httpx, mock_valkey_connection, client, mock_chat_service, mock_agent_service, valid_headers
    ):
        """Command interactions are not saved to conversation history."""
        mock_httpx.return_value = create_mock_httpx_client()
        mock_valkey_connection.return_value.is_connected.return_value = False

        mock_chat_service.get_chat_data.return_value = ChatData(
            messages=[], metadata=ChatMetadata(mcp_mode="read-only")
        )

        response = client.post(
            "/api/v1/chats/chat_123/messages",
            headers=valid_headers,
            json={"content": "/list-commands"},
        )

        assert response.status_code == 200
        mock_chat_service.save_messages.assert_not_called()

    @patch("rossum_agent.api.routes.helpers.ValkeyConnection")
    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_list_commits_handles_commit_store_init_failure(
        self, mock_httpx, mock_valkey_connection, client, mock_chat_service, mock_agent_service, valid_headers
    ):
        """List commits should degrade gracefully when commit store init fails."""
        mock_httpx.return_value = create_mock_httpx_client()
        mock_valkey_connection.side_effect = ValueError("invalid VALKEY_PORT")

        mock_chat_service.get_chat_data.return_value = ChatData(
            messages=[],
            metadata=ChatMetadata(mcp_mode="read-only"),
        )

        response = client.post(
            "/api/v1/chats/chat_123/messages",
            headers=valid_headers,
            json={"content": "/list-commits"},
        )

        assert response.status_code == 200
        assert "Commit tracking is not available" in response.text
        mock_agent_service.run_agent.assert_not_called()


class TestCommandsListEndpoint:
    def test_list_commands_endpoint(self, client):
        """GET /api/v1/commands returns available commands."""
        response = client.get("/api/v1/commands")

        assert response.status_code == 200
        data = response.json()
        assert "commands" in data
        commands = data["commands"]
        assert len(commands) >= 2

        names = [c["name"] for c in commands]
        assert "/list-commands" in names
        assert "/list-commits" in names

        for cmd in commands:
            assert "name" in cmd
            assert "description" in cmd
