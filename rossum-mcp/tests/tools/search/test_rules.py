"""Tests for _list_rules workspace resolution."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_queue, create_mock_rule
from rossum_api.domain_logic.resources import Resource
from rossum_mcp.tools.search.registry import _list_rules


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestListRules:
    """Tests for _list_rules workspace resolution."""

    @pytest.mark.asyncio
    async def test_list_rules_resolves_workspaces(self, mock_client: AsyncMock) -> None:
        """Test that workspace URLs are resolved from queue data."""
        mock_rules = [
            create_mock_rule(
                id=1,
                name="Rule 1",
                queues=[
                    "https://api.test.rossum.ai/v1/queues/10",
                    "https://api.test.rossum.ai/v1/queues/20",
                ],
            ),
            create_mock_rule(
                id=2,
                name="Rule 2",
                queues=["https://api.test.rossum.ai/v1/queues/20"],
            ),
        ]
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
            items = mock_rules if resource == Resource.Rule else mock_queues
            for item in items:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_rules(mock_client)

        assert len(result) == 2
        assert sorted(result[0].workspaces) == [
            "https://api.test.rossum.ai/v1/workspaces/100",
            "https://api.test.rossum.ai/v1/workspaces/200",
        ]
        assert result[1].workspaces == ["https://api.test.rossum.ai/v1/workspaces/200"]

    @pytest.mark.asyncio
    async def test_list_rules_empty_workspaces_when_no_queues(self, mock_client: AsyncMock) -> None:
        """Test that workspaces is empty when rule has no queues."""
        mock_rules = [create_mock_rule(id=1, name="Rule 1", queues=[])]

        async def mock_fetch_all(resource, **filters):
            for rule in mock_rules:
                yield rule

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_rules(mock_client)

        assert len(result) == 1
        assert result[0].workspaces == []

    @pytest.mark.asyncio
    async def test_list_rules_filter_by_workspace_id(self, mock_client: AsyncMock) -> None:
        """Test that workspace_id filters rules to those belonging to the workspace."""
        mock_rules = [
            create_mock_rule(
                id=1,
                name="Rule A",
                queues=["https://api.test.rossum.ai/v1/queues/10"],
            ),
            create_mock_rule(
                id=2,
                name="Rule B",
                queues=["https://api.test.rossum.ai/v1/queues/20"],
            ),
            create_mock_rule(
                id=3,
                name="Rule C",
                queues=[
                    "https://api.test.rossum.ai/v1/queues/10",
                    "https://api.test.rossum.ai/v1/queues/20",
                ],
            ),
        ]
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
            items = mock_rules if resource == Resource.Rule else mock_queues
            for item in items:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_rules(mock_client, workspace_id=100)

        assert len(result) == 2
        assert {r.id for r in result} == {1, 3}

    @pytest.mark.asyncio
    async def test_list_rules_filter_by_workspace_id_no_match(self, mock_client: AsyncMock) -> None:
        """Test that workspace_id returns empty list when no rules belong to the workspace."""
        mock_rules = [
            create_mock_rule(
                id=1,
                name="Rule A",
                queues=["https://api.test.rossum.ai/v1/queues/10"],
            ),
        ]
        mock_queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
        ]

        async def mock_fetch_all(resource, **filters):
            items = mock_rules if resource == Resource.Rule else mock_queues
            for item in items:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_rules(mock_client, workspace_id=999)

        assert len(result) == 0
