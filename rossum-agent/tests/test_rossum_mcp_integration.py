"""Tests for rossum_agent.mcp_tools module."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.change_tracking.models import EntityChange
from rossum_agent.rossum_mcp_integration.connection import MCPConnection, connect_mcp_server, create_mcp_transport
from rossum_agent.rossum_mcp_integration.tools import _pop_tracked_resources, mcp_tools_to_anthropic_format


class TestCreateMCPTransport:
    """Test create_mcp_transport function."""

    def test_creates_transport_with_required_params(self, monkeypatch):
        """Test creating transport with required parameters."""
        monkeypatch.delenv("ROSSUM_API_TOKEN", raising=False)
        monkeypatch.delenv("ROSSUM_API_BASE_URL", raising=False)

        transport = create_mcp_transport(
            rossum_api_token="test_token",
            rossum_api_base_url="https://api.rossum.ai",
        )

        assert transport.command == "rossum-mcp"
        assert transport.args == []
        assert transport.env["ROSSUM_API_TOKEN"] == "test_token"
        assert transport.env["ROSSUM_API_BASE_URL"] == "https://api.rossum.ai"
        assert transport.env["ROSSUM_MCP_MODE"] == "read-only"

    def test_creates_transport_with_read_write_mode(self, monkeypatch):
        """Test creating transport with read-write mode."""
        monkeypatch.delenv("ROSSUM_MCP_MODE", raising=False)

        transport = create_mcp_transport(
            rossum_api_token="test_token",
            rossum_api_base_url="https://api.rossum.ai",
            mcp_mode="read-write",
        )

        assert transport.env["ROSSUM_MCP_MODE"] == "read-write"

    def test_inherits_environment_variables(self):
        """Test that transport inherits current environment variables."""
        with patch.dict(os.environ, {"CUSTOM_VAR": "custom_value"}):
            transport = create_mcp_transport(
                rossum_api_token="test_token",
                rossum_api_base_url="https://api.rossum.ai",
            )

            assert transport.env["CUSTOM_VAR"] == "custom_value"


class TestMCPToolsToAnthropicFormat:
    """Test mcp_tools_to_anthropic_format function."""

    def test_converts_multiple_tools(self):
        """Test converting a list of tools."""
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"
        mock_tool1.description = "First tool"
        mock_tool1.inputSchema = {"type": "object", "properties": {}}

        mock_tool2 = MagicMock()
        mock_tool2.name = "tool2"
        mock_tool2.description = "Second tool"
        mock_tool2.inputSchema = {"type": "object", "properties": {"param": {"type": "string"}}}

        result = mcp_tools_to_anthropic_format([mock_tool1, mock_tool2])

        assert len(result) == 2
        assert result[0]["name"] == "tool1"
        assert result[1]["name"] == "tool2"

    def test_handles_empty_list(self):
        """Test converting an empty list of tools."""
        result = mcp_tools_to_anthropic_format([])

        assert result == []


class TestMCPConnection:
    """Test MCPConnection class."""

    @pytest.mark.asyncio
    async def test_get_tools_caches_result(self):
        """Test that get_tools caches the result after first call."""
        mock_client = AsyncMock()
        mock_tools = [MagicMock(name="tool1"), MagicMock(name="tool2")]
        mock_client.list_tools.return_value = mock_tools

        connection = MCPConnection(client=mock_client)

        result1 = await connection.get_tools()
        result2 = await connection.get_tools()

        assert result1 == mock_tools
        assert result2 == mock_tools
        mock_client.list_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_returns_data_property(self):
        """Test that call_tool returns the data property when available."""
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.structured_content = None
        mock_result.data = {"queues": [{"id": 1, "name": "Test Queue"}]}
        mock_result.content = []
        mock_client.call_tool.return_value = mock_result

        connection = MCPConnection(client=mock_client)

        result = await connection.call_tool("list_queues", {"workspace_url": "https://example.com"})

        assert result == {"queues": [{"id": 1, "name": "Test Queue"}]}
        mock_client.call_tool.assert_called_once_with("list_queues", {"workspace_url": "https://example.com"})

    @pytest.mark.asyncio
    async def test_call_tool_returns_text_content_when_no_data(self):
        """Test that call_tool returns text content when data is None."""
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.structured_content = None
        mock_result.data = None
        mock_text_block = MagicMock()
        mock_text_block.text = "Tool executed successfully"
        mock_result.content = [mock_text_block]
        mock_client.call_tool.return_value = mock_result

        connection = MCPConnection(client=mock_client)

        result = await connection.call_tool("simple_tool")

        assert result == "Tool executed successfully"

    @pytest.mark.asyncio
    async def test_call_tool_joins_multiple_text_blocks(self):
        """Test that call_tool joins multiple text content blocks."""
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.structured_content = None
        mock_result.data = None

        mock_text1 = MagicMock()
        mock_text1.text = "Line 1"
        mock_text2 = MagicMock()
        mock_text2.text = "Line 2"
        mock_result.content = [mock_text1, mock_text2]
        mock_client.call_tool.return_value = mock_result

        connection = MCPConnection(client=mock_client)

        result = await connection.call_tool("multi_output_tool")

        assert result == "Line 1\nLine 2"

    @pytest.mark.asyncio
    async def test_call_tool_handles_empty_arguments(self):
        """Test that call_tool handles missing arguments."""
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.data = "result"
        mock_client.call_tool.return_value = mock_result

        connection = MCPConnection(client=mock_client)

        await connection.call_tool("no_args_tool")

        mock_client.call_tool.assert_called_once_with("no_args_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_returns_none_for_empty_response(self):
        """Test that call_tool returns None when no data or content."""
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.structured_content = None
        mock_result.data = None
        mock_result.content = []
        mock_client.call_tool.return_value = mock_result

        connection = MCPConnection(client=mock_client)

        result = await connection.call_tool("void_tool")

        assert result is None

    @pytest.mark.asyncio
    async def test_call_tool_prefers_structured_content_over_data(self):
        """Test that call_tool prefers structured_content over data to avoid FastMCP parsing bugs."""
        mock_client = AsyncMock()
        mock_result = MagicMock()
        # structured_content is the raw dict, data is the parsed pydantic model (possibly broken)
        mock_result.structured_content = {"id": 1, "config": {"code": "print(1)"}}
        mock_result.data = {"id": 1, "config": {}}  # Simulates FastMCP bug where nested dicts are empty
        mock_result.content = []
        mock_client.call_tool.return_value = mock_result

        connection = MCPConnection(client=mock_client)

        result = await connection.call_tool("get_hook", {"hook_id": 1})

        # Should return structured_content, not data
        assert result == {"id": 1, "config": {"code": "print(1)"}}


class TestConnectMCPServer:
    """Test connect_mcp_server context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_yields_connection(self):
        """Test that connect_mcp_server yields an MCPConnection."""
        mock_client_instance = AsyncMock()
        mock_tools = [MagicMock(name="tool1")]
        mock_client_instance.list_tools.return_value = mock_tools

        with patch("rossum_agent.rossum_mcp_integration.connection.Client") as mock_client_class:
            mock_client_class.return_value = mock_client_instance
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)

            async with connect_mcp_server(
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ) as connection:
                assert isinstance(connection, MCPConnection)
                tools = await connection.get_tools()
                assert tools == mock_tools

    @pytest.mark.asyncio
    async def test_context_manager_configures_transport(self):
        """Test that connect_mcp_server configures the transport correctly."""
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("rossum_agent.rossum_mcp_integration.connection.Client") as mock_client_class,
            patch("rossum_agent.rossum_mcp_integration.connection.create_mcp_transport") as mock_create_transport,
        ):
            mock_transport = MagicMock()
            mock_create_transport.return_value = mock_transport
            mock_client_class.return_value = mock_client_instance

            async with connect_mcp_server(
                rossum_api_token="test_token",
                rossum_api_base_url="https://api.rossum.ai",
                mcp_mode="read-write",
            ):
                pass

            mock_create_transport.assert_called_once_with(
                rossum_api_token="test_token",
                rossum_api_base_url="https://api.rossum.ai",
                mcp_mode="read-write",
            )
            mock_client_class.assert_called_once_with(mock_transport)


