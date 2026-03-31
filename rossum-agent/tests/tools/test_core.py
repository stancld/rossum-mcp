"""Tests for rossum_agent.tools.core module."""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from rossum_agent.tools.core import (
    AgentContext,
    SubAgentProgress,
    SubAgentText,
    SubAgentTokenUsage,
    get_context,
    reset_context,
    set_context,
)
from rossum_agent.tools.task_tracker import TaskTracker

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture(autouse=True)
def _reset_core_state() -> Iterator[None]:
    """Reset core module state between tests to avoid leakage."""
    token = set_context(AgentContext())
    yield  # type: ignore[misc]
    reset_context(token)


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
            tool_name="search_knowledge_base",
            iteration=3,
            max_iterations=10,
            current_tool="list_annotations",
            tool_calls=["get_hook", "list_rules"],
            status="completed",
        )
        assert progress.tool_name == "search_knowledge_base"
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
            tool_name="search_knowledge_base",
            text="Final analysis complete",
            is_final=True,
        )
        assert text.tool_name == "search_knowledge_base"
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
            tool_name="search_knowledge_base",
            input_tokens=1000,
            output_tokens=500,
            iteration=3,
        )
        assert usage.iteration == 3


class TestAgentContext:
    """Tests for AgentContext dataclass and its methods."""

    def test_default_values(self) -> None:
        ctx = AgentContext()
        assert ctx.mcp_connection is None
        assert ctx.mcp_event_loop is None
        assert ctx.mcp_mode == "read-only"
        assert ctx.rossum_credentials is None
        assert ctx.rossum_environment is None
        assert ctx.output_dir is None
        assert ctx.commit_store is None
        assert ctx.snapshot_store is None
        assert ctx.task_tracker is None
        assert ctx.progress_callback is None
        assert ctx.text_callback is None
        assert ctx.token_callback is None
        assert ctx.task_snapshot_callback is None

    def test_is_read_only_default(self) -> None:
        ctx = AgentContext()
        assert ctx.is_read_only is True

    def test_is_read_only_read_write(self) -> None:
        ctx = AgentContext(mcp_mode="read-write")
        assert ctx.is_read_only is False

    def test_get_output_dir_with_value(self, tmp_path: Path) -> None:
        ctx = AgentContext(output_dir=tmp_path)
        assert ctx.get_output_dir() == tmp_path

    def test_get_output_dir_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        ctx = AgentContext()
        result = ctx.get_output_dir()
        assert result.resolve() == (tmp_path / "outputs").resolve()
        assert result.exists()

    def test_get_rossum_credentials_from_context(self) -> None:
        ctx = AgentContext(rossum_credentials=("https://api.example.com", "tok123"))
        assert ctx.get_rossum_credentials() == ("https://api.example.com", "tok123")

    def test_get_rossum_credentials_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = AgentContext()
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://env.example.com")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "envtok")
        assert ctx.get_rossum_credentials() == ("https://env.example.com", "envtok")

    def test_get_rossum_credentials_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = AgentContext()
        monkeypatch.delenv("ROSSUM_API_BASE_URL", raising=False)
        monkeypatch.delenv("ROSSUM_API_TOKEN", raising=False)
        assert ctx.get_rossum_credentials() is None

    def test_require_rossum_credentials_success(self) -> None:
        ctx = AgentContext(rossum_credentials=("https://api.example.com", "tok123"))
        assert ctx.require_rossum_credentials() == ("https://api.example.com", "tok123")

    def test_require_rossum_credentials_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = AgentContext()
        monkeypatch.delenv("ROSSUM_API_BASE_URL", raising=False)
        monkeypatch.delenv("ROSSUM_API_TOKEN", raising=False)
        with pytest.raises(ValueError, match="Rossum API credentials not available"):
            ctx.require_rossum_credentials()

    def test_report_progress_with_callback(self) -> None:
        callback = MagicMock()
        ctx = AgentContext(progress_callback=callback)
        progress = SubAgentProgress(tool_name="test", iteration=1, max_iterations=5)
        ctx.report_progress(progress)
        callback.assert_called_once_with(progress)

    def test_report_progress_no_callback(self) -> None:
        ctx = AgentContext()
        progress = SubAgentProgress(tool_name="test", iteration=1, max_iterations=5)
        ctx.report_progress(progress)  # should not raise

    def test_report_token_usage_with_callback(self) -> None:
        callback = MagicMock()
        ctx = AgentContext(token_callback=callback)
        usage = SubAgentTokenUsage(tool_name="test", input_tokens=100, output_tokens=50)
        ctx.report_token_usage(usage)
        callback.assert_called_once_with(usage)

    def test_report_token_usage_no_callback(self) -> None:
        ctx = AgentContext()
        usage = SubAgentTokenUsage(tool_name="test", input_tokens=100, output_tokens=50)
        ctx.report_token_usage(usage)  # should not raise

    def test_report_task_snapshot_with_callback(self) -> None:
        callback = MagicMock()
        ctx = AgentContext(task_snapshot_callback=callback)
        snapshot = [{"id": "1", "subject": "Test", "status": "pending"}]
        ctx.report_task_snapshot(snapshot)
        callback.assert_called_once_with(snapshot)

    def test_report_task_snapshot_no_callback(self) -> None:
        ctx = AgentContext()
        ctx.report_task_snapshot([])  # should not raise


