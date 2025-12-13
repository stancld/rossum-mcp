"""Tests for rossum_mcp.tools.relations module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.relation import Relation


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
    client._deserializer = Mock()
    return client


@pytest.fixture
def mock_mcp() -> Mock:
    """Create a mock FastMCP instance that captures registered tools."""
    tools: dict = {}

    def tool_decorator(**kwargs):
        def wrapper(fn):
            tools[fn.__name__] = fn
            return fn

        return wrapper

    mcp = Mock()
    mcp.tool = tool_decorator
    mcp._tools = tools
    return mcp


@pytest.mark.unit
class TestGetRelation:
    """Tests for get_relation tool."""

    @pytest.mark.asyncio
    async def test_get_relation_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful relation retrieval."""
        from rossum_mcp.tools.relations import register_relation_tools

        register_relation_tools(mock_mcp, mock_client)

        mock_relation = create_mock_relation(id=100, type="duplicate", key="xyz789")
        mock_client._http_client.fetch_one.return_value = {"id": 100}
        mock_client._deserializer.return_value = mock_relation

        get_relation = mock_mcp._tools["get_relation"]
        result = await get_relation(relation_id=100)

        assert result.id == 100
        assert result.type == "duplicate"
        assert result.key == "xyz789"
        mock_client._http_client.fetch_one.assert_called_once_with(Resource.Relation, 100)

    @pytest.mark.asyncio
    async def test_get_relation_edit_type(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test retrieving an edit-type relation."""
        from rossum_mcp.tools.relations import register_relation_tools

        register_relation_tools(mock_mcp, mock_client)

        mock_relation = create_mock_relation(id=200, type="edit", key=None)
        mock_client._http_client.fetch_one.return_value = {"id": 200}
        mock_client._deserializer.return_value = mock_relation

        get_relation = mock_mcp._tools["get_relation"]
        result = await get_relation(relation_id=200)

        assert result.id == 200
        assert result.type == "edit"
        assert result.key is None


@pytest.mark.unit
class TestListRelations:
    """Tests for list_relations tool."""

    @pytest.mark.asyncio
    async def test_list_relations_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful relations listing."""
        from rossum_mcp.tools.relations import register_relation_tools

        register_relation_tools(mock_mcp, mock_client)

        mock_rel1 = create_mock_relation(id=1, type="duplicate")
        mock_rel2 = create_mock_relation(id=2, type="edit")

        async def async_iter():
            for item in [mock_rel1, mock_rel2]:
                yield item

        mock_client.list_relations = Mock(side_effect=lambda **kwargs: async_iter())

        list_relations = mock_mcp._tools["list_relations"]
        result = await list_relations()

        assert result.count == 2
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_list_relations_with_type_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test relations listing filtered by type."""
        from rossum_mcp.tools.relations import register_relation_tools

        register_relation_tools(mock_mcp, mock_client)

        mock_rel = create_mock_relation(id=1, type="duplicate")

        async def async_iter():
            yield mock_rel

        mock_client.list_relations = Mock(side_effect=lambda **kwargs: async_iter())

        list_relations = mock_mcp._tools["list_relations"]
        result = await list_relations(type="duplicate")

        assert result.count == 1
        mock_client.list_relations.assert_called_once_with(type="duplicate")

    @pytest.mark.asyncio
    async def test_list_relations_with_parent_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test relations listing filtered by parent."""
        from rossum_mcp.tools.relations import register_relation_tools

        register_relation_tools(mock_mcp, mock_client)

        mock_rel = create_mock_relation(id=1)

        async def async_iter():
            yield mock_rel

        mock_client.list_relations = Mock(side_effect=lambda **kwargs: async_iter())

        list_relations = mock_mcp._tools["list_relations"]
        result = await list_relations(parent=500)

        assert result.count == 1
        mock_client.list_relations.assert_called_once_with(parent=500)

    @pytest.mark.asyncio
    async def test_list_relations_with_annotation_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test relations listing filtered by annotation."""
        from rossum_mcp.tools.relations import register_relation_tools

        register_relation_tools(mock_mcp, mock_client)

        mock_rel = create_mock_relation(id=1)

        async def async_iter():
            yield mock_rel

        mock_client.list_relations = Mock(side_effect=lambda **kwargs: async_iter())

        list_relations = mock_mcp._tools["list_relations"]
        result = await list_relations(annotation=600)

        assert result.count == 1
        mock_client.list_relations.assert_called_once_with(annotation=600)

    @pytest.mark.asyncio
    async def test_list_relations_with_key_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test relations listing filtered by key."""
        from rossum_mcp.tools.relations import register_relation_tools

        register_relation_tools(mock_mcp, mock_client)

        mock_rel = create_mock_relation(id=1, key="specific_key")

        async def async_iter():
            yield mock_rel

        mock_client.list_relations = Mock(side_effect=lambda **kwargs: async_iter())

        list_relations = mock_mcp._tools["list_relations"]
        result = await list_relations(key="specific_key")

        assert result.count == 1
        mock_client.list_relations.assert_called_once_with(key="specific_key")

    @pytest.mark.asyncio
    async def test_list_relations_empty(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test relations listing when none exist."""
        from rossum_mcp.tools.relations import register_relation_tools

        register_relation_tools(mock_mcp, mock_client)

        async def async_iter():
            return
            yield

        mock_client.list_relations = Mock(side_effect=lambda **kwargs: async_iter())

        list_relations = mock_mcp._tools["list_relations"]
        result = await list_relations()

        assert result.count == 0
        assert result.results == []
