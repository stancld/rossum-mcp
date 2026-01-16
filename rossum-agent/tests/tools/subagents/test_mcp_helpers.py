"""Tests for rossum_agent.tools.subagents.mcp_helpers module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.tools.subagents.mcp_helpers import call_mcp_tool


class TestCallMcpTool:
    """Test call_mcp_tool function."""

    def test_raises_runtime_error_when_mcp_connection_not_set(self):
        """Test that RuntimeError is raised when MCP connection is not set."""
        with (
            patch("rossum_agent.tools.subagents.mcp_helpers.get_mcp_connection", return_value=None),
            patch("rossum_agent.tools.subagents.mcp_helpers.get_mcp_event_loop", return_value=None),
            pytest.raises(RuntimeError, match="MCP connection not set"),
        ):
            call_mcp_tool("get_schema", {"schema_id": "123"})

    def test_raises_runtime_error_when_only_connection_set(self):
        """Test that RuntimeError is raised when only connection is set but not loop."""
        mock_connection = MagicMock()
        with (
            patch("rossum_agent.tools.subagents.mcp_helpers.get_mcp_connection", return_value=mock_connection),
            patch("rossum_agent.tools.subagents.mcp_helpers.get_mcp_event_loop", return_value=None),
            pytest.raises(RuntimeError, match="MCP connection not set"),
        ):
            call_mcp_tool("get_schema", {"schema_id": "123"})

    def test_calls_mcp_tool_and_returns_result(self):
        """Test that MCP tool is called and result is returned."""
        mock_connection = MagicMock()
        mock_loop = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = {"id": "123", "content": []}

        with (
            patch("rossum_agent.tools.subagents.mcp_helpers.get_mcp_connection", return_value=mock_connection),
            patch("rossum_agent.tools.subagents.mcp_helpers.get_mcp_event_loop", return_value=mock_loop),
            patch(
                "rossum_agent.tools.subagents.mcp_helpers.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ) as mock_run,
        ):
            result = call_mcp_tool("get_schema", {"schema_id": 123})

            assert result == {"id": "123", "content": []}
            mock_run.assert_called_once()
            mock_future.result.assert_called_once_with(timeout=60)

    def test_custom_timeout(self):
        """Test that custom timeout is passed to future.result."""
        mock_connection = MagicMock()
        mock_loop = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = {}

        with (
            patch("rossum_agent.tools.subagents.mcp_helpers.get_mcp_connection", return_value=mock_connection),
            patch("rossum_agent.tools.subagents.mcp_helpers.get_mcp_event_loop", return_value=mock_loop),
            patch(
                "rossum_agent.tools.subagents.mcp_helpers.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            call_mcp_tool("get_schema", {"schema_id": 123}, timeout=120)

            mock_future.result.assert_called_once_with(timeout=120)

    def test_logs_timing_on_completion(self):
        """Test that timing is logged when MCP call completes."""
        mock_connection = MagicMock()
        mock_loop = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = {"id": "123"}

        with (
            patch("rossum_agent.tools.subagents.mcp_helpers.get_mcp_connection", return_value=mock_connection),
            patch("rossum_agent.tools.subagents.mcp_helpers.get_mcp_event_loop", return_value=mock_loop),
            patch(
                "rossum_agent.tools.subagents.mcp_helpers.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
            patch("rossum_agent.tools.subagents.mcp_helpers.logger") as mock_logger,
        ):
            call_mcp_tool("get_schema", {"schema_id": "123"})

            mock_logger.info.assert_called_once()
            log_msg = mock_logger.info.call_args[0][0]
            assert "MCP call 'get_schema'" in log_msg
            assert "completed in" in log_msg
            assert "ms" in log_msg
