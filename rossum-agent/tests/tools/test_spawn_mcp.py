"""Tests for rossum_agent.tools.spawn_mcp module."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.tools.core import set_mcp_connection
from rossum_agent.tools.spawn_mcp import (
    SpawnedConnection,
    _close_spawned_connection_async,
    _spawn_connection_async,
    call_on_connection,
    cleanup_all_spawned_connections,
    clear_spawned_connections,
    close_connection,
    get_spawned_connections,
    get_spawned_connections_lock,
    spawn_mcp_connection,
)


class TestSpawnMcpConnection:
    """Tests for spawn_mcp_connection tool."""

    def test_spawn_without_event_loop(self) -> None:
        """Test that spawn fails gracefully without MCP event loop."""
        set_mcp_connection(None, None)

        result = spawn_mcp_connection(
            connection_id="test",
            api_token="token",
            api_base_url="https://api.test.com",
        )

        assert "Error: MCP event loop not set" in result

    def test_spawn_empty_connection_id(self) -> None:
        """Test that spawn fails with empty connection_id."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        try:
            result = spawn_mcp_connection(
                connection_id="",
                api_token="token",
                api_base_url="https://api.test.com",
            )
            assert "Error: connection_id must be non-empty" in result
        finally:
            loop.close()
            set_mcp_connection(None, None)

    def test_spawn_invalid_api_base_url(self) -> None:
        """Test that spawn fails with invalid API base URL."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        try:
            result = spawn_mcp_connection(
                connection_id="test",
                api_token="token",
                api_base_url="http://insecure.com",
            )
            assert "Error: api_base_url must start with https://" in result
        finally:
            loop.close()
            set_mcp_connection(None, None)

    def test_spawn_duplicate_connection_id(self) -> None:
        """Test that spawn fails with duplicate connection ID."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        spawned = get_spawned_connections()
        spawned["existing"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.side_effect = ValueError("Connection 'existing' already exists")
                mock_run.return_value = future

                result = spawn_mcp_connection(
                    connection_id="existing",
                    api_token="token",
                    api_base_url="https://api.test.com",
                )
                assert "Error:" in result
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)


class TestCallOnConnection:
    """Tests for call_on_connection tool."""

    def test_call_without_event_loop(self) -> None:
        """Test that call fails gracefully without MCP event loop."""
        set_mcp_connection(None, None)

        result = call_on_connection(
            connection_id="test",
            tool_name="some_tool",
            arguments="{}",
        )

        assert "Error: MCP event loop not set" in result

    def test_call_nonexistent_connection(self) -> None:
        """Test that call fails for nonexistent connection."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)
        clear_spawned_connections()

        try:
            result = call_on_connection(
                connection_id="nonexistent",
                tool_name="some_tool",
                arguments="{}",
            )
            assert "Error: Connection 'nonexistent' not found" in result
        finally:
            loop.close()
            set_mcp_connection(None, None)

    def test_call_invalid_json_arguments(self) -> None:
        """Test that call fails with invalid JSON arguments."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            result = call_on_connection(
                connection_id="test",
                tool_name="some_tool",
                arguments="not valid json",
            )
            assert "Error parsing arguments JSON" in result
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)

    def test_call_with_dict_arguments(self) -> None:
        """Test that call accepts dict arguments directly (not just JSON strings)."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        mock_connection = MagicMock()
        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=mock_connection,
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.return_value = {"result": "ok"}
                mock_run.return_value = future

                # Pass dict directly instead of JSON string
                result = call_on_connection(
                    connection_id="test",
                    tool_name="some_tool",
                    arguments={"param": "value"},
                )
                assert result.startswith("[some_tool]")
                assert '"result": "ok"' in result

                # Verify call_tool received the dict
                mock_connection.call_tool.assert_called_once_with("some_tool", {"param": "value"})
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)

    def test_call_success_with_dict_result(self) -> None:
        """Test successful call returning dict."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        mock_connection = MagicMock()
        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=mock_connection,
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.return_value = {"key": "value"}
                mock_run.return_value = future

                result = call_on_connection(
                    connection_id="test",
                    tool_name="some_tool",
                    arguments='{"param": "value"}',
                )
                assert result.startswith("[some_tool]")
                assert '"key": "value"' in result
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)

    def test_call_success_with_none_result(self) -> None:
        """Test successful call returning None."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        mock_connection = MagicMock()
        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=mock_connection,
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.return_value = None
                mock_run.return_value = future

                result = call_on_connection(
                    connection_id="test",
                    tool_name="some_tool",
                    arguments="",
                )
                assert result == "[some_tool] Tool executed successfully"
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)


class TestCloseConnection:
    """Tests for close_connection tool."""

    def test_close_without_event_loop(self) -> None:
        """Test that close fails gracefully without MCP event loop."""
        set_mcp_connection(None, None)

        result = close_connection(connection_id="test")
        assert "Error: MCP event loop not set" in result

    def test_close_nonexistent_connection(self) -> None:
        """Test that close handles nonexistent connection."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)
        clear_spawned_connections()

        try:
            result = close_connection(connection_id="nonexistent")
            assert "not found" in result
        finally:
            loop.close()
            set_mcp_connection(None, None)

    def test_close_success(self) -> None:
        """Test successful connection close."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.return_value = None
                mock_run.return_value = future

                result = close_connection(connection_id="test")
                assert "Successfully closed" in result
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)


class TestClearSpawnedConnections:
    """Tests for clear_spawned_connections function."""

    def test_clear_removes_all_connections(self) -> None:
        """Test that clear removes all spawned connections."""
        spawned = get_spawned_connections()
        spawned["conn1"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api1.test.com",
        )
        spawned["conn2"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api2.test.com",
        )

        clear_spawned_connections()

        assert len(spawned) == 0


class TestCleanupAllSpawnedConnections:
    """Tests for cleanup_all_spawned_connections function."""

    def test_cleanup_without_event_loop(self) -> None:
        """Test that cleanup does nothing without event loop."""
        set_mcp_connection(None, None)
        cleanup_all_spawned_connections()

    def test_cleanup_with_connections(self) -> None:
        """Test cleanup closes all connections."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        spawned = get_spawned_connections()
        spawned["test1"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.return_value = None
                mock_run.return_value = future

                cleanup_all_spawned_connections()
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)


