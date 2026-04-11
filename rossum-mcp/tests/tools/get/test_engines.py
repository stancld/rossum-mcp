"""Tests for rossum_mcp.tools.get.engines module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_engine_field
from rossum_mcp.tools.get import register_get_tools


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
class TestGetEngineFields:
    """Tests for get_engine_fields tool."""

    @pytest.mark.asyncio
    async def test_get_engine_fields_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful engine fields retrieval."""
        register_get_tools(mock_mcp, mock_client)

        mock_field1 = create_mock_engine_field(id=1, label="Field 1")
        mock_field2 = create_mock_engine_field(id=2, label="Field 2")

        async def async_iter():
            for item in [mock_field1, mock_field2]:
                yield item

        mock_client.retrieve_engine_fields = Mock(side_effect=lambda **kwargs: async_iter())

        get_engine_fields = mock_mcp._tools["get_engine_fields"]
        result = await get_engine_fields(engine_id=123)

        assert len(result) == 2
        mock_client.retrieve_engine_fields.assert_called_once_with(engine_id=123)

    @pytest.mark.asyncio
    async def test_get_engine_fields_all(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test retrieving all engine fields without filter."""
        register_get_tools(mock_mcp, mock_client)

        async def async_iter():
            return
            yield

        mock_client.retrieve_engine_fields = Mock(side_effect=lambda **kwargs: async_iter())

        get_engine_fields = mock_mcp._tools["get_engine_fields"]
        result = await get_engine_fields()

        assert len(result) == 0
        mock_client.retrieve_engine_fields.assert_called_once_with(engine_id=None)
