"""Shared fixtures for API tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.agent.models import FinalAnswerStep
from rossum_agent.api.main import app
from rossum_agent.api.models.schemas import StreamDoneEvent
from rossum_agent.api.routes.messages import limiter
from rossum_agent.api.shutdown import shutdown_state

if TYPE_CHECKING:
    from collections.abc import Callable, Generator


@pytest.fixture(autouse=True)
def mock_chat_summary():
    """Prevent real AWS Bedrock calls from _generate_chat_summary in route tests."""
    with patch("rossum_agent.api.routes.messages.generate_chat_summary", return_value=None):
        yield


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """Reset rate limiter storage before each test to prevent cross-test rate limit bleed."""
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def reset_shutdown_state() -> Generator[None, None, None]:
    """Reset graceful shutdown state before each test."""
    shutdown_state.shutting_down = False
    shutdown_state.active_requests = 0
    yield
    shutdown_state.shutting_down = False
    shutdown_state.active_requests = 0


@pytest.fixture(autouse=True)
def reset_app_state() -> Generator[None, None, None]:
    """Reset app.state before and after each test to ensure isolation.

    This fixture is autouse to ensure test isolation - each test starts with
    fresh app.state and doesn't leak state to other tests.
    """
    original_state = {}
    for attr in ("chat_service", "agent_service", "file_service", "valkey_connection"):
        if hasattr(app.state, attr):
            original_state[attr] = getattr(app.state, attr)
            delattr(app.state, attr)

    try:
        yield
    finally:
        for attr in ("chat_service", "agent_service", "file_service", "valkey_connection"):
            if hasattr(app.state, attr):
                delattr(app.state, attr)
        for attr, value in original_state.items():
            setattr(app.state, attr, value)


@pytest.fixture
def mock_chat_service() -> MagicMock:
    """Create a mock ChatService."""
    return MagicMock()


@pytest.fixture
def mock_agent_service() -> MagicMock:
    """Create a mock AgentService."""
    mock = MagicMock()
    # Intermediate saves use get_last_memory; return None so they are skipped in tests
    mock.get_last_memory.return_value = None
    return mock


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


@pytest.fixture
def mock_run_agent_factory() -> Callable[[], tuple[list, Callable]]:
    """Factory fixture for creating mock run_agent generators with call tracking.

    Returns a factory function that creates:
        - A list to capture call kwargs
        - An async generator function that yields standard success events
    """

    def create_mock() -> tuple[list, Callable]:
        calls: list[dict] = []

        async def mock_run_agent(*args, **kwargs):
            calls.append(kwargs)
            yield FinalAnswerStep(step_number=1, final_answer="Done!")
            yield StreamDoneEvent(total_steps=1, input_tokens=100, output_tokens=50)

        return calls, mock_run_agent

    return create_mock
