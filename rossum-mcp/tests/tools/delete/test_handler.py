"""Tests for rossum_mcp.tools.delete.handler — unified delete tool."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from fastmcp.exceptions import ToolError
from rossum_api import APIClientError
from rossum_mcp.tools.delete.handler import register_delete_tools
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
    @pytest.mark.asyncio
    async def test_delete_queue(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.delete_queue.return_value = None
        register_delete_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["delete"](entity="queue", entity_id=100)
        assert "scheduled for deletion" in result["message"]
        assert "100" in result["message"]
        mock_client.delete_queue.assert_called_once_with(100)

    @pytest.mark.asyncio
    async def test_delete_schema(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.delete_schema.return_value = None
        register_delete_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["delete"](entity="schema", entity_id=50)
        assert "deleted successfully" in result["message"]
        assert "50" in result["message"]
        mock_client.delete_schema.assert_called_once_with(50)

    @pytest.mark.asyncio
    async def test_delete_hook(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.delete_hook.return_value = None
        register_delete_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["delete"](entity="hook", entity_id=123)
        assert "deleted successfully" in result["message"]
        assert "123" in result["message"]
        mock_client.delete_hook.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_delete_rule(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.delete_rule.return_value = None
        register_delete_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["delete"](entity="rule", entity_id=123)
        assert "deleted successfully" in result["message"]
        assert "123" in result["message"]
        mock_client.delete_rule.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_delete_workspace(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.delete_workspace.return_value = None
        register_delete_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["delete"](entity="workspace", entity_id=100)
        assert "deleted successfully" in result["message"]
        assert "100" in result["message"]
        mock_client.delete_workspace.assert_called_once_with(100)

    @pytest.mark.asyncio
    async def test_delete_annotation(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.delete_annotation.return_value = None
        register_delete_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["delete"](entity="annotation", entity_id=12345)
        assert "deleted" in result["message"]
        assert "12345" in result["message"]
        mock_client.delete_annotation.assert_called_once_with(12345)


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
        expected = {"queue", "schema", "hook", "rule", "workspace", "annotation", "inbox", "connector"}
        assert set(registry.keys()) == expected

    def test_all_entities_have_delete_fn(self, mock_client: AsyncMock, setup_env: None) -> None:
        registry = build_delete_registry(mock_client)
        for entity_name, delete_fn in registry.items():
            assert delete_fn is not None, f"Entity '{entity_name}' has no delete_fn"
