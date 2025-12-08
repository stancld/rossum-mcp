"""Tests for rossum_mcp.tools.document_relations module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.document_relation import DocumentRelation


def create_mock_document_relation(**kwargs) -> DocumentRelation:
    """Create a mock DocumentRelation dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/document_relations/1",
        "type": "export",
        "annotation": "https://api.test.rossum.ai/v1/annotations/100",
        "key": "export_key",
        "documents": [
            "https://api.test.rossum.ai/v1/documents/200",
            "https://api.test.rossum.ai/v1/documents/201",
        ],
    }
    defaults.update(kwargs)
    return DocumentRelation(**defaults)


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
class TestGetDocumentRelation:
    """Tests for get_document_relation tool."""

    @pytest.mark.asyncio
    async def test_get_document_relation_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful document relation retrieval."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_doc_relation = create_mock_document_relation(id=100, type="export", key="exported_file_key")
        mock_client._http_client.fetch_one.return_value = {"id": 100}
        mock_client._deserializer.return_value = mock_doc_relation

        get_document_relation = mock_mcp._tools["get_document_relation"]
        result = await get_document_relation(document_relation_id=100)

        assert result["id"] == 100
        assert result["type"] == "export"
        assert result["key"] == "exported_file_key"
        mock_client._http_client.fetch_one.assert_called_once_with(Resource.DocumentRelation, 100)

    @pytest.mark.asyncio
    async def test_get_document_relation_einvoice_type(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test retrieving an einvoice-type document relation."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_doc_relation = create_mock_document_relation(id=200, type="einvoice", key=None)
        mock_client._http_client.fetch_one.return_value = {"id": 200}
        mock_client._deserializer.return_value = mock_doc_relation

        get_document_relation = mock_mcp._tools["get_document_relation"]
        result = await get_document_relation(document_relation_id=200)

        assert result["id"] == 200
        assert result["type"] == "einvoice"
        assert result["key"] is None


@pytest.mark.unit
class TestListDocumentRelations:
    """Tests for list_document_relations tool."""

    @pytest.mark.asyncio
    async def test_list_document_relations_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful document relations listing."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_dr1 = create_mock_document_relation(id=1, type="export")
        mock_dr2 = create_mock_document_relation(id=2, type="einvoice")

        async def async_iter():
            for item in [mock_dr1, mock_dr2]:
                yield item

        mock_client.list_document_relations = Mock(side_effect=lambda **kwargs: async_iter())

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations()

        assert result["count"] == 2
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_list_document_relations_with_type_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test document relations listing filtered by type."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_dr = create_mock_document_relation(id=1, type="export")

        async def async_iter():
            yield mock_dr

        mock_client.list_document_relations = Mock(side_effect=lambda **kwargs: async_iter())

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations(type="export")

        assert result["count"] == 1
        mock_client.list_document_relations.assert_called_once_with(type="export")

    @pytest.mark.asyncio
    async def test_list_document_relations_with_annotation_filter(
        self, mock_mcp: Mock, mock_client: AsyncMock
    ) -> None:
        """Test document relations listing filtered by annotation."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_dr = create_mock_document_relation(id=1)

        async def async_iter():
            yield mock_dr

        mock_client.list_document_relations = Mock(side_effect=lambda **kwargs: async_iter())

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations(annotation=500)

        assert result["count"] == 1
        mock_client.list_document_relations.assert_called_once_with(annotation=500)

    @pytest.mark.asyncio
    async def test_list_document_relations_with_documents_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test document relations listing filtered by documents."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_dr = create_mock_document_relation(id=1)

        async def async_iter():
            yield mock_dr

        mock_client.list_document_relations = Mock(side_effect=lambda **kwargs: async_iter())

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations(documents=700)

        assert result["count"] == 1
        mock_client.list_document_relations.assert_called_once_with(documents=700)

    @pytest.mark.asyncio
    async def test_list_document_relations_with_key_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test document relations listing filtered by key."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_dr = create_mock_document_relation(id=1, key="specific_key")

        async def async_iter():
            yield mock_dr

        mock_client.list_document_relations = Mock(side_effect=lambda **kwargs: async_iter())

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations(key="specific_key")

        assert result["count"] == 1
        mock_client.list_document_relations.assert_called_once_with(key="specific_key")

    @pytest.mark.asyncio
    async def test_list_document_relations_empty(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test document relations listing when none exist."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        async def async_iter():
            return
            yield

        mock_client.list_document_relations = Mock(side_effect=lambda **kwargs: async_iter())

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations()

        assert result["count"] == 0
        assert result["results"] == []
