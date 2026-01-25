"""Rossum Agent API client implementations."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Literal

import httpx

from rossum_agent_client.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    RossumAgentError,
    ServerError,
    ValidationError,
)
from rossum_agent_client.models.requests import CreateChatRequest, DocumentContent, ImageContent, MessageRequest
from rossum_agent_client.models.responses import (
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

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)

type SSEEvent = StepEvent | StreamDoneEvent | FileCreatedEvent | SubAgentProgressEvent | SubAgentTextEvent


class BaseClient:
    """Base client with shared functionality."""

    def __init__(
        self,
        agent_api_url: str,
        rossum_api_base_url: str,
        token: str,
        timeout: float = 300.0,
    ) -> None:
        self.agent_api_url = agent_api_url.rstrip("/")
        self.rossum_api_base_url = rossum_api_base_url
        self.token = token
        self.timeout = timeout

    def _get_headers(self) -> dict[str, str]:
        return {
            "X-Rossum-Token": self.token,
            "X-Rossum-Api-Url": self.rossum_api_base_url,
            "Content-Type": "application/json",
        }

    def _handle_error(self, response: httpx.Response) -> None:
        status = response.status_code
        body = response.text

        match status:
            case s if 300 <= s < 400:
                location = response.headers.get("Location", "unknown")
                raise RossumAgentError(f"Unexpected redirect to {location}", status, body)
            case 401:
                raise AuthenticationError("Authentication failed", status, body)
            case 404:
                raise NotFoundError("Resource not found", status, body)
            case 422:
                raise ValidationError("Validation error", status, body)
            case 429:
                retry_after = response.headers.get("Retry-After")
                raise RateLimitError(
                    "Rate limit exceeded",
                    status,
                    body,
                    int(retry_after) if retry_after else None,
                )
            case s if s >= 500:
                raise ServerError(f"Server error: {status}", status, body)
            case s if s >= 400:
                raise RossumAgentError(f"Request failed: {status}", status, body)

    def _parse_sse_event(self, event_type: str, data: str) -> SSEEvent | None:
        """Parse an SSE event into the appropriate model."""
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("Failed to parse SSE event data as JSON: event_type=%s, data=%r", event_type, data[:200])
            return None

        match event_type:
            case "step":
                return StepEvent.model_validate(parsed)
            case "done":
                return StreamDoneEvent.model_validate(parsed)
            case "file_created":
                return FileCreatedEvent.model_validate(parsed)
            case "sub_agent_progress":
                return SubAgentProgressEvent.model_validate(parsed)
            case "sub_agent_text":
                return SubAgentTextEvent.model_validate(parsed)
            case "error":
                return StepEvent.model_validate(parsed)
            case _:
                logger.debug("Unknown SSE event type: %s", event_type)
                return None


class RossumAgentClient(BaseClient):
    """Synchronous client for Rossum Agent API."""

    def __init__(self, agent_api_url: str, rossum_api_base_url: str, token: str, timeout: float = 300.0) -> None:
        super().__init__(agent_api_url, rossum_api_base_url, token, timeout)
        self._client = httpx.Client(timeout=timeout)

    def _request(
        self,
        method: str,
        url: str,
        *,
        expected_status: int = 200,
        headers: dict[str, str] | None = None,
        json: dict[str, str | int | list[dict[str, str]]] | None = None,
        params: dict[str, int] | None = None,
    ) -> httpx.Response:
        """Execute a request."""
        response = self._client.request(method, url, headers=headers, json=json, params=params)
        if response.status_code != expected_status:
            self._handle_error(response)
        return response

    def __enter__(self) -> RossumAgentClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._client.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def health_check(self) -> HealthResponse:
        """Check API health and dependencies."""
        response = self._request("GET", f"{self.agent_api_url}/api/v1/health")
        return HealthResponse.model_validate(response.json())

    def create_chat(self, mcp_mode: Literal["read-only", "read-write"] = "read-only") -> ChatResponse:
        """Create a new chat session."""
        request = CreateChatRequest(mcp_mode=mcp_mode)
        response = self._request(
            "POST",
            f"{self.agent_api_url}/api/v1/chats",
            headers=self._get_headers(),
            json=request.model_dump(),
            expected_status=201,
        )
        return ChatResponse.model_validate(response.json())

    def list_chats(self, limit: int = 50, offset: int = 0) -> ChatListResponse:
        """List chat sessions for the authenticated user."""
        response = self._request(
            "GET",
            f"{self.agent_api_url}/api/v1/chats",
            headers=self._get_headers(),
            params={"limit": limit, "offset": offset},
        )
        return ChatListResponse.model_validate(response.json())

    def get_chat(self, chat_id: str) -> ChatDetail:
        """Get detailed information about a chat session."""
        response = self._request(
            "GET",
            f"{self.agent_api_url}/api/v1/chats/{chat_id}",
            headers=self._get_headers(),
        )
        return ChatDetail.model_validate(response.json())

    def delete_chat(self, chat_id: str) -> DeleteResponse:
        """Delete a chat session."""
        response = self._request(
            "DELETE",
            f"{self.agent_api_url}/api/v1/chats/{chat_id}",
            headers=self._get_headers(),
        )
        return DeleteResponse.model_validate(response.json())

    def send_message_stream(
        self,
        chat_id: str,
        content: str,
        *,
        images: list[ImageContent] | None = None,
        documents: list[DocumentContent] | None = None,
        rossum_url: str | None = None,
    ) -> Iterator[SSEEvent]:
        """Send a message and stream the agent's response via SSE."""
        request = MessageRequest(
            content=content,
            images=images,
            documents=documents,
            rossum_url=rossum_url,
        )

        with self._client.stream(
            "POST",
            f"{self.agent_api_url}/api/v1/chats/{chat_id}/messages",
            headers=self._get_headers(),
            json=request.model_dump(exclude_none=True),
            timeout=self.timeout,
        ) as response:
            if response.status_code != 200:
                response.read()
                self._handle_error(response)

            event_type: str | None = None
            data_buffer: list[str] = []

            for line in response.iter_lines():
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_buffer.append(line[5:].strip())
                elif line == "" and event_type and data_buffer:
                    data = "\n".join(data_buffer)
                    event = self._parse_sse_event(event_type, data)
                    if event:
                        yield event
                    event_type = None
                    data_buffer = []

    def list_files(self, chat_id: str) -> FileListResponse:
        """List all files for a chat session."""
        response = self._request(
            "GET",
            f"{self.agent_api_url}/api/v1/chats/{chat_id}/files",
            headers=self._get_headers(),
        )
        return FileListResponse.model_validate(response.json())

    def download_file(self, chat_id: str, filename: str) -> bytes:
        """Download a file from a chat session."""
        response = self._request(
            "GET",
            f"{self.agent_api_url}/api/v1/chats/{chat_id}/files/{filename}",
            headers=self._get_headers(),
        )
        return response.content


