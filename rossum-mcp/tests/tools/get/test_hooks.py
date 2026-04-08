"""Tests for get_hook operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_hook, create_mock_queue
from rossum_mcp.tools.get.registry import _get_hook


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestGetHook:
    """Tests for get_hook tool."""

    @pytest.mark.asyncio
    async def test_get_hook_success(self, mock_client: AsyncMock) -> None:
        """Test successful hook retrieval."""
        mock_hook = create_mock_hook(id=5, name="Test Hook")
        mock_client.retrieve_hook.return_value = mock_hook

        result = await _get_hook(mock_client, 5)

        assert result.id == 5
        assert result.name == "Test Hook"
        mock_client.retrieve_hook.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_get_hook_resolves_workspaces(self, mock_client: AsyncMock) -> None:
        """Test that workspace URLs are resolved from queue data."""
        mock_hook = create_mock_hook(
            id=5,
            name="Invoice Hook",
            queues=[
                "https://api.test.rossum.ai/v1/queues/10",
                "https://api.test.rossum.ai/v1/queues/20",
            ],
        )
        mock_client.retrieve_hook.return_value = mock_hook

        mock_queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
            create_mock_queue(
                id=20,
                url="https://api.test.rossum.ai/v1/queues/20",
                workspace="https://api.test.rossum.ai/v1/workspaces/200",
            ),
        ]

        async def mock_cursor_fetch_all(resource, **filters):
            for item in mock_queues:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _get_hook(mock_client, 5)

        assert result.id == 5
        assert result.name == "Invoice Hook"
        assert sorted(result.workspaces) == [
            "https://api.test.rossum.ai/v1/workspaces/100",
            "https://api.test.rossum.ai/v1/workspaces/200",
        ]

    @pytest.mark.asyncio
    async def test_get_hook_empty_workspaces_when_no_queues(self, mock_client: AsyncMock) -> None:
        """Test that workspaces is empty when hook has no queues."""
        mock_hook = create_mock_hook(id=5, name="Unassigned Hook", queues=[])
        mock_client.retrieve_hook.return_value = mock_hook

        result = await _get_hook(mock_client, 5)

        assert result.id == 5
        assert result.workspaces == []