class TestGetSpawnedConnectionsLock:
    """Tests for get_spawned_connections_lock function."""

    def test_returns_lock(self) -> None:
        """Test that function returns a threading lock."""
        import threading

        lock = get_spawned_connections_lock()
        assert isinstance(lock, type(threading.Lock()))


class TestSpawnConnectionTimeout:
    """Tests for timeout scenarios."""

    def test_spawn_timeout(self) -> None:
        """Test timeout during spawn."""
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.side_effect = FuturesTimeoutError()
                mock_run.return_value = future

                result = spawn_mcp_connection(
                    connection_id="test",
                    api_token="token",
                    api_base_url="https://api.test.com",
                )
                assert "Timed out" in result
        finally:
            loop.close()
            set_mcp_connection(None, None)

    def test_spawn_runtime_error(self) -> None:
        """Test RuntimeError during spawn."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                mock_run.side_effect = RuntimeError("Event loop closed")

                result = spawn_mcp_connection(
                    connection_id="test",
                    api_token="token",
                    api_base_url="https://api.test.com",
                )
                assert "Failed to schedule MCP call" in result
        finally:
            loop.close()
            set_mcp_connection(None, None)

    def test_spawn_generic_exception(self) -> None:
        """Test generic exception during spawn."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.side_effect = Exception("Network error")
                mock_run.return_value = future

                result = spawn_mcp_connection(
                    connection_id="test",
                    api_token="token",
                    api_base_url="https://api.test.com",
                )
                assert "Error spawning connection" in result
        finally:
            loop.close()
            set_mcp_connection(None, None)


