"""Tests for annotation search functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_annotation, create_mock_queue
from rossum_api.domain_logic.resources import Resource
from rossum_mcp.tools.search.annotations import _list_annotations


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestListAnnotations:
    @pytest.mark.asyncio
    async def test_resolves_workspace_from_queue(self, mock_client: AsyncMock) -> None:
        annotations = [
            create_mock_annotation(id=1, queue="https://api.test.rossum.ai/v1/queues/10"),
        ]
        queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
        ]

        async def mock_fetch(resource, **filters):
            items = annotations if resource == Resource.Annotation else queues
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_annotations(mock_client, queue_id=10)

        assert len(result) == 1
        assert result[0].workspaces == ["https://api.test.rossum.ai/v1/workspaces/100"]

    @pytest.mark.asyncio
    async def test_filter_by_workspace_id(self, mock_client: AsyncMock) -> None:
        annotations = [
            create_mock_annotation(id=1, queue="https://api.test.rossum.ai/v1/queues/10"),
            create_mock_annotation(id=2, queue="https://api.test.rossum.ai/v1/queues/20"),
        ]
        queues = [
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

        async def mock_fetch(resource, **filters):
            items = annotations if resource == Resource.Annotation else queues
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_annotations(mock_client, queue_id=10, workspace_id=100)

        assert len(result) == 1
        assert result[0].id == 1

    @pytest.mark.asyncio
    async def test_workspace_id_no_match(self, mock_client: AsyncMock) -> None:
        annotations = [
            create_mock_annotation(id=1, queue="https://api.test.rossum.ai/v1/queues/10"),
        ]
        queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
        ]

        async def mock_fetch(resource, **filters):
            items = annotations if resource == Resource.Annotation else queues
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_annotations(mock_client, queue_id=10, workspace_id=999)

        assert result == []

    @pytest.mark.asyncio
    async def test_default_status_filter(self, mock_client: AsyncMock) -> None:
        """Default status filter includes importing, to_review, confirmed, exported."""
        captured_filters: dict = {}

        async def mock_fetch(resource, **filters):
            captured_filters.update(filters)
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_fetch

        await _list_annotations(mock_client, queue_id=10)

        assert captured_filters["status"] == "importing,to_review,confirmed,exported"

    @pytest.mark.asyncio
    async def test_unresolvable_queue_yields_empty_workspaces(self, mock_client: AsyncMock) -> None:
        annotations = [
            create_mock_annotation(id=1, queue="https://api.test.rossum.ai/v1/queues/999"),
        ]

        call_count = 0

        async def mock_fetch(resource, **filters):
            nonlocal call_count
            items = annotations if call_count == 0 else []
            call_count += 1
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_annotations(mock_client, queue_id=999)

        assert len(result) == 1
        assert result[0].workspaces == []
