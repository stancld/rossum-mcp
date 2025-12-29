"""Tests for rossum_agent.tools.core module."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    import pytest

from rossum_agent.tools.core import (
    SubAgentProgress,
    SubAgentText,
    get_mcp_connection,
    get_mcp_event_loop,
    get_output_dir,
    report_progress,
    report_text,
    set_mcp_connection,
    set_output_dir,
    set_progress_callback,
    set_text_callback,
)
from rossum_agent.tools.spawn_mcp import (
    SpawnedConnection,
    get_spawned_connections,
    get_spawned_connections_lock,
)


class TestSubAgentProgress:
    """Tests for SubAgentProgress dataclass."""

    def test_default_field_values(self) -> None:
        progress = SubAgentProgress(
            tool_name="test_tool",
            iteration=1,
            max_iterations=5,
        )
        assert progress.tool_name == "test_tool"
        assert progress.iteration == 1
        assert progress.max_iterations == 5
        assert progress.current_tool is None
        assert progress.tool_calls == []
        assert progress.status == "running"

    def test_with_custom_values(self) -> None:
        progress = SubAgentProgress(
            tool_name="debug_hook",
            iteration=3,
            max_iterations=10,
            current_tool="list_annotations",
            tool_calls=["get_hook", "list_rules"],
            status="completed",
        )
        assert progress.tool_name == "debug_hook"
        assert progress.iteration == 3
        assert progress.max_iterations == 10
        assert progress.current_tool == "list_annotations"
        assert progress.tool_calls == ["get_hook", "list_rules"]
        assert progress.status == "completed"


class TestSubAgentText:
    """Tests for SubAgentText dataclass."""

    def test_default_field_values(self) -> None:
        text = SubAgentText(tool_name="test_tool", text="Some output")
        assert text.tool_name == "test_tool"
        assert text.text == "Some output"
        assert text.is_final is False

    def test_with_custom_values(self) -> None:
        text = SubAgentText(
            tool_name="debug_hook",
            text="Final analysis complete",
            is_final=True,
        )
        assert text.tool_name == "debug_hook"
        assert text.text == "Final analysis complete"
        assert text.is_final is True


class TestCallbacks:
    """Tests for callback functions."""

    def test_set_progress_callback_and_clear(self) -> None:
        callback = MagicMock()
        set_progress_callback(callback)

        progress = SubAgentProgress(tool_name="test", iteration=1, max_iterations=5)
        report_progress(progress)
        callback.assert_called_once_with(progress)

        set_progress_callback(None)
        callback.reset_mock()
        report_progress(progress)
        callback.assert_not_called()

    def test_set_text_callback_and_clear(self) -> None:
        callback = MagicMock()
        set_text_callback(callback)

        text = SubAgentText(tool_name="test", text="output")
        report_text(text)
        callback.assert_called_once_with(text)

        set_text_callback(None)
        callback.reset_mock()
        report_text(text)
        callback.assert_not_called()

    def test_report_progress_calls_callback(self) -> None:
        callback = MagicMock()
        set_progress_callback(callback)

        progress = SubAgentProgress(
            tool_name="debug_hook",
            iteration=2,
            max_iterations=10,
            current_tool="get_annotation",
            status="running",
        )
        report_progress(progress)

        callback.assert_called_once_with(progress)
        set_progress_callback(None)

    def test_report_progress_no_callback_no_error(self) -> None:
        set_progress_callback(None)
        progress = SubAgentProgress(tool_name="test", iteration=1, max_iterations=5)
        report_progress(progress)

    def test_report_text_calls_callback(self) -> None:
        callback = MagicMock()
        set_text_callback(callback)

        text = SubAgentText(tool_name="debug_hook", text="Analysis output", is_final=True)
        report_text(text)

        callback.assert_called_once_with(text)
        set_text_callback(None)

    def test_report_text_no_callback_no_error(self) -> None:
        set_text_callback(None)
        text = SubAgentText(tool_name="test", text="output")
        report_text(text)


class TestOutputDirectory:
    """Tests for output directory functions."""

    def test_set_and_get_output_dir(self, tmp_path: Path) -> None:
        custom_dir = tmp_path / "custom_outputs"
        custom_dir.mkdir()

        set_output_dir(custom_dir)
        assert get_output_dir() == custom_dir

        set_output_dir(None)

    def test_get_output_dir_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        set_output_dir(None)
        monkeypatch.chdir(tmp_path)

        result = get_output_dir()
        assert result == Path("./outputs")
        assert result.exists()

        set_output_dir(None)


class TestMCPConnection:
    """Tests for MCP connection functions."""

    def test_set_mcp_connection_sets_values(self) -> None:
        mock_connection = MagicMock()
        loop = asyncio.new_event_loop()

        try:
            set_mcp_connection(mock_connection, loop)
            assert get_mcp_connection() is mock_connection
            assert get_mcp_event_loop() is loop
        finally:
            loop.close()
            set_mcp_connection(None, None)  # type: ignore[arg-type]

    def test_get_mcp_connection(self) -> None:
        set_mcp_connection(None, None)  # type: ignore[arg-type]
        assert get_mcp_connection() is None

        mock_connection = MagicMock()
        loop = asyncio.new_event_loop()
        try:
            set_mcp_connection(mock_connection, loop)
            assert get_mcp_connection() is mock_connection
        finally:
            loop.close()
            set_mcp_connection(None, None)  # type: ignore[arg-type]

    def test_get_mcp_event_loop(self) -> None:
        set_mcp_connection(None, None)  # type: ignore[arg-type]
        assert get_mcp_event_loop() is None

        mock_connection = MagicMock()
        loop = asyncio.new_event_loop()
        try:
            set_mcp_connection(mock_connection, loop)
            assert get_mcp_event_loop() is loop
        finally:
            loop.close()
            set_mcp_connection(None, None)  # type: ignore[arg-type]

    def test_get_spawned_connections(self) -> None:
        spawned = get_spawned_connections()
        assert isinstance(spawned, dict)

    def test_get_spawned_connections_lock(self) -> None:
        lock = get_spawned_connections_lock()
        assert isinstance(lock, type(threading.Lock()))


class TestSpawnedConnection:
    """Tests for SpawnedConnection dataclass."""

    def test_spawned_connection_fields(self) -> None:
        mock_connection = MagicMock()
        mock_client = MagicMock()

        spawned = SpawnedConnection(
            connection=mock_connection,
            client=mock_client,
            api_base_url="https://api.example.com",
        )

        assert spawned.connection is mock_connection
        assert spawned.client is mock_client
        assert spawned.api_base_url == "https://api.example.com"