# -- Change tracking tests --


def _make_mcp_result(data):
    """Create a mock MCP call_tool result returning structured_content."""
    result = MagicMock()
    result.structured_content = data
    result.data = None
    result.content = []
    return result


def _make_connection(write_tools=None):
    """Create an MCPConnection with a mocked client for testing."""
    mock_client = AsyncMock()
    return MCPConnection(client=mock_client, write_tools=write_tools or set())


class TestHandleWriteUpdate:
    @pytest.mark.asyncio
    async def test_update_fetches_before_and_after_snapshots(self):
        conn = _make_connection(write_tools={"update_queue"})
        before = {"id": 1, "name": "Before"}
        after = {"id": 1, "name": "After"}

        call_count = 0

        async def mock_call_tool(name, args):
            nonlocal call_count
            call_count += 1
            if name == "get":
                return _make_mcp_result(before if call_count == 1 else after)
            return _make_mcp_result({"ok": True})

        conn.client.call_tool = mock_call_tool

        result = await conn.call_tool("update_queue", {"queue_id": 1, "name": "After"})

        assert result == {"ok": True}
        assert len(conn.get_changes()) == 1
        change = conn.get_changes()[0]
        assert change.entity_type == "queue"
        assert change.entity_id == "1"
        assert change.operation == "update"
        assert change.before == before
        assert change.after == after

    @pytest.mark.asyncio
    async def test_update_unwraps_fastmcp_result_wrapper_for_unified_get(self):
        """Regression: FastMCP wraps structured_content in {"result": ...}.

        When fetch_snapshot calls get(entity=..., entity_id=...), the response
        is {"entity": ..., "id": ..., "data": {actual_entity}}. If FastMCP wraps
        this in {"result": ...}, _call_mcp must unwrap it so fetch_snapshot can
        extract the inner "data" dict. Without this fix, before/after snapshots
        for schemas would be missing the "content" field, breaking revert_commit.
        """
        conn = _make_connection(write_tools={"patch_schema"})
        schema_before = {"id": 1, "name": "Schema", "content": [{"id": "field_1"}]}
        schema_after = {"id": 1, "name": "Schema", "content": [{"id": "field_1"}, {"id": "field_2"}]}

        call_count = 0

        async def mock_call_tool(name, args):
            nonlocal call_count
            call_count += 1
            if name == "get":
                # Simulate FastMCP wrapping the unified get response
                inner = schema_before if call_count == 1 else schema_after
                wrapped = {"result": {"entity": "schema", "id": 1, "data": inner}}
                return _make_mcp_result(wrapped)
            return _make_mcp_result({"ok": True})

        conn.client.call_tool = mock_call_tool

        await conn.call_tool("patch_schema", {"schema_id": 1, "nodes": []})

        change = conn.get_changes()[0]
        assert change.entity_type == "schema"
        # Verify the before snapshot has content (the bug was that it didn't)
        assert change.before == schema_before
        assert isinstance(change.before["content"], list)
        assert change.after == schema_after


