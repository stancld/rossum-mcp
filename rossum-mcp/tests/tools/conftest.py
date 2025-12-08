"""Shared fixtures for tools tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture
def mock_env_read_write(monkeypatch: MonkeyPatch) -> None:
    """Set up environment variables for read-write mode testing."""
    monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
    monkeypatch.setenv("ROSSUM_API_TOKEN", "test-token-123")
    monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
    monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")


@pytest.fixture
def mock_env_read_only(monkeypatch: MonkeyPatch) -> None:
    """Set up environment variables for read-only mode testing."""
    monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
    monkeypatch.setenv("ROSSUM_API_TOKEN", "test-token-123")
    monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")


@pytest.fixture
def mock_mcp() -> Mock:
    """Create a mock FastMCP instance."""
    mcp = Mock()
    mcp.tool = Mock(side_effect=lambda **kwargs: lambda fn: fn)
    return mcp


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock()
    return client
