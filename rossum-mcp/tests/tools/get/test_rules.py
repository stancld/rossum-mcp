"""Tests for get_rule operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_queue, create_mock_rule
from rossum_mcp.tools.get.registry import _get_rule


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestGetRule:
    """Tests for get_rule tool."""

    @pytest.mark.asyncio
    async def test_get_rule_success(self, mock_client: AsyncMock) -> None:
        """Test successful rule retrieval."""
        mock_rule = create_mock_rule(id=5, name="Test Rule")
        mock_client.retrieve_rule.return_value = mock_rule

        result = await _get_rule(mock_client, 5)

        assert result.id == 5
        assert result.name == "Test Rule"
        mock_client.retrieve_rule.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_get_rule_resolves_workspaces(self, mock_client: AsyncMock) -> None:
        """Test that workspace URLs are resolved from queue data."""
        mock_rule = create_mock_rule(
            id=5,
            name="Invoice Rule",
            queues=[
                "https://api.test.rossum.ai/v1/queues/10",
                "https://api.test.rossum.ai/v1/queues/20",
            ],
        )
        mock_client.retrieve_rule.return_value = mock_rule

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

        async def mock_fetch_all(resource, **filters):
            for item in mock_queues:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _get_rule(mock_client, 5)

        assert result.id == 5
        assert result.name == "Invoice Rule"
        assert sorted(result.workspaces) == [
            "https://api.test.rossum.ai/v1/workspaces/100",
            "https://api.test.rossum.ai/v1/workspaces/200",
        ]

    @pytest.mark.asyncio
    async def test_get_rule_empty_workspaces_when_no_queues(self, mock_client: AsyncMock) -> None:
        """Test that workspaces is empty when rule has no queues."""
        mock_rule = create_mock_rule(id=5, name="Unassigned Rule", queues=[])
        mock_client.retrieve_rule.return_value = mock_rule

        result = await _get_rule(mock_client, 5)

        assert result.id == 5
        assert result.workspaces == []