class AsyncRossumAgentClient(BaseClient):
    """Asynchronous client for Rossum Agent API."""

    def __init__(
        self,
        agent_api_url: str,
        rossum_api_base_url: str,
        token: str,
        timeout: float = 300.0,
    ) -> None:
        super().__init__(agent_api_url, rossum_api_base_url, token, timeout)
        self._client = httpx.AsyncClient(timeout=timeout)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        expected_status: int = 200,
        headers: dict[str, str] | None = None,
        json: dict[str, str | int | list[dict[str, str]]] | None = None,
        params: dict[str, int] | None = None,
    ) -> httpx.Response:
        """Execute a request."""
        response = await self._client.request(method, url, headers=headers, json=json, params=params)
        if response.status_code != expected_status:
            self._handle_error(response)
        return response

    async def __aenter__(self) -> AsyncRossumAgentClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self._client.aclose()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def health_check(self) -> HealthResponse:
        """Check API health and dependencies."""
        response = await self._request("GET", f"{self.agent_api_url}/api/v1/health")
        return HealthResponse.model_validate(response.json())

    async def create_chat(self, mcp_mode: Literal["read-only", "read-write"] = "read-only") -> ChatResponse:
        """Create a new chat session."""
        request = CreateChatRequest(mcp_mode=mcp_mode)
        response = await self._request(
            "POST",
            f"{self.agent_api_url}/api/v1/chats",
            headers=self._get_headers(),
            json=request.model_dump(),
            expected_status=201,
        )
        return ChatResponse.model_validate(response.json())

    async def list_chats(self, limit: int = 50, offset: int = 0) -> ChatListResponse:
        """List chat sessions for the authenticated user."""
        response = await self._request(
            "GET",
            f"{self.agent_api_url}/api/v1/chats",
            headers=self._get_headers(),
            params={"limit": limit, "offset": offset},
        )
        return ChatListResponse.model_validate(response.json())

    async def get_chat(self, chat_id: str) -> ChatDetail:
        """Get detailed information about a chat session."""
        response = await self._request(
            "GET",
            f"{self.agent_api_url}/api/v1/chats/{chat_id}",
            headers=self._get_headers(),
        )
        return ChatDetail.model_validate(response.json())

    async def delete_chat(self, chat_id: str) -> DeleteResponse:
        """Delete a chat session."""
        response = await self._request(
            "DELETE",
            f"{self.agent_api_url}/api/v1/chats/{chat_id}",
            headers=self._get_headers(),
        )
        return DeleteResponse.model_validate(response.json())

    async def send_message_stream(
        self,
        chat_id: str,
        content: str,
        *,
        images: list[ImageContent] | None = None,
        documents: list[DocumentContent] | None = None,
        rossum_url: str | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """Send a message and stream the agent's response via SSE."""
        request = MessageRequest(
            content=content,
            images=images,
            documents=documents,
            rossum_url=rossum_url,
        )

        async with self._client.stream(
            "POST",
            f"{self.agent_api_url}/api/v1/chats/{chat_id}/messages",
            headers=self._get_headers(),
            json=request.model_dump(exclude_none=True),
            timeout=self.timeout,
        ) as response:
            if response.status_code != 200:
                await response.aread()
                self._handle_error(response)

            event_type: str | None = None
            data_buffer: list[str] = []

            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_buffer.append(line[5:].strip())
                elif line == "" and event_type and data_buffer:
                    data = "\n".join(data_buffer)
                    event = self._parse_sse_event(event_type, data)
                    if event:
                        yield event
                    event_type = None
                    data_buffer = []

    async def list_files(self, chat_id: str) -> FileListResponse:
        """List all files for a chat session."""
        response = await self._request(
            "GET",
            f"{self.agent_api_url}/api/v1/chats/{chat_id}/files",
            headers=self._get_headers(),
        )
        return FileListResponse.model_validate(response.json())

    async def download_file(self, chat_id: str, filename: str) -> bytes:
        """Download a file from a chat session."""
        response = await self._request(
            "GET",
            f"{self.agent_api_url}/api/v1/chats/{chat_id}/files/{filename}",
            headers=self._get_headers(),
        )
        return response.content
