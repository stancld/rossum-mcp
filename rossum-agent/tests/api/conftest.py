"""Shared fixtures for API tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_chat_service() -> MagicMock:
    """Create a mock ChatService."""
    return MagicMock()


@pytest.fixture
def mock_agent_service() -> MagicMock:
    """Create a mock AgentService."""
    return MagicMock()


@pytest.fixture
def mock_file_service() -> MagicMock:
    """Create a mock FileService."""
    return MagicMock()


@pytest.fixture
def valid_headers() -> dict[str, str]:
    """Valid authentication headers."""
    return {"X-Rossum-Token": "test_token", "X-Rossum-Api-Url": "https://api.rossum.ai"}


def create_mock_httpx_client(
    status_code: int = 200, json_response: dict | None = None, side_effect: Exception | None = None
) -> AsyncMock:
    """Create a mocked httpx.AsyncClient for auth validation.

    Args:
        status_code: HTTP status code to return.
        json_response: JSON response to return (default: {"id": 12345}).
        side_effect: Exception to raise instead of returning a response.

    Returns:
        AsyncMock configured as an async context manager.
    """
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_response if json_response is not None else {"id": 12345}

    mock_async_client = AsyncMock()
    if side_effect:
        mock_async_client.get = AsyncMock(side_effect=side_effect)
    else:
        mock_async_client.get = AsyncMock(return_value=mock_response)
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=None)

    return mock_async_client


@pytest.fixture
def mock_httpx_success() -> AsyncMock:
    """Create mocked httpx client for successful auth."""
    return create_mock_httpx_client()


@pytest.fixture(autouse=True)
def reset_main_service_singletons() -> Generator[None, None, None]:
    """Reset service singletons in main module before and after each test.

    This fixture is autouse to ensure test isolation - each test starts with
    fresh singleton state and doesn't leak state to other tests.
    """
    import rossum_agent.api.main as main_module

    original_chat = main_module._chat_service
    original_agent = main_module._agent_service
    original_file = main_module._file_service

    main_module._chat_service = None
    main_module._agent_service = None
    main_module._file_service = None

    try:
        yield
    finally:
        main_module._chat_service = original_chat
        main_module._agent_service = original_agent
        main_module._file_service = original_file


@pytest.fixture(autouse=True)
def reset_route_service_getters() -> Generator[None, None, None]:
    """Reset service getter functions in route modules before and after each test.

    This ensures route modules don't leak configured getters between tests.
    Each test starts with service getters set to None (unconfigured state).
    """
    import rossum_agent.api.routes.chats as chats_module
    import rossum_agent.api.routes.files as files_module
    import rossum_agent.api.routes.health as health_module
    import rossum_agent.api.routes.messages as messages_module

    original_health_chat = health_module._get_chat_service
    original_chats_chat = chats_module._get_chat_service
    original_messages_chat = messages_module._get_chat_service
    original_messages_agent = messages_module._get_agent_service
    original_files_chat = files_module._get_chat_service
    original_files_file = files_module._get_file_service

    health_module._get_chat_service = None
    chats_module._get_chat_service = None
    messages_module._get_chat_service = None
    messages_module._get_agent_service = None
    files_module._get_chat_service = None
    files_module._get_file_service = None

    try:
        yield
    finally:
        health_module._get_chat_service = original_health_chat
        chats_module._get_chat_service = original_chats_chat
        messages_module._get_chat_service = original_messages_chat
        messages_module._get_agent_service = original_messages_agent
        files_module._get_chat_service = original_files_chat
        files_module._get_file_service = original_files_file