class TestHandleWriteCreate:
    @pytest.mark.asyncio
    async def test_create_extracts_id_from_result(self):
        conn = _make_connection(write_tools={"create_queue"})
        # FastMCP wraps structured_content in {"result": ...}; _call_mcp unwraps it
        created_wrapped = {"result": {"id": 99, "name": "New Queue"}}

        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result(created_wrapped))

        await conn.call_tool("create_queue", {"name": "New Queue"})

        change = conn.get_changes()[0]
        assert change.entity_type == "queue"
        assert change.entity_id == "99"
        assert change.operation == "create"
        assert change.before is None
        assert change.after == {"id": 99, "name": "New Queue"}


class TestHandleWriteDelete:
    @pytest.mark.asyncio
    async def test_delete_sets_after_to_none(self):
        conn = _make_connection(write_tools={"delete_hook"})
        before = {"id": 5, "name": "Hook"}
        conn._read_cache[("hook", "5")] = before

        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result({"deleted": True}))

        await conn.call_tool("delete_hook", {"hook_id": 5})

        change = conn.get_changes()[0]
        assert change.operation == "delete"
        assert change.before == before
        assert change.after is None

    @pytest.mark.asyncio
    async def test_unified_delete_routes_correctly(self):
        conn = _make_connection(write_tools={"delete"})
        before = {"id": 7, "name": "MyQueue"}
        conn._read_cache[("queue", "7")] = before

        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result({"message": "Queue scheduled for deletion"}))

        await conn.call_tool("delete", {"entity": "queue", "entity_id": 7})

        change = conn.get_changes()[0]
        assert change.entity_type == "queue"
        assert change.entity_id == "7"
        assert change.operation == "delete"
        assert change.before == before
        assert change.after is None

    @pytest.mark.asyncio
    async def test_unified_delete_entity_id_cast_to_str(self):
        conn = _make_connection(write_tools={"delete"})
        conn._read_cache[("hook", "99")] = {"id": 99, "name": "H"}

        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result({"message": "deleted"}))

        await conn.call_tool("delete", {"entity": "hook", "entity_id": 99})

        change = conn.get_changes()[0]
        assert change.entity_id == "99"