class TestGetSetResetContext:
    """Tests for get_context(), set_context(), reset_context()."""

    def test_get_context_lazy_creation(self) -> None:
        # reset_context in fixture sets a fresh AgentContext; simulate no context
        ctx = get_context()
        assert isinstance(ctx, AgentContext)

    def test_set_and_get_context(self) -> None:
        custom = AgentContext(mcp_mode="read-write")
        token = set_context(custom)
        try:
            assert get_context() is custom
            assert get_context().mcp_mode == "read-write"
        finally:
            reset_context(token)

    def test_reset_context_restores_previous(self) -> None:
        original = get_context()
        custom = AgentContext(mcp_mode="read-write")
        token = set_context(custom)
        assert get_context() is custom
        reset_context(token)
        assert get_context() is original


class TestContextVarIsolation:
    """Tests for context variable thread isolation."""

    def test_context_isolated_between_threads(self, tmp_path: Path) -> None:
        """Test that AgentContext is isolated between threads."""
        results: dict[str, Path | None] = {}
        custom_dir = tmp_path / "thread_test"
        custom_dir.mkdir()

        def thread_func(thread_id: str) -> None:
            if thread_id == "thread1":
                ctx = AgentContext(output_dir=custom_dir)
                set_context(ctx)
                results[thread_id] = get_context().get_output_dir()
            else:
                results[thread_id] = get_context().get_output_dir()

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
            ctx = AgentContext(progress_callback=callback1)
            set_context(ctx)
            progress = SubAgentProgress(tool_name="t1", iteration=1, max_iterations=5)
            get_context().report_progress(progress)

        def thread2_func() -> None:
            progress = SubAgentProgress(tool_name="t2", iteration=1, max_iterations=5)
            get_context().report_progress(progress)

        t1 = threading.Thread(target=thread1_func)
        t2 = threading.Thread(target=thread2_func)

        t1.start()
        t1.join()
        t2.start()
        t2.join()

        callback1.assert_called_once()
        assert callback1.call_args[0][0].tool_name == "t1"


class TestMCPConnection:
    """Tests for MCP connection via AgentContext."""

    def test_set_mcp_connection(self) -> None:
        mock_connection = MagicMock()
        loop = asyncio.new_event_loop()

        try:
            ctx = AgentContext(mcp_connection=mock_connection, mcp_event_loop=loop)
            set_context(ctx)
            assert get_context().mcp_connection is mock_connection
            assert get_context().mcp_event_loop is loop
            assert get_context().mcp_mode == "read-only"  # Default mode
        finally:
            loop.close()

    def test_mcp_mode_read_write(self) -> None:
        mock_connection = MagicMock()
        loop = asyncio.new_event_loop()

        try:
            ctx = AgentContext(mcp_connection=mock_connection, mcp_event_loop=loop, mcp_mode="read-write")
            set_context(ctx)
            assert get_context().mcp_mode == "read-write"
            assert not get_context().is_read_only
        finally:
            loop.close()

    def test_is_read_only_default(self) -> None:
        assert get_context().mcp_mode == "read-only"

    def test_is_read_only_true(self) -> None:
        mock_connection = MagicMock()
        loop = asyncio.new_event_loop()

        try:
            ctx = AgentContext(mcp_connection=mock_connection, mcp_event_loop=loop, mcp_mode="read-only")
            set_context(ctx)
            assert get_context().is_read_only is True
        finally:
            loop.close()


class TestTaskTrackerContextVar:
    """Tests for task tracker via AgentContext."""

    def test_set_and_get_task_tracker(self) -> None:
        tracker = TaskTracker()
        ctx = get_context()
        ctx.task_tracker = tracker
        assert get_context().task_tracker is tracker

    def test_task_tracker_default_none(self) -> None:
        assert get_context().task_tracker is None

    def test_set_task_tracker_to_none(self) -> None:
        tracker = TaskTracker()
        ctx = get_context()
        ctx.task_tracker = tracker
        ctx.task_tracker = None
        assert get_context().task_tracker is None