class TestCallOnConnectionEdgeCases:
    """Tests for edge cases in call_on_connection."""

    def test_call_timeout(self) -> None:
        """Test timeout during call."""
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.side_effect = FuturesTimeoutError()
                mock_run.return_value = future

                result = call_on_connection(
                    connection_id="test",
                    tool_name="some_tool",
                    arguments="{}",
                )
                assert "Timed out" in result
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)

    def test_call_exception(self) -> None:
        """Test exception during call."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.side_effect = Exception("API error")
                mock_run.return_value = future

                result = call_on_connection(
                    connection_id="test",
                    tool_name="some_tool",
                    arguments="{}",
                )
                assert "Error calling some_tool" in result
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)

    def test_call_with_list_result(self) -> None:
        """Test successful call returning list."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.return_value = [{"id": 1}, {"id": 2}]
                mock_run.return_value = future

                result = call_on_connection(
                    connection_id="test",
                    tool_name="some_tool",
                    arguments="{}",
                )
                assert '"id": 1' in result
                assert '"id": 2' in result
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)

    def test_call_with_string_result(self) -> None:
        """Test successful call returning string."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.return_value = "String result"
                mock_run.return_value = future

                result = call_on_connection(
                    connection_id="test",
                    tool_name="some_tool",
                    arguments="{}",
                )
                assert result == "[some_tool] String result"
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)


class TestCloseConnectionEdgeCases:
    """Tests for edge cases in close_connection."""

    def test_close_timeout(self) -> None:
        """Test timeout during close."""
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.side_effect = FuturesTimeoutError()
                mock_run.return_value = future

                result = close_connection(connection_id="test")
                assert "Timed out" in result
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)

    def test_close_exception(self) -> None:
        """Test exception during close."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.side_effect = Exception("Close error")
                mock_run.return_value = future

                result = close_connection(connection_id="test")
                assert "Error closing connection" in result
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)


class TestAsyncSpawnConnection:
    """Tests for async _spawn_connection_async function."""

    @pytest.mark.asyncio
    async def test_spawn_connection_duplicate_id_raises(self) -> None:
        """Test that duplicate connection ID raises ValueError."""
        spawned = get_spawned_connections()
        spawned["existing"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with pytest.raises(ValueError, match="already exists"):
                await _spawn_connection_async(
                    connection_id="existing",
                    api_token="token",
                    api_base_url="https://api.test.com",
                )
        finally:
            spawned.clear()

    @pytest.mark.asyncio
    async def test_spawn_connection_success(self) -> None:
        """Test successful connection spawn."""
        clear_spawned_connections()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_connection = MagicMock()

        with patch("rossum_agent.tools.spawn_mcp.create_mcp_transport"):
            with patch("rossum_agent.tools.spawn_mcp.Client", return_value=mock_client):
                with patch("rossum_agent.tools.spawn_mcp.MCPConnection", return_value=mock_connection):
                    result = await _spawn_connection_async(
                        connection_id="test", api_token="token", api_base_url="https://api.test.com"
                    )

                    assert result.connection is mock_connection
                    assert result.api_base_url == "https://api.test.com"
                    assert "test" in get_spawned_connections()

        get_spawned_connections().clear()


class TestAsyncCloseConnection:
    """Tests for async _close_spawned_connection_async function."""

    @pytest.mark.asyncio
    async def test_close_existing_connection(self) -> None:
        """Test closing an existing connection."""
        mock_client = AsyncMock()
        mock_client.__aexit__ = AsyncMock(return_value=None)

        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=MagicMock(),
            client=mock_client,
            api_base_url="https://api.test.com",
        )

        await _close_spawned_connection_async("test")

        assert "test" not in spawned
        mock_client.__aexit__.assert_called_once_with(None, None, None)

    @pytest.mark.asyncio
    async def test_close_nonexistent_connection(self) -> None:
        """Test closing a nonexistent connection does not raise."""
        clear_spawned_connections()
        await _close_spawned_connection_async("nonexistent")


class TestCleanupEdgeCases:
    """Tests for edge cases in cleanup_all_spawned_connections."""

    def test_cleanup_timeout(self) -> None:
        """Test timeout during cleanup."""
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.side_effect = FuturesTimeoutError()
                mock_run.return_value = future

                cleanup_all_spawned_connections()
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)

    def test_cleanup_exception(self) -> None:
        """Test exception during cleanup."""
        loop = asyncio.new_event_loop()
        mock_conn = MagicMock()
        set_mcp_connection(mock_conn, loop)

        spawned = get_spawned_connections()
        spawned["test"] = SpawnedConnection(
            connection=MagicMock(),
            client=MagicMock(),
            api_base_url="https://api.test.com",
        )

        try:
            with patch("rossum_agent.tools.spawn_mcp.asyncio.run_coroutine_threadsafe") as mock_run:
                future = MagicMock()
                future.result.side_effect = Exception("Cleanup error")
                mock_run.return_value = future

                cleanup_all_spawned_connections()
        finally:
            spawned.clear()
            loop.close()
            set_mcp_connection(None, None)