class TestHandleWriteAutoCommit:
    @pytest.mark.asyncio
    async def test_auto_commits_on_operation_type_change(self):
        conn = _make_connection(write_tools={"create_queue", "delete_queue"})
        committed = False
        conn._commit_store = object()  # type: ignore[assignment]

        def on_flush(user_request: str) -> None:
            nonlocal committed
            committed = True

        conn.flush_and_commit = on_flush  # type: ignore[method-assign]
        # Simulate a prior create change on queue:1
        conn._changes.append(
            EntityChange(
                entity_type="queue", entity_id="1", entity_name="Q", operation="create", before=None, after={}
            )
        )

        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result({"deleted": True}))

        await conn.call_tool("delete_queue", {"queue_id": 1})

        assert committed

    @pytest.mark.asyncio
    async def test_no_auto_commit_for_same_operation_type(self):
        conn = _make_connection(write_tools={"update_queue", "patch_queue"})
        committed = False
        conn._commit_store = object()  # type: ignore[assignment]

        def on_flush(user_request: str) -> None:
            nonlocal committed
            committed = True

        conn.flush_and_commit = on_flush  # type: ignore[method-assign]
        conn._changes.append(
            EntityChange(entity_type="queue", entity_id="1", entity_name="Q", operation="update", before={}, after={})
        )

        # patch_ also classifies as "update"
        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result({"ok": True}))

        # Need to also mock fetch_snapshot for the after-snapshot
        async def mock_call_tool(name, args):
            return _make_mcp_result({"id": 1, "name": "Updated"})

        conn.client.call_tool = mock_call_tool

        await conn.call_tool("patch_queue", {"queue_id": 1})

        assert not committed


class TestHandleWriteUnknownEntity:
    @pytest.mark.asyncio
    async def test_unknown_entity_logs_warning_and_returns_result(self):
        conn = _make_connection(write_tools={"do_something"})
        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result({"done": True}))

        result = await conn.call_tool("do_something", {"x": 1})

        assert result == {"done": True}
        assert conn.get_changes() == []


class TestCallToolWriteDispatch:
    @pytest.mark.asyncio
    async def test_routes_write_tool_to_handle_write(self):
        conn = _make_connection(write_tools={"update_schema"})
        before = {"id": 10, "name": "S"}

        async def mock_call_tool(name, args):
            return _make_mcp_result(before)

        conn.client.call_tool = mock_call_tool

        await conn.call_tool("update_schema", {"schema_id": 10})

        assert conn.has_changes()

    @pytest.mark.asyncio
    async def test_non_write_tool_not_tracked(self):
        conn = _make_connection(write_tools={"update_schema"})
        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result({"id": 1}))

        await conn.call_tool("get_schema", {"schema_id": 1})

        assert not conn.has_changes()


# -- Cache tests --


class TestCacheInMemory:
    def test_round_trip(self):
        conn = _make_connection()
        conn._cache_set("queue", "1", {"id": 1, "name": "Q"})
        assert conn._cache_get("queue", "1") == {"id": 1, "name": "Q"}

    def test_miss_returns_none(self):
        conn = _make_connection()
        assert conn._cache_get("queue", "999") is None


class TestCacheValkey:
    def test_valkey_set_and_get(self):
        conn = _make_connection()
        conn.chat_id = "chat-1"
        mock_valkey = MagicMock()
        conn.valkey_client = mock_valkey

        data = {"id": 1, "name": "Q"}
        conn._cache_set("queue", "1", data)

        expected_key = "read_cache:chat-1:queue:1"
        mock_valkey.setex.assert_called_once_with(expected_key, conn.cache_ttl_seconds, json.dumps(data, default=str))

        # Simulate valkey get
        mock_valkey.get.return_value = json.dumps(data).encode()
        result = conn._cache_get("queue", "1")
        assert result == data

    def test_valkey_miss(self):
        conn = _make_connection()
        conn.chat_id = "chat-1"
        mock_valkey = MagicMock()
        mock_valkey.get.return_value = None
        conn.valkey_client = mock_valkey

        assert conn._cache_get("queue", "999") is None


