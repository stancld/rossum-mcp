"""Tests for relation and document relation search functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.domain_logic.resources import Resource
from rossum_mcp.tools.search.relations import _list_document_relations, _list_relations


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestListRelations:
    @pytest.mark.asyncio
    async def test_returns_items(self, mock_client: AsyncMock) -> None:
        items = [{"id": 1, "type": "relation"}, {"id": 2, "type": "relation"}]

        async def mock_fetch(resource, **filters):
            assert resource == Resource.Relation
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_relations(mock_client)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_passes_kwargs_as_filters(self, mock_client: AsyncMock) -> None:
        captured_filters: dict = {}

        async def mock_fetch(resource, **filters):
            captured_filters.update(filters)
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_fetch

        await _list_relations(mock_client, annotation=123, type="parent")

        assert captured_filters["annotation"] == 123
        assert captured_filters["type"] == "parent"


@pytest.mark.unit
class TestListDocumentRelations:
    @pytest.mark.asyncio
    async def test_returns_items(self, mock_client: AsyncMock) -> None:
        items = [{"id": 1}]

        async def mock_fetch(resource, **filters):
            assert resource == Resource.DocumentRelation
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_document_relations(mock_client)

        assert len(result) == 1
