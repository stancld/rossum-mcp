"""Tests for rossum_mcp.tools.update.annotations module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_mcp.tools.update.annotations import register_annotation_tools


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
class TestStartAnnotation:
    """Tests for start_annotation tool."""

    @pytest.mark.asyncio
    async def test_start_annotation_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful annotation start."""
        register_annotation_tools(mock_mcp, mock_client)

        start_annotation = mock_mcp._tools["start_annotation"]
        result = await start_annotation(annotation_id=12345)

        assert result["annotation_id"] == 12345
        assert "started successfully" in result["message"]
        mock_client.start_annotation.assert_called_once_with(12345)


@pytest.mark.unit
class TestBulkUpdateAnnotationFields:
    """Tests for bulk_update_annotation_fields tool."""

    @pytest.mark.asyncio
    async def test_bulk_update_annotation_fields_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful bulk update of annotation fields."""
        register_annotation_tools(mock_mcp, mock_client)

        operations = [
            {"op": "replace", "id": 1, "value": {"content": {"value": "new value"}}},
            {"op": "replace", "id": 2, "value": {"content": {"value": "another value"}}},
        ]

        bulk_update = mock_mcp._tools["bulk_update_annotation_fields"]
        result = await bulk_update(annotation_id=12345, operations=operations)

        assert result["annotation_id"] == 12345
        assert result["operations_count"] == 2
        assert "updated with 2 operations" in result["message"]
        mock_client.bulk_update_annotation_data.assert_called_once_with(12345, operations)


@pytest.mark.unit
class TestConfirmAnnotation:
    """Tests for confirm_annotation tool."""

    @pytest.mark.asyncio
    async def test_confirm_annotation_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful annotation confirmation."""
        register_annotation_tools(mock_mcp, mock_client)

        confirm_annotation = mock_mcp._tools["confirm_annotation"]
        result = await confirm_annotation(annotation_id=12345)

        assert result["annotation_id"] == 12345
        assert "confirmed successfully" in result["message"]
        mock_client.confirm_annotation.assert_called_once_with(12345)