class TestTryCacheRead:
    @pytest.mark.asyncio
    async def test_caches_get_result(self):
        conn = _make_connection()
        conn._try_cache_read("get_queue", {"queue_id": "1"}, {"id": 1, "name": "Q"})
        assert conn._cache_get("queue", "1") == {"id": 1, "name": "Q"}

    @pytest.mark.asyncio
    async def test_skips_non_dict_result(self):
        conn = _make_connection()
        conn._try_cache_read("get_queue", {"queue_id": "1"}, "plain string")
        assert conn._cache_get("queue", "1") is None

    @pytest.mark.asyncio
    async def test_get_without_id_in_args_uses_result_id(self):
        conn = _make_connection()
        conn._try_cache_read("get_queue", {}, {"id": 42, "name": "Q"})
        assert conn._cache_get("queue", "42") == {"id": 42, "name": "Q"}

    def test_unified_get_caches_data_from_wrapper(self):
        conn = _make_connection()
        result = {"entity": "queue", "id": 1, "data": {"id": 1, "name": "Q"}}
        conn._try_cache_read("get", {"entity": "queue", "entity_id": 1}, result)
        assert conn._cache_get("queue", "1") == {"id": 1, "name": "Q"}

    def test_unified_get_caches_fallback_when_no_data_key(self):
        conn = _make_connection()
        result = {"id": 1, "name": "Q"}
        conn._try_cache_read("get", {"entity": "queue", "entity_id": 1}, result)
        assert conn._cache_get("queue", "1") == {"id": 1, "name": "Q"}


class TestFetchSnapshot:
    @pytest.mark.asyncio
    async def test_success(self):
        conn = _make_connection()
        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result({"id": 1, "name": "Q"}))

        result = await conn.fetch_snapshot("queue", "1")

        assert result == {"id": 1, "name": "Q"}

    @pytest.mark.asyncio
    async def test_failure_returns_none(self):
        conn = _make_connection()
        conn.client.call_tool = AsyncMock(side_effect=Exception("API error"))

        result = await conn.fetch_snapshot("queue", "1")

        assert result is None

    @pytest.mark.asyncio
    async def test_non_dict_result_returns_none(self):
        conn = _make_connection()
        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result(None))

        result = await conn.fetch_snapshot("queue", "1")

        assert result is None

    @pytest.mark.asyncio
    async def test_unwraps_unified_get_response(self):
        conn = _make_connection()
        unified = {"entity": "queue", "id": 1, "data": {"id": 1, "name": "Q", "schema": "https://..."}}
        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result(unified))

        result = await conn.fetch_snapshot("queue", "1")

        assert result == {"id": 1, "name": "Q", "schema": "https://..."}


class TestChangeTrackerState:
    def test_clear_changes(self):
        conn = _make_connection()
        conn._changes.append(
            EntityChange(entity_type="queue", entity_id="1", entity_name="Q", operation="update", before={}, after={})
        )
        assert conn.has_changes()
        conn.clear_changes()
        assert not conn.has_changes()
        assert conn.get_changes() == []


# -- Tracked resources tests --


class TestPopTrackedResources:
    def test_extracts_from_dict_result(self):
        result = {
            "id": 1,
            "name": "Q",
            "_tracked_resources": [{"entity_type": "schema", "entity_id": "10", "data": {"id": 10}}],
        }
        tracked = _pop_tracked_resources(result)

        assert len(tracked) == 1
        assert tracked[0]["entity_type"] == "schema"
        assert "_tracked_resources" not in result

    def test_returns_empty_for_non_dict(self):
        assert _pop_tracked_resources("plain string") == []
        assert _pop_tracked_resources(42) == []
        assert _pop_tracked_resources(None) == []

    def test_returns_empty_when_key_absent(self):
        result = {"id": 1, "name": "Q"}
        tracked = _pop_tracked_resources(result)

        assert tracked == []
        assert result == {"id": 1, "name": "Q"}


