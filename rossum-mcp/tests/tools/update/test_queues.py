"""Tests for rossum_mcp.tools.update.queues module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from fastmcp.exceptions import ToolError
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.queue import Queue
from rossum_mcp.tools.update.queues import register_queue_tools


def create_mock_queue(**kwargs) -> Queue:
    """Create a mock Queue dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/queues/1",
        "name": "Test Queue",
        "workspace": "https://api.test.rossum.ai/v1/workspaces/1",
        "connector": None,
        "schema": "https://api.test.rossum.ai/v1/schemas/1",
        "inbox": "https://api.test.rossum.ai/v1/inboxes/1",
        "hooks": [],
        "users": [],
        "use_confirmed_state": True,
        "default_score_threshold": 0.8,
        "locale": "en_GB",
        "training_enabled": True,
        "automation_enabled": True,
        "automation_level": "never",
        "generic_engine": None,
        "dedicated_engine": None,
        "engine": "https://api.test.rossum.ai/v1/engines/1",
        "counts": {},
        "metadata": {},
        "settings": {},
        "status": "active",
        "document_lifetime": None,
        "delete_after": None,
    }
    defaults.update(kwargs)
    return Queue(**defaults)


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
class TestUpdateQueue:
    """Tests for update_queue tool."""

    @pytest.mark.asyncio
    async def test_update_queue_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful queue update."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=100, name="Updated Queue")
        mock_client._http_client.update.return_value = {"id": 100, "name": "Updated Queue"}
        mock_client._deserializer = Mock(return_value=mock_queue)

        update_queue = mock_mcp._tools["update_queue"]
        result = await update_queue(queue_id=100, queue_data={"name": "Updated Queue"})

        assert result.id == 100
        assert result.name == "Updated Queue"
        mock_client._http_client.update.assert_called_once_with(Resource.Queue, 100, {"name": "Updated Queue"})

    @pytest.mark.asyncio
    async def test_update_queue_rejects_invalid_meta_name(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_queue_tools(mock_mcp, mock_client)

        update_queue = mock_mcp._tools["update_queue"]
        with pytest.raises(ToolError, match="Invalid meta_name") as exc_info:
            await update_queue(
                queue_id=100,
                queue_data={
                    "settings": {
                        "annotation_list_table": {
                            "columns": [
                                {"column_type": "meta", "meta_name": "created_by", "visible": True},
                            ]
                        }
                    }
                },
            )

        assert "created_by" in str(exc_info.value)
        mock_client._http_client.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_queue_allows_valid_meta_names(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=100, name="Test Queue")
        mock_client._http_client.update.return_value = {"id": 100}
        mock_client._deserializer = Mock(return_value=mock_queue)

        update_queue = mock_mcp._tools["update_queue"]
        result = await update_queue(
            queue_id=100,
            queue_data={
                "settings": {
                    "annotation_list_table": {
                        "columns": [
                            {"column_type": "meta", "meta_name": "created_at", "visible": True},
                            {"column_type": "meta", "meta_name": "modifier", "visible": True},
                        ]
                    }
                }
            },
        )

        assert result.id == 100
        mock_client._http_client.update.assert_called_once()
