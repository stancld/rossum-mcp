"""Tests for synchronous RossumAgentClient."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from rossum_agent_client import RossumAgentClient
from rossum_agent_client.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    RossumAgentError,
    ServerError,
    ValidationError,
)
from rossum_agent_client.models import (
    ChatDetail,
    ChatListResponse,
    ChatResponse,
    DeleteResponse,
    FileCreatedEvent,
    FileListResponse,
    HealthResponse,
    StepEvent,
    StreamDoneEvent,
    SubAgentProgressEvent,
    SubAgentTextEvent,
)


class TestClientInitialization:
    def test_init_sets_attributes(self, agent_api_url: str, rossum_api_base_url: str, token: str) -> None:
        client = RossumAgentClient(agent_api_url, rossum_api_base_url, token)
        assert client.agent_api_url == agent_api_url
        assert client.token == token
        assert client.rossum_api_base_url == rossum_api_base_url
        assert client.timeout == 300.0

    def test_init_strips_trailing_slash(self, rossum_api_base_url: str, token: str) -> None:
        client = RossumAgentClient("https://example.com/", rossum_api_base_url, token)
        assert client.agent_api_url == "https://example.com"

    def test_init_custom_timeout(self, agent_api_url: str, rossum_api_base_url: str, token: str) -> None:
        client = RossumAgentClient(agent_api_url, rossum_api_base_url, token, timeout=60.0)
        assert client.timeout == 60.0

    def test_context_manager(self, agent_api_url: str, rossum_api_base_url: str, token: str) -> None:
        with RossumAgentClient(agent_api_url, rossum_api_base_url, token) as client:
            assert isinstance(client, RossumAgentClient)


class TestGetHeaders:
    def test_returns_correct_headers(self, client: RossumAgentClient, expected_headers: dict[str, str]) -> None:
        headers = client._get_headers()
        assert headers == expected_headers


class TestHealthCheck:
    def test_health_check_success(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/health",
            json={"status": "healthy", "redis_connected": True, "version": "1.0.0dev"},
        )

        result = client.health_check()

        assert isinstance(result, HealthResponse)
        assert result.status == "healthy"
        assert result.redis_connected is True
        assert result.version == "1.0.0dev"

    def test_health_check_unhealthy(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/health",
            json={"status": "unhealthy", "redis_connected": False, "version": "1.0.0dev"},
        )

        result = client.health_check()

        assert result.status == "unhealthy"
        assert result.redis_connected is False


class TestCreateChat:
    def test_create_chat_success(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=201,
            json={"chat_id": "chat-123", "created_at": "2024-01-15T10:00:00Z"},
        )

        result = client.create_chat()

        assert isinstance(result, ChatResponse)
        assert result.chat_id == "chat-123"

    def test_create_chat_with_mcp_mode(
        self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=201,
            json={"chat_id": "chat-456", "created_at": "2024-01-15T10:00:00Z"},
        )

        result = client.create_chat(mcp_mode="read-write")

        assert result.chat_id == "chat-456"
        request = httpx_mock.get_request()
        assert request is not None
        assert b'"mcp_mode":"read-write"' in request.content


class TestListChats:
    def test_list_chats_success(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats?limit=50&offset=0",
            json={
                "chats": [
                    {
                        "chat_id": "chat-1",
                        "timestamp": 1705312800,
                        "message_count": 5,
                        "first_message": "Hello",
                        "preview": "How can I help?",
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0,
            },
        )

        result = client.list_chats()

        assert isinstance(result, ChatListResponse)
        assert result.total == 1
        assert len(result.chats) == 1
        assert result.chats[0].chat_id == "chat-1"

    def test_list_chats_with_pagination(
        self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats?limit=10&offset=20",
            json={"chats": [], "total": 100, "limit": 10, "offset": 20},
        )

        result = client.list_chats(limit=10, offset=20)

        assert result.limit == 10
        assert result.offset == 20


class TestGetChat:
    def test_get_chat_success(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123",
            json={
                "chat_id": "chat-123",
                "messages": [{"role": "user", "content": "Hello"}],
                "created_at": "2024-01-15T10:00:00Z",
                "files": [],
            },
        )

        result = client.get_chat("chat-123")

        assert isinstance(result, ChatDetail)
        assert result.chat_id == "chat-123"
        assert len(result.messages) == 1

    def test_get_chat_not_found(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/nonexistent",
            status_code=404,
            text="Chat not found",
        )

        with pytest.raises(NotFoundError) as exc_info:
            client.get_chat("nonexistent")

        assert exc_info.value.status_code == 404


class TestDeleteChat:
    def test_delete_chat_success(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123",
            method="DELETE",
            json={"deleted": True},
        )

        result = client.delete_chat("chat-123")

        assert isinstance(result, DeleteResponse)
        assert result.deleted is True


class TestListFiles:
    def test_list_files_success(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/files",
            json={
                "files": [
                    {
                        "filename": "report.csv",
                        "size": 1024,
                        "timestamp": "2024-01-15T10:00:00Z",
                        "mime_type": "text/csv",
                    }
                ],
                "total": 1,
            },
        )

        result = client.list_files("chat-123")

        assert isinstance(result, FileListResponse)
        assert result.total == 1
        assert result.files[0].filename == "report.csv"


class TestDownloadFile:
    def test_download_file_success(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        file_content = b"col1,col2\nval1,val2"
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/files/report.csv",
            content=file_content,
        )

        result = client.download_file("chat-123", "report.csv")

        assert result == file_content


class TestSendMessageStream:
    def test_send_message_stream_parses_events(
        self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str
    ) -> None:
        sse_response = (
            'event: step\ndata: {"type": "thinking", "step_number": 1, "content": "Analyzing..."}\n\n'
            'event: step\ndata: {"type": "tool_start", "step_number": 2, "tool_name": "list_queues"}\n\n'
            'event: step\ndata: {"type": "final_answer", "step_number": 3, "content": "Done", "is_final": true}\n\n'
            'event: done\ndata: {"total_steps": 3, "input_tokens": 100, "output_tokens": 50}\n\n'
        )
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/messages",
            method="POST",
            content=sse_response.encode(),
        )

        events = list(client.send_message_stream("chat-123", "List queues"))

        assert len(events) == 4
        assert isinstance(events[0], StepEvent)
        assert events[0].type == "thinking"
        assert isinstance(events[1], StepEvent)
        assert events[1].tool_name == "list_queues"
        assert isinstance(events[2], StepEvent)
        assert events[2].type == "final_answer"
        assert isinstance(events[3], StreamDoneEvent)
        assert events[3].total_steps == 3

    def test_send_message_stream_with_images(
        self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str
    ) -> None:
        from rossum_agent_client.models import ImageContent

        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/messages",
            method="POST",
            content=b'event: done\ndata: {"total_steps": 1, "input_tokens": 10, "output_tokens": 5}\n\n',
        )

        images = [ImageContent(media_type="image/png", data="base64data")]
        list(client.send_message_stream("chat-123", "Analyze image", images=images))

        request = httpx_mock.get_request()
        assert request is not None
        assert b'"images"' in request.content

    def test_send_message_stream_with_documents(
        self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str
    ) -> None:
        from rossum_agent_client.models import DocumentContent

        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/messages",
            method="POST",
            content=b'event: done\ndata: {"total_steps": 1, "input_tokens": 10, "output_tokens": 5}\n\n',
        )

        documents = [DocumentContent(data="base64pdf", filename="invoice.pdf")]
        list(client.send_message_stream("chat-123", "Process PDF", documents=documents))

        request = httpx_mock.get_request()
        assert request is not None
        assert b'"documents"' in request.content

    def test_send_message_stream_file_created_event(
        self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str
    ) -> None:
        sse_response = (
            "event: file_created\n"
            'data: {"type": "file_created", "filename": "output.csv", "url": "/files/output.csv"}\n\n'
            "event: done\n"
            'data: {"total_steps": 1, "input_tokens": 10, "output_tokens": 5}\n\n'
        )
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/messages",
            method="POST",
            content=sse_response.encode(),
        )

        events = list(client.send_message_stream("chat-123", "Create file"))

        assert isinstance(events[0], FileCreatedEvent)
        assert events[0].filename == "output.csv"

    def test_send_message_stream_sub_agent_events(
        self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str
    ) -> None:
        sse_response = (
            "event: sub_agent_progress\n"
            "data: {"
            '"type": "sub_agent_progress", "tool_name": "search", '
            '"iteration": 1, "max_iterations": 5, "status": "searching"'
            "}\n\n"
            "event: sub_agent_text\n"
            "data: {"
            '"type": "sub_agent_text", "tool_name": "search", '
            '"text": "Found results", "is_final": true'
            "}\n\n"
            "event: done\n"
            'data: {"total_steps": 1, "input_tokens": 10, "output_tokens": 5}\n\n'
        )
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/messages",
            method="POST",
            content=sse_response.encode(),
        )

        events = list(client.send_message_stream("chat-123", "Search"))

        assert isinstance(events[0], SubAgentProgressEvent)
        assert events[0].tool_name == "search"
        assert events[0].iteration == 1
        assert isinstance(events[1], SubAgentTextEvent)
        assert events[1].text == "Found results"

    def test_send_message_stream_multiline_data(
        self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str
    ) -> None:
        sse_response = (
            'event: step\ndata: {"type": "final_answer", "step_number": 1,\n'
            'data: "content": "Line 1\\nLine 2", "is_final": true}\n\n'
            'event: done\ndata: {"total_steps": 1, "input_tokens": 10, "output_tokens": 5}\n\n'
        )
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/messages",
            method="POST",
            content=sse_response.encode(),
        )

        events = list(client.send_message_stream("chat-123", "Test"))

        assert len(events) == 2
        assert isinstance(events[0], StepEvent)

    def test_send_message_stream_with_rossum_url(
        self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/messages",
            method="POST",
            content=b'event: done\ndata: {"total_steps": 1, "input_tokens": 10, "output_tokens": 5}\n\n',
        )

        list(client.send_message_stream("chat-123", "Check queue", rossum_url="https://elis.rossum.ai/queues/123"))

        request = httpx_mock.get_request()
        assert request is not None
        assert b'"rossum_url"' in request.content

    def test_send_message_stream_error_response(
        self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/messages",
            method="POST",
            status_code=401,
            text="Unauthorized",
        )

        with pytest.raises(AuthenticationError) as exc_info:
            list(client.send_message_stream("chat-123", "Test"))

        assert exc_info.value.status_code == 401


class TestErrorHandling:
    def test_authentication_error(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=401,
            text="Invalid token",
        )

        with pytest.raises(AuthenticationError) as exc_info:
            client.create_chat()

        assert exc_info.value.status_code == 401
        assert exc_info.value.response_body == "Invalid token"

    def test_not_found_error(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/missing",
            status_code=404,
            text="Not found",
        )

        with pytest.raises(NotFoundError) as exc_info:
            client.get_chat("missing")

        assert exc_info.value.status_code == 404

    def test_validation_error(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=422,
            text="Validation failed",
        )

        with pytest.raises(ValidationError) as exc_info:
            client.create_chat()

        assert exc_info.value.status_code == 422

    def test_server_error(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=500,
            text="Internal error",
        )

        with pytest.raises(ServerError) as exc_info:
            client.create_chat()

        assert exc_info.value.status_code == 500

    def test_generic_client_error(self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=400,
            text="Bad request",
        )

        with pytest.raises(RossumAgentError) as exc_info:
            client.create_chat()

        assert exc_info.value.status_code == 400

    def test_rate_limit_error_with_retry_after(
        self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=429,
            text="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )

        with pytest.raises(RateLimitError) as exc_info:
            client.create_chat()

        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 60
        assert exc_info.value.response_body == "Rate limit exceeded"

    def test_rate_limit_error_without_retry_after(
        self, httpx_mock: HTTPXMock, client: RossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=429,
            text="Too many requests",
        )

        with pytest.raises(RateLimitError) as exc_info:
            client.create_chat()

        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after is None


class TestClose:
    def test_close_method(self, agent_api_url: str, rossum_api_base_url: str, token: str) -> None:
        client = RossumAgentClient(agent_api_url, rossum_api_base_url, token)
        client.close()
        assert client._client.is_closed


class TestParseSSEEvent:
    def test_invalid_json_returns_none(self, client: RossumAgentClient) -> None:
        result = client._parse_sse_event("step", "not valid json")
        assert result is None

    def test_unknown_event_type_returns_none(self, client: RossumAgentClient) -> None:
        result = client._parse_sse_event("unknown_event", '{"type": "unknown"}')
        assert result is None

    def test_error_event_type_returns_step_event(self, client: RossumAgentClient) -> None:
        result = client._parse_sse_event(
            "error", '{"type": "error", "step_number": 1, "content": "Error occurred", "is_error": true}'
        )
        assert isinstance(result, StepEvent)
        assert result.type == "error"
        assert result.is_error is True
