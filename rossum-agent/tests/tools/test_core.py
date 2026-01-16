"""Tests for rossum_agent.tools.core module."""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from rossum_agent.tools.core import (
    SubAgentProgress,
    SubAgentText,
    SubAgentTokenUsage,
    get_mcp_connection,
    get_mcp_event_loop,
    get_output_dir,
    report_progress,
    report_text,
    report_token_usage,
    set_mcp_connection,
    set_output_dir,
    set_progress_callback,
    set_text_callback,
    set_token_callback,
)
from rossum_agent.tools.spawn_mcp import SpawnedConnection, get_spawned_connections, get_spawned_connections_lock

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture(autouse=True)
def _reset_core_state() -> Iterator[None]:
    """Reset core module state between tests to avoid leakage."""
    yield  # type: ignore[misc]
    set_output_dir(None)
    set_progress_callback(None)
    set_text_callback(None)
    set_token_callback(None)
    set_mcp_connection(None, None)  # type: ignore[arg-type]


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


class TestSubAgentTokenUsage:
    """Tests for SubAgentTokenUsage dataclass."""

    def test_default_field_values(self) -> None:
        usage = SubAgentTokenUsage(
            tool_name="test_tool",
            input_tokens=100,
            output_tokens=50,
        )
        assert usage.tool_name == "test_tool"
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.iteration is None

    def test_with_iteration(self) -> None:
        usage = SubAgentTokenUsage(
            tool_name="debug_hook",
            input_tokens=1000,
            output_tokens=500,
            iteration=3,
        )
        assert usage.iteration == 3


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

    def test_report_text_no_callback_no_error(self) -> None:
        set_text_callback(None)
        text = SubAgentText(tool_name="test", text="output")
        report_text(text)

    def test_set_token_callback_and_clear(self) -> None:
        callback = MagicMock()
        set_token_callback(callback)

        usage = SubAgentTokenUsage(tool_name="test", input_tokens=100, output_tokens=50)
        report_token_usage(usage)
        callback.assert_called_once_with(usage)

        set_token_callback(None)
        callback.reset_mock()
        report_token_usage(usage)
        callback.assert_not_called()

    def test_report_token_usage_calls_callback(self) -> None:
        callback = MagicMock()
        set_token_callback(callback)

        usage = SubAgentTokenUsage(
            tool_name="debug_hook",
            input_tokens=1000,
            output_tokens=500,
            iteration=2,
        )
        report_token_usage(usage)

        callback.assert_called_once_with(usage)

    def test_report_token_usage_no_callback_no_error(self) -> None:
        set_token_callback(None)
        usage = SubAgentTokenUsage(tool_name="test", input_tokens=100, output_tokens=50)
        report_token_usage(usage)


class TestOutputDirectory:
    """Tests for output directory functions."""

    def test_set_and_get_output_dir(self, tmp_path: Path) -> None:
        custom_dir = tmp_path / "custom_outputs"
        custom_dir.mkdir()

        set_output_dir(custom_dir)
        assert get_output_dir() == custom_dir

    def test_get_output_dir_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        set_output_dir(None)
        monkeypatch.chdir(tmp_path)

        result = get_output_dir()
        assert result.resolve() == (tmp_path / "outputs").resolve()
        assert result.exists()

    def test_get_output_dir_fallback_creates_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that get_output_dir creates the fallback directory if it doesn't exist."""
        set_output_dir(None)
        test_dir = tmp_path / "new_workdir"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        outputs_dir = test_dir / "outputs"
        assert not outputs_dir.exists()

        result = get_output_dir()
        assert result.resolve() == outputs_dir.resolve()
        assert outputs_dir.exists()


class TestContextVarIsolation:
    """Tests for context variable thread isolation."""

    def test_context_vars_isolated_between_threads(self, tmp_path: Path) -> None:
        """Test that context variables are isolated between threads."""
        results: dict[str, Path | None] = {}
        custom_dir = tmp_path / "thread_test"
        custom_dir.mkdir()

        def thread_func(thread_id: str) -> None:
            results[thread_id] = get_output_dir() if thread_id == "thread2" else None
            if thread_id == "thread1":
                set_output_dir(custom_dir)
                results[thread_id] = get_output_dir()

        set_output_dir(None)

        t1 = threading.Thread(target=thread_func, args=("thread1",))
        t2 = threading.Thread(target=thread_func, args=("thread2",))

        t1.start()
        t1.join()
        t2.start()
        t2.join()

        assert results["thread1"] == custom_dir
        assert results["thread2"] != custom_dir

    def test_callbacks_isolated_between_threads(self) -> None:
        """Test that callbacks set in one thread don't affect another."""
        callback1 = MagicMock()

        def thread1_func() -> None:
            set_progress_callback(callback1)
            progress = SubAgentProgress(tool_name="t1", iteration=1, max_iterations=5)
            report_progress(progress)

        def thread2_func() -> None:
            progress = SubAgentProgress(tool_name="t2", iteration=1, max_iterations=5)
            report_progress(progress)

        set_progress_callback(None)

        t1 = threading.Thread(target=thread1_func)
        t2 = threading.Thread(target=thread2_func)

        t1.start()
        t1.join()
        t2.start()
        t2.join()

        callback1.assert_called_once()
        assert callback1.call_args[0][0].tool_name == "t1"


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
