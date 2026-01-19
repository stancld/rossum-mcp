"""Tests for asynchronous AsyncRossumAgentClient."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from rossum_agent_client import AsyncRossumAgentClient
from rossum_agent_client.exceptions import AuthenticationError, NotFoundError, ServerError
from rossum_agent_client.models import (
    ChatDetail,
    ChatListResponse,
    ChatResponse,
    DeleteResponse,
    FileListResponse,
    HealthResponse,
    StepEvent,
    StreamDoneEvent,
)


class TestAsyncClientInitialization:
    def test_init_sets_attributes(self, agent_api_url: str, rossum_api_base_url: str, token: str) -> None:
        client = AsyncRossumAgentClient(agent_api_url, rossum_api_base_url, token)
        assert client.agent_api_url == agent_api_url
        assert client.token == token
        assert client.rossum_api_base_url == rossum_api_base_url

    @pytest.mark.asyncio
    async def test_async_context_manager(self, agent_api_url: str, rossum_api_base_url: str, token: str) -> None:
        async with AsyncRossumAgentClient(agent_api_url, rossum_api_base_url, token) as client:
            assert isinstance(client, AsyncRossumAgentClient)


class TestAsyncHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_success(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/health",
            json={"status": "healthy", "redis_connected": True, "version": "1.0.0dev"},
        )

        result = await async_client.health_check()

        assert isinstance(result, HealthResponse)
        assert result.status == "healthy"


class TestAsyncCreateChat:
    @pytest.mark.asyncio
    async def test_create_chat_success(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=201,
            json={"chat_id": "chat-123", "created_at": "2024-01-15T10:00:00Z"},
        )

        result = await async_client.create_chat()

        assert isinstance(result, ChatResponse)
        assert result.chat_id == "chat-123"

    @pytest.mark.asyncio
    async def test_create_chat_read_write_mode(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=201,
            json={"chat_id": "chat-456", "created_at": "2024-01-15T10:00:00Z"},
        )

        result = await async_client.create_chat(mcp_mode="read-write")

        assert result.chat_id == "chat-456"


class TestAsyncListChats:
    @pytest.mark.asyncio
    async def test_list_chats_success(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats?limit=50&offset=0",
            json={
                "chats": [
                    {
                        "chat_id": "chat-1",
                        "timestamp": 1705312800,
                        "message_count": 3,
                        "first_message": "Hello",
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0,
            },
        )

        result = await async_client.list_chats()

        assert isinstance(result, ChatListResponse)
        assert result.total == 1


class TestAsyncGetChat:
    @pytest.mark.asyncio
    async def test_get_chat_success(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123",
            json={
                "chat_id": "chat-123",
                "messages": [],
                "created_at": "2024-01-15T10:00:00Z",
                "files": [],
            },
        )

        result = await async_client.get_chat("chat-123")

        assert isinstance(result, ChatDetail)
        assert result.chat_id == "chat-123"

    @pytest.mark.asyncio
    async def test_get_chat_not_found(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/missing",
            status_code=404,
            text="Not found",
        )

        with pytest.raises(NotFoundError):
            await async_client.get_chat("missing")


class TestAsyncDeleteChat:
    @pytest.mark.asyncio
    async def test_delete_chat_success(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123",
            method="DELETE",
            json={"deleted": True},
        )

        result = await async_client.delete_chat("chat-123")

        assert isinstance(result, DeleteResponse)
        assert result.deleted is True


class TestAsyncListFiles:
    @pytest.mark.asyncio
    async def test_list_files_success(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/files",
            json={"files": [], "total": 0},
        )

        result = await async_client.list_files("chat-123")

        assert isinstance(result, FileListResponse)
        assert result.total == 0


class TestAsyncDownloadFile:
    @pytest.mark.asyncio
    async def test_download_file_success(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        file_content = b"test,data\n1,2"
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/files/data.csv",
            content=file_content,
        )

        result = await async_client.download_file("chat-123", "data.csv")

        assert result == file_content


class TestAsyncSendMessageStream:
    @pytest.mark.asyncio
    async def test_send_message_stream_parses_events(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        sse_response = (
            'event: step\ndata: {"type": "thinking", "step_number": 1, "content": "Processing..."}\n\n'
            'event: step\ndata: {"type": "final_answer", "step_number": 2, "content": "Result", "is_final": true}\n\n'
            'event: done\ndata: {"total_steps": 2, "input_tokens": 50, "output_tokens": 25}\n\n'
        )
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/messages",
            method="POST",
            content=sse_response.encode(),
        )

        events = []
        async for event in async_client.send_message_stream("chat-123", "Process this"):
            events.append(event)

        assert len(events) == 3
        assert isinstance(events[0], StepEvent)
        assert events[0].type == "thinking"
        assert events[1].type == "final_answer"
        assert isinstance(events[2], StreamDoneEvent)

    @pytest.mark.asyncio
    async def test_send_message_stream_with_rossum_url(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/messages",
            method="POST",
            content=b'event: done\ndata: {"total_steps": 1, "input_tokens": 10, "output_tokens": 5}\n\n',
        )

        events = []
        async for event in async_client.send_message_stream(
            "chat-123", "Check queue", rossum_url="https://elis.rossum.ai/queues/123"
        ):
            events.append(event)

        request = httpx_mock.get_request()
        assert request is not None
        assert b'"rossum_url"' in request.content


class TestAsyncClose:
    @pytest.mark.asyncio
    async def test_close_method(self, agent_api_url: str, rossum_api_base_url: str, token: str) -> None:
        client = AsyncRossumAgentClient(agent_api_url, rossum_api_base_url, token)
        await client.close()
        assert client._client.is_closed


class TestAsyncSendMessageStreamError:
    @pytest.mark.asyncio
    async def test_send_message_stream_error_response(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/messages",
            method="POST",
            status_code=401,
            text="Unauthorized",
        )

        with pytest.raises(AuthenticationError) as exc_info:
            async for _ in async_client.send_message_stream("chat-123", "Test"):
                pass

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_send_message_stream_with_images_and_documents(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        from rossum_agent_client.models import DocumentContent, ImageContent

        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats/chat-123/messages",
            method="POST",
            content=b'event: done\ndata: {"total_steps": 1, "input_tokens": 10, "output_tokens": 5}\n\n',
        )

        images = [ImageContent(media_type="image/png", data="base64data")]
        documents = [DocumentContent(data="base64pdf", filename="doc.pdf")]

        events = []
        async for event in async_client.send_message_stream(
            "chat-123", "Analyze", images=images, documents=documents, rossum_url="https://elis.rossum.ai/queues/1"
        ):
            events.append(event)

        request = httpx_mock.get_request()
        assert request is not None
        assert b'"images"' in request.content
        assert b'"documents"' in request.content
        assert b'"rossum_url"' in request.content


class TestAsyncErrorHandling:
    @pytest.mark.asyncio
    async def test_authentication_error(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=401,
            text="Unauthorized",
        )

        with pytest.raises(AuthenticationError) as exc_info:
            await async_client.create_chat()

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_server_error(
        self, httpx_mock: HTTPXMock, async_client: AsyncRossumAgentClient, agent_api_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{agent_api_url}/api/v1/chats",
            status_code=500,
            text="Internal error",
        )

        with pytest.raises(ServerError) as exc_info:
            await async_client.create_chat()

        assert exc_info.value.status_code == 500
