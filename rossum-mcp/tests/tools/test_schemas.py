"""Tests for rossum_mcp.tools.schemas module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.schema import Schema

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def create_mock_schema(**kwargs) -> Schema:
    """Create a mock Schema dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/schemas/1",
        "name": "Test Schema",
        "queues": [],
        "content": [{"id": "section1", "label": "Section 1", "children": []}],
        "metadata": {},
        "modified_by": None,
        "modified_at": "2025-01-01T00:00:00Z",
    }
    defaults.update(kwargs)
    return Schema(**defaults)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
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
    async def test_get_schema_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful schema retrieval."""
        from rossum_mcp.tools.schemas import register_schema_tools

        register_schema_tools(mock_mcp, mock_client)

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

        get_schema = mock_mcp._tools["get_schema"]
        result = await get_schema(schema_id=50)

        assert result["id"] == 50
        assert result["name"] == "Invoice Schema"
        assert len(result["content"]) == 1
        mock_client.retrieve_schema.assert_called_once_with(50)


@pytest.mark.unit
class TestUpdateSchema:
    """Tests for update_schema tool."""

    @pytest.mark.asyncio
    async def test_update_schema_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful schema update."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.schemas import register_schema_tools

        register_schema_tools(mock_mcp, mock_client)

        updated_schema = create_mock_schema(id=50, name="Updated Schema")
        mock_client._http_client.update.return_value = {"id": 50}
        mock_client.retrieve_schema.return_value = updated_schema

        update_schema = mock_mcp._tools["update_schema"]
        result = await update_schema(schema_id=50, schema_data={"name": "Updated Schema"})

        assert result["id"] == 50
        assert result["name"] == "Updated Schema"

    @pytest.mark.asyncio
    async def test_update_schema_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test update_schema is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.schemas import register_schema_tools

        register_schema_tools(mock_mcp, mock_client)

        update_schema = mock_mcp._tools["update_schema"]
        result = await update_schema(schema_id=50, schema_data={"name": "Updated"})

        assert result["error"] == "update_schema is not available in read-only mode"
        mock_client._http_client.update.assert_not_called()


@pytest.mark.unit
class TestCreateSchema:
    """Tests for create_schema tool."""

    @pytest.mark.asyncio
    async def test_create_schema_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful schema creation."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.schemas import register_schema_tools

        register_schema_tools(mock_mcp, mock_client)

        content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [{"id": "invoice_number", "label": "Invoice Number", "type": "string"}],
            }
        ]

        new_schema = create_mock_schema(id=100, name="New Schema", content=content)
        mock_client.create_new_schema.return_value = new_schema

        create_schema = mock_mcp._tools["create_schema"]
        result = await create_schema(name="New Schema", content=content)

        assert result["id"] == 100
        assert result["name"] == "New Schema"
        mock_client.create_new_schema.assert_called_once_with({"name": "New Schema", "content": content})

    @pytest.mark.asyncio
    async def test_create_schema_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_schema is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.schemas import register_schema_tools

        register_schema_tools(mock_mcp, mock_client)

        create_schema = mock_mcp._tools["create_schema"]
        result = await create_schema(name="New Schema", content=[])

        assert result["error"] == "create_schema is not available in read-only mode"
        mock_client.create_new_schema.assert_not_called()
