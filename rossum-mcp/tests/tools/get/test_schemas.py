"""Tests for get_schema and get_schema_tree_structure operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_schema
from fastmcp.exceptions import ToolError
from rossum_api import APIClientError
from rossum_mcp.tools.get.handler import register_get_tools
from rossum_mcp.tools.get.registry import _get_schema


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
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
class TestGetSchema:
    """Tests for get_schema tool."""

    @pytest.mark.asyncio
    async def test_get_schema_success(self, mock_client: AsyncMock) -> None:
        """Test successful schema retrieval."""
        mock_schema = create_mock_schema(
            id=50,
            name="Invoice Schema",
            content=[
                {
                    "id": "header_section",
                    "label": "Header",
                    "children": [{"id": "invoice_number", "label": "Invoice Number"}],
                }
            ],
        )
        mock_client.retrieve_schema.return_value = mock_schema

        result = await _get_schema(mock_client, 50)

        assert result.id == 50
        assert result.name == "Invoice Schema"
        assert len(result.content) == 1
        mock_client.retrieve_schema.assert_called_once_with(50)

    @pytest.mark.asyncio
    async def test_get_schema_not_found(self, mock_client: AsyncMock) -> None:
        """Test schema not found returns error dict instead of raising exception."""
        mock_client.retrieve_schema.side_effect = APIClientError(
            method="GET",
            url="https://api.test/schemas/999",
            status_code=404,
            error=Exception("Not found"),
        )

        with pytest.raises(ToolError, match="Schema 999 not found"):
            await _get_schema(mock_client, 999)


@pytest.mark.unit
class TestGetSchemaTreeStructure:
    """Tests for get_schema_tree_structure tool."""

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful tree structure extraction."""
        register_get_tools(mock_mcp, mock_client)

        mock_schema = create_mock_schema(
            id=50,
            content=[
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {
                            "id": "invoice_number",
                            "label": "Invoice Number",
                            "category": "datapoint",
                            "type": "string",
                            "constraints": {"required": True},
                        },
                        {
                            "id": "invoice_date",
                            "label": "Invoice Date",
                            "category": "datapoint",
                            "type": "date",
                            "constraints": {"required": False},
                        },
                    ],
                },
                {
                    "id": "line_items_section",
                    "label": "Line Items",
                    "category": "section",
                    "children": [
                        {
                            "id": "line_items",
                            "label": "Line Items",
                            "category": "multivalue",
                            "children": {
                                "id": "line_item",
                                "label": "Line Item",
                                "category": "tuple",
                                "children": [
                                    {
                                        "id": "description",
                                        "label": "Description",
                                        "category": "datapoint",
                                        "type": "string",
                                    },
                                    {"id": "amount", "label": "Amount", "category": "datapoint", "type": "number"},
                                ],
                            },
                        }
                    ],
                },
            ],
        )
        mock_client.retrieve_schema.return_value = mock_schema

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        result = await get_schema_tree_structure(schema_id=50)

        assert len(result) == 2
        assert result[0]["id"] == "header_section"
        assert result[0]["label"] == "Header"
        assert result[0]["required"] is False
        assert result[0]["hidden"] is False
        assert len(result[0]["children"]) == 2
        assert result[0]["children"][0]["id"] == "invoice_number"
        assert result[0]["children"][0]["type"] == "string"
        assert result[0]["children"][0]["required"] is True
        assert result[0]["children"][0]["hidden"] is False
        assert result[0]["children"][1]["required"] is False
        assert result[0]["children"][1]["hidden"] is False
        assert result[1]["children"][0]["id"] == "line_items"
        assert result[1]["children"][0]["required"] is False
        assert result[1]["children"][0]["hidden"] is False
        assert result[1]["children"][0]["children"][0]["id"] == "line_item"
        assert result[1]["children"][0]["children"][0]["required"] is False
        assert result[1]["children"][0]["children"][0]["hidden"] is False

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_always_includes_boolean_flags(
        self, mock_mcp: Mock, mock_client: AsyncMock
    ) -> None:
        """Test that required/hidden are always present as booleans in tree structure."""
        register_get_tools(mock_mcp, mock_client)

        mock_schema = create_mock_schema(
            id=50,
            content=[
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {
                            "id": "invoice_number",
                            "label": "Invoice Number",
                            "category": "datapoint",
                            "type": "string",
                            "hidden": False,
                        },
                        {
                            "id": "internal_id",
                            "label": "Internal ID",
                            "category": "datapoint",
                            "type": "string",
                            "hidden": True,
                        },
                        {
                            "id": "no_hidden_key",
                            "label": "No Hidden Key",
                            "category": "datapoint",
                            "type": "string",
                        },
                    ],
                },
            ],
        )
        mock_client.retrieve_schema.return_value = mock_schema

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        result = await get_schema_tree_structure(schema_id=50)

        children = result[0]["children"]
        assert children[0]["required"] is False
        assert children[0]["hidden"] is False
        assert children[1]["required"] is False
        assert children[1]["hidden"] is True
        assert children[2]["required"] is False
        assert children[2]["hidden"] is False

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_not_found(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test tree structure raises ToolError when schema not found."""
        register_get_tools(mock_mcp, mock_client)

        mock_client.retrieve_schema.side_effect = APIClientError(
            method="GET",
            url="https://api.test/schemas/999",
            status_code=404,
            error=Exception("Not found"),
        )

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        with pytest.raises(ToolError, match="Schema 999 not found"):
            await get_schema_tree_structure(schema_id=999)

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_by_queue_id(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test tree structure via queue_id resolves schema automatically."""
        register_get_tools(mock_mcp, mock_client)

        mock_queue = Mock()
        mock_queue.schema = "https://api.test/v1/schemas/50"
        mock_client.retrieve_queue.return_value = mock_queue

        mock_schema = create_mock_schema(
            id=50,
            content=[
                {
                    "id": "section",
                    "label": "Section",
                    "category": "section",
                    "children": [{"id": "field1", "label": "Field 1", "category": "datapoint", "type": "string"}],
                }
            ],
        )
        mock_client.retrieve_schema.return_value = mock_schema

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        result = await get_schema_tree_structure(queue_id=100)

        mock_client.retrieve_queue.assert_called_once_with(100)
        mock_client.retrieve_schema.assert_called_once_with(50)
        assert len(result) == 1
        assert result[0]["id"] == "section"

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_no_args(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test tree structure raises ToolError when neither schema_id nor queue_id provided."""
        register_get_tools(mock_mcp, mock_client)

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        with pytest.raises(ToolError, match="Provide schema_id or queue_id"):
            await get_schema_tree_structure()

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_both_args(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test tree structure raises ToolError when both schema_id and queue_id provided."""
        register_get_tools(mock_mcp, mock_client)

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        with pytest.raises(ToolError, match="not both"):
            await get_schema_tree_structure(schema_id=50, queue_id=100)
