"""Tests for rossum_mcp.tools.delete — unified delete tool."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from fastmcp.exceptions import ToolError
from rossum_api import APIClientError
from rossum_mcp.tools.delete import register_delete_tools
from rossum_mcp.tools.delete.registry import build_delete_registry

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    return client


@pytest.fixture
def mock_mcp() -> Mock:
    """Create a mock FastMCP that captures registered tools by name."""
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


@pytest.fixture
def setup_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
    monkeypatch.setenv("ROSSUM_API_TOKEN", "test-token-123")
    monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")


@pytest.mark.unit
class TestToolRegistration:
    def test_registers_delete(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        register_delete_tools(mock_mcp, mock_client)
        assert "delete" in mock_mcp._tools

    def test_registers_exactly_one_tool(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        register_delete_tools(mock_mcp, mock_client)
        assert len(mock_mcp._tools) == 1


@pytest.mark.unit
class TestDeleteRouting:
    @pytest.mark.parametrize(
        ("entity", "entity_id", "message_fragment"),
        [
            ("queue", 100, "scheduled for deletion"),
            ("schema", 50, "deleted successfully"),
            ("hook", 123, "deleted successfully"),
            ("rule", 123, "deleted successfully"),
            ("workspace", 100, "deleted successfully"),
            ("annotation", 12345, "deleted"),
        ],
    )
    @pytest.mark.asyncio
    async def test_delete_entity(
        self,
        mock_mcp: Mock,
        mock_client: AsyncMock,
        setup_env: None,
        entity: str,
        entity_id: int,
        message_fragment: str,
    ) -> None:
        delete_method = getattr(mock_client, f"delete_{entity}")
        delete_method.return_value = None
        register_delete_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["delete"](entity=entity, entity_id=entity_id)
        assert message_fragment in result["message"]
        assert str(entity_id) in result["message"]
        delete_method.assert_called_once_with(entity_id)


@pytest.mark.unit
class TestCustomMessages:
    @pytest.mark.asyncio
    async def test_queue_has_scheduled_message(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.delete_queue.return_value = None
        register_delete_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["delete"](entity="queue", entity_id=1)
        assert "scheduled for deletion" in result["message"]

    @pytest.mark.asyncio
    async def test_annotation_has_soft_delete_message(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        mock_client.delete_annotation.return_value = None
        register_delete_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["delete"](entity="annotation", entity_id=1)
        assert "moved to 'deleted' status" in result["message"]


@pytest.mark.unit
class TestDeleteErrors:
    @pytest.mark.asyncio
    async def test_unknown_entity_returns_error(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        register_delete_tools(mock_mcp, mock_client)
        with pytest.raises(ToolError, match="Unknown entity"):
            await mock_mcp._tools["delete"](entity="nonexistent", entity_id=1)

    @pytest.mark.asyncio
    async def test_not_found_propagates_exception(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        mock_client.delete_queue.side_effect = APIClientError(
            method="DELETE",
            url="https://api.test.rossum.ai/v1/queues/99999",
            status_code=404,
            error=Exception("Not Found"),
        )
        register_delete_tools(mock_mcp, mock_client)

        with pytest.raises(APIClientError) as exc_info:
            await mock_mcp._tools["delete"](entity="queue", entity_id=99999)
        assert exc_info.value.status_code == 404


@pytest.mark.unit
class TestDeleteRegistry:
    def test_all_entities_in_registry(self, mock_client: AsyncMock, setup_env: None) -> None:
        registry = build_delete_registry(mock_client)
        expected = {"queue", "schema", "hook", "rule", "workspace", "annotation"}
        assert set(registry.keys()) == expected

    def test_all_entities_have_delete_fn(self, mock_client: AsyncMock, setup_env: None) -> None:
        registry = build_delete_registry(mock_client)
        for entity_name, delete_fn in registry.items():
            assert delete_fn is not None, f"Entity '{entity_name}' has no delete_fn"
