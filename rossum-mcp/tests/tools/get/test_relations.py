"""Tests for rossum_mcp.tools.get.registry and rossum_mcp.tools.search.registry (relations)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.relation import Relation
from rossum_mcp.tools.get.registry import _get_relation
from rossum_mcp.tools.search.registry import _list_relations


def create_mock_relation(**kwargs) -> Relation:
    """Create a mock Relation dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/relations/1",
        "type": "duplicate",
        "key": "abc123",
        "parent": "https://api.test.rossum.ai/v1/annotations/100",
        "annotations": [
            "https://api.test.rossum.ai/v1/annotations/100",
            "https://api.test.rossum.ai/v1/annotations/101",
        ],
    }
    defaults.update(kwargs)
    return Relation(**defaults)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestGetRelation:
    """Tests for get_relation tool."""

    @pytest.mark.asyncio
    async def test_get_relation_success(self, mock_client: AsyncMock) -> None:
        """Test successful relation retrieval."""
        from rossum_api.domain_logic.resources import Resource

        mock_relation = create_mock_relation(id=100, type="duplicate", key="xyz789")
        mock_client._http_client.fetch_one.return_value = {"id": 100}
        mock_client._deserializer = Mock(return_value=mock_relation)

        result = await _get_relation(mock_client, relation_id=100)

        assert result.id == 100
        assert result.type == "duplicate"
        assert result.key == "xyz789"
        mock_client._http_client.fetch_one.assert_called_once_with(Resource.Relation, 100)

    @pytest.mark.asyncio
    async def test_get_relation_edit_type(self, mock_client: AsyncMock) -> None:
        """Test retrieving an edit-type relation."""
        mock_relation = create_mock_relation(id=200, type="edit", key=None)
        mock_client._http_client.fetch_one.return_value = {"id": 200}
        mock_client._deserializer = Mock(return_value=mock_relation)

        result = await _get_relation(mock_client, relation_id=200)

        assert result.id == 200
        assert result.type == "edit"
        assert result.key is None


@pytest.mark.unit
class TestListRelations:
    """Tests for list_relations tool."""

    @pytest.mark.asyncio
    async def test_list_relations_success(self, mock_client: AsyncMock) -> None:
        """Test successful relations listing."""
        mock_rel1 = create_mock_relation(id=1, type="duplicate")
        mock_rel2 = create_mock_relation(id=2, type="edit")

        async def mock_cursor_fetch_all(resource, **filters):
            for item in [mock_rel1, mock_rel2]:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_relations(mock_client)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_relations_with_type_filter(self, mock_client: AsyncMock) -> None:
        """Test relations listing filtered by type."""
        mock_rel = create_mock_relation(id=1, type="duplicate")
        received_filters: dict = {}

        async def mock_cursor_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_rel

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_relations(mock_client, type="duplicate")

        assert len(result) == 1
        assert received_filters["type"] == "duplicate"

    @pytest.mark.asyncio
    async def test_list_relations_with_parent_filter(self, mock_client: AsyncMock) -> None:
        """Test relations listing filtered by parent."""
        mock_rel = create_mock_relation(id=1)
        received_filters: dict = {}

        async def mock_cursor_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_rel

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_relations(mock_client, parent=500)

        assert len(result) == 1
        assert received_filters["parent"] == 500

    @pytest.mark.asyncio
    async def test_list_relations_with_annotation_filter(self, mock_client: AsyncMock) -> None:
        """Test relations listing filtered by annotation."""
        mock_rel = create_mock_relation(id=1)
        received_filters: dict = {}

        async def mock_cursor_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_rel

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_relations(mock_client, annotation=600)

        assert len(result) == 1
        assert received_filters["annotation"] == 600

    @pytest.mark.asyncio
    async def test_list_relations_with_key_filter(self, mock_client: AsyncMock) -> None:
        """Test relations listing filtered by key."""
        mock_rel = create_mock_relation(id=1, key="specific_key")
        received_filters: dict = {}

        async def mock_cursor_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_rel

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_relations(mock_client, key="specific_key")

        assert len(result) == 1
        assert received_filters["key"] == "specific_key"

    @pytest.mark.asyncio
    async def test_list_relations_empty(self, mock_client: AsyncMock) -> None:
        """Test relations listing when none exist."""

        async def mock_cursor_fetch_all(resource, **filters):
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_relations(mock_client)

        assert len(result) == 0
        assert result == []

    @pytest.mark.asyncio
    async def test_list_relations_skips_broken_items(self, mock_client: AsyncMock) -> None:
        """Test list_relations gracefully skips items that fail deserialization."""
        mock_rel = create_mock_relation(id=1, type="duplicate")

        def mock_deserializer(resource, raw):
            if raw.get("id") == 2:
                raise ValueError("broken relation")
            return mock_rel

        mock_client._deserializer = mock_deserializer

        async def mock_cursor_fetch_all(resource, **filters):
            yield {"id": 1, "type": "duplicate"}
            yield {"id": 2, "type": "broken"}
            yield {"id": 3, "type": "edit"}

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_relations(mock_client)

        assert len(result) == 2
