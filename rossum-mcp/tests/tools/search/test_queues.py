"""Tests for queue search functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_queue
from rossum_mcp.tools.search.queues import _list_queues


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestListQueues:
    @pytest.mark.asyncio
    async def test_transforms_to_list_item(self, mock_client: AsyncMock) -> None:
        """Settings are omitted in the QueueListItem output."""
        queues = [create_mock_queue(id=1, name="Q1", settings={"lang": "en"})]

        async def mock_fetch(resource, **filters):
            for q in queues:
                yield q

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_queues(mock_client)

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].name == "Q1"
        assert result[0].settings == "<omitted>"

    @pytest.mark.asyncio
    async def test_filter_by_workspace_id(self, mock_client: AsyncMock) -> None:
        queues = [
            create_mock_queue(id=1, name="Q1", workspace="https://api.test.rossum.ai/v1/workspaces/100"),
            create_mock_queue(id=2, name="Q2", workspace="https://api.test.rossum.ai/v1/workspaces/200"),
        ]

        captured_filters: dict = {}

        async def mock_fetch(resource, **filters):
            captured_filters.update(filters)
            for q in queues:
                yield q

        mock_client._http_client.cursor_fetch_all = mock_fetch

        await _list_queues(mock_client, workspace_id=100)

        assert captured_filters["workspace"] == 100

    @pytest.mark.asyncio
    async def test_regex_name_filter(self, mock_client: AsyncMock) -> None:
        queues = [
            create_mock_queue(id=1, name="Invoice Queue"),
            create_mock_queue(id=2, name="PO Queue"),
            create_mock_queue(id=3, name="Invoice-DE Queue"),
        ]

        async def mock_fetch(resource, **filters):
            for q in queues:
                yield q

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_queues(mock_client, name="^Invoice", use_regex=True)

        assert len(result) == 2
        assert {r.id for r in result} == {1, 3}

    @pytest.mark.asyncio
    async def test_regex_bypasses_api_name_filter(self, mock_client: AsyncMock) -> None:
        """When use_regex=True, name is not sent as API filter."""
        captured_filters: dict = {}

        async def mock_fetch(resource, **filters):
            captured_filters.update(filters)
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_fetch

        await _list_queues(mock_client, name="test", use_regex=True)

        assert "name" not in captured_filters

    @pytest.mark.asyncio
    async def test_counts_none_becomes_none(self, mock_client: AsyncMock) -> None:
        """Queue with counts=None keeps None in list item (not empty dict)."""
        queues = [create_mock_queue(id=1, counts=None)]

        async def mock_fetch(resource, **filters):
            for q in queues:
                yield q

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_queues(mock_client)

        assert result[0].counts is None