class TestHandleWriteTrackedResources:
    @pytest.mark.asyncio
    async def test_records_tracked_resources_as_changes(self):
        conn = _make_connection(write_tools={"create_queue_from_template"})
        # _tracked_resources lives inside the result dict, then FastMCP wraps in {"result": ...}
        created = {
            "result": {
                "id": 99,
                "name": "New Queue",
                "_tracked_resources": [
                    {"entity_type": "schema", "entity_id": "50", "data": {"id": 50, "name": "S"}},
                    {"entity_type": "engine", "entity_id": "60", "data": {"id": 60, "name": "E"}},
                ],
            }
        }
        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result(created))

        await conn.call_tool("create_queue_from_template", {"name": "Q"})

        changes = conn.get_changes()
        assert len(changes) == 3

        queue_change = changes[0]
        assert queue_change.entity_type == "queue"
        assert queue_change.entity_id == "99"
        assert queue_change.operation == "create"

        schema_change = changes[1]
        assert schema_change.entity_type == "schema"
        assert schema_change.entity_id == "50"
        assert schema_change.entity_name == "S"
        assert schema_change.operation == "create"
        assert schema_change.before is None
        assert schema_change.after == {"id": 50, "name": "S"}

        engine_change = changes[2]
        assert engine_change.entity_type == "engine"
        assert engine_change.entity_id == "60"
        assert engine_change.entity_name == "E"

    @pytest.mark.asyncio
    async def test_tracked_resources_are_cached(self):
        conn = _make_connection(write_tools={"create_queue_from_template"})
        created = {
            "result": {
                "id": 99,
                "name": "Q",
                "_tracked_resources": [
                    {"entity_type": "schema", "entity_id": "50", "data": {"id": 50, "name": "S"}},
                ],
            }
        }
        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result(created))

        await conn.call_tool("create_queue_from_template", {"name": "Q"})

        assert conn._cache_get("schema", "50") == {"id": 50, "name": "S"}

    @pytest.mark.asyncio
    async def test_tracked_resources_stripped_from_main_snapshot(self):
        conn = _make_connection(write_tools={"create_queue_from_template"})
        created = {
            "result": {
                "id": 99,
                "name": "Q",
                "_tracked_resources": [
                    {"entity_type": "schema", "entity_id": "50", "data": {"id": 50}},
                ],
            }
        }
        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result(created))

        await conn.call_tool("create_queue_from_template", {"name": "Q"})

        queue_change = conn.get_changes()[0]
        # The after snapshot should not contain _tracked_resources
        assert "_tracked_resources" not in (queue_change.after or {})

    @pytest.mark.asyncio
    async def test_no_tracked_resources_works_normally(self):
        conn = _make_connection(write_tools={"create_queue"})
        created = {"result": {"id": 99, "name": "Q"}}
        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result(created))

        await conn.call_tool("create_queue", {"name": "Q"})

        changes = conn.get_changes()
        assert len(changes) == 1
        assert changes[0].entity_type == "queue"

    @pytest.mark.asyncio
    async def test_setup_change_tracking_sets_snapshot_store(self):
        conn = _make_connection()
        commit_store = MagicMock()
        commit_store.client = MagicMock()
        snapshot_store = MagicMock()

        conn.setup_change_tracking(
            write_tools={"update_queue"},
            chat_id="chat-1",
            environment="https://api.elis.rossum.ai/v1",
            commit_store=commit_store,
            snapshot_store=snapshot_store,
        )

        assert conn._snapshot_store is snapshot_store
        assert conn._commit_store is commit_store
        assert conn.write_tools == {"update_queue"}
        assert conn.chat_id == "chat-1"
        assert conn._environment == "https://api.elis.rossum.ai/v1"

    def test_flush_skipped_when_snapshot_store_is_none(self):
        conn = _make_connection()
        conn._commit_store = MagicMock()
        conn._snapshot_store = None
        conn._environment = "https://api.elis.rossum.ai/v1"
        conn._changes.append(
            EntityChange(entity_type="queue", entity_id="1", entity_name="Q", operation="update", before={}, after={})
        )

        # Should not raise and should not call CommitService
        with patch("rossum_agent.rossum_mcp_integration.change_tracking.CommitService") as mock_cs:
            conn.flush_and_commit("test request")
            mock_cs.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_malformed_tracked_entries(self):
        conn = _make_connection(write_tools={"create_queue_from_template"})
        created = {
            "result": {
                "id": 99,
                "name": "Q",
                "_tracked_resources": [
                    {"entity_type": "", "entity_id": "50", "data": {"id": 50}},
                    {"entity_type": "schema", "entity_id": "", "data": {"id": 50}},
                    {"entity_type": "engine", "entity_id": "60", "data": "not a dict"},
                    {"entity_type": "schema", "entity_id": "70", "data": {"id": 70, "name": "Valid"}},
                ],
            }
        }
        conn.client.call_tool = AsyncMock(return_value=_make_mcp_result(created))

        await conn.call_tool("create_queue_from_template", {"name": "Q"})

        changes = conn.get_changes()
        # 1 queue + 1 valid tracked resource (the last one)
        assert len(changes) == 2
        assert changes[1].entity_type == "schema"
        assert changes[1].entity_id == "70"
