"""Tests for rossum_mcp.tools.update.engines module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_engine
from rossum_api.domain_logic.resources import Resource
from rossum_mcp.tools.update.engines import register_engine_tools


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
class TestUpdateEngine:
    """Tests for update_engine tool."""

    @pytest.mark.asyncio
    async def test_update_engine_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful engine update."""
        register_engine_tools(mock_mcp, mock_client)

        mock_engine = create_mock_engine(id=123, name="Updated Engine")
        mock_client._http_client.update.return_value = {"id": 123}
        mock_client._deserializer = Mock(return_value=mock_engine)

        update_engine = mock_mcp._tools["update_engine"]
        result = await update_engine(engine_id=123, engine_data={"name": "Updated Engine"})

        assert result.id == 123
        assert result.name == "Updated Engine"
        mock_client._http_client.update.assert_called_once_with(Resource.Engine, 123, {"name": "Updated Engine"})
