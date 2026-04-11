"""Tests for rossum_mcp.middleware module."""

from __future__ import annotations

import io
import json
import logging
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import mcp.types as mt
import pytest
import structlog
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.tools.base import ToolResult
from rossum_mcp.logging_config import LogFormat, LogLevel, setup_logging
from rossum_mcp.middleware import ObservabilityMiddleware


@pytest.fixture(autouse=True)
def _setup_logging():
    setup_logging(log_level=LogLevel.DEBUG, log_format=LogFormat.JSON)
    yield
    structlog.contextvars.clear_contextvars()
    root = logging.getLogger()
    handlers_to_remove = [
        h
        for h in root.handlers
        if not isinstance(h, logging.NullHandler) and h.__class__.__name__ != "LogCaptureHandler"
    ]
    for h in handlers_to_remove:
        root.removeHandler(h)


@pytest.fixture
def log_output():
    """Capture structured log output via a StringIO handler."""
    buf = io.StringIO()
    root = logging.getLogger()
    # Reuse the ProcessorFormatter from the existing handler
    formatter = root.handlers[0].formatter
    handler = logging.StreamHandler(buf)
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)
    root.addHandler(handler)
    yield buf
    root.removeHandler(handler)


def _make_context(
    tool_name: str = "search_queues",
    session_id: str | None = "sess-1",
    request_id: str | None = "req-1",
    arguments: dict | None = None,
) -> MiddlewareContext[mt.CallToolRequestParams]:
    message = mt.CallToolRequestParams(name=tool_name, arguments=arguments or {})

    fastmcp_ctx = None
    if session_id is not None or request_id is not None:
        fastmcp_ctx = MagicMock()
        fastmcp_ctx.request_context = MagicMock()
        type(fastmcp_ctx).session_id = PropertyMock(return_value=session_id)
        type(fastmcp_ctx).request_id = PropertyMock(return_value=request_id)

    return MiddlewareContext(
        message=message,
        fastmcp_context=fastmcp_ctx,
        method="tools/call",
    )


def _parse_log_lines(buf: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in buf.getvalue().strip().split("\n") if line.strip()]


class TestObservabilityMiddleware:
    @pytest.fixture
    def middleware(self) -> ObservabilityMiddleware:
        return ObservabilityMiddleware()

    async def test_successful_call_logs_completed(self, middleware, log_output):
        context = _make_context()
        tool_result = ToolResult(content=[mt.TextContent(type="text", text="ok")])
        call_next = AsyncMock(return_value=tool_result)

        result = await middleware.on_call_tool(context, call_next)

        assert result is tool_result
        call_next.assert_awaited_once_with(context)

        entries = _parse_log_lines(log_output)
        events = {e["event"] for e in entries}
        assert "tool_call.started" in events
        assert "tool_call.completed" in events

    async def test_failed_call_logs_error_and_reraises(self, middleware, log_output):
        context = _make_context()
        call_next = AsyncMock(side_effect=ValueError("boom"))

        with pytest.raises(ValueError, match="boom"):
            await middleware.on_call_tool(context, call_next)

        entries = _parse_log_lines(log_output)
        events = {e["event"] for e in entries}
        assert "tool_call.failed" in events

        failed = next(e for e in entries if e["event"] == "tool_call.failed")
        assert failed["error_type"] == "ValueError"
        assert failed["status"] == "error"
        assert "duration_seconds" in failed

    async def test_binds_and_unbinds_contextvars(self, middleware):
        context = _make_context(session_id="sess-x", request_id="req-y")
        captured_ctx = {}

        async def capturing_call_next(_ctx):
            captured_ctx.update(structlog.contextvars.get_contextvars())
            return ToolResult(content=[mt.TextContent(type="text", text="ok")])

        await middleware.on_call_tool(context, capturing_call_next)

        assert captured_ctx["session_id"] == "sess-x"
        assert captured_ctx["request_id"] == "req-y"
        assert captured_ctx["tool_name"] == "search_queues"

        remaining = structlog.contextvars.get_contextvars()
        assert "session_id" not in remaining
        assert "request_id" not in remaining
        assert "tool_name" not in remaining

    async def test_unbinds_contextvars_on_failure(self, middleware):
        context = _make_context()
        call_next = AsyncMock(side_effect=RuntimeError("fail"))

        with pytest.raises(RuntimeError):
            await middleware.on_call_tool(context, call_next)

        remaining = structlog.contextvars.get_contextvars()
        assert "session_id" not in remaining
        assert "tool_name" not in remaining

    async def test_handles_missing_fastmcp_context(self, middleware, log_output):
        context = MiddlewareContext(
            message=mt.CallToolRequestParams(name="test_tool", arguments={}),
            fastmcp_context=None,
            method="tools/call",
        )
        tool_result = ToolResult(content=[mt.TextContent(type="text", text="ok")])
        call_next = AsyncMock(return_value=tool_result)

        result = await middleware.on_call_tool(context, call_next)
        assert result is tool_result

        entries = _parse_log_lines(log_output)
        events = {e["event"] for e in entries}
        assert "tool_call.completed" in events

    async def test_completed_log_has_duration_and_tool_name(self, middleware, log_output):
        context = _make_context()
        tool_result = ToolResult(content=[mt.TextContent(type="text", text="ok")])
        call_next = AsyncMock(return_value=tool_result)

        await middleware.on_call_tool(context, call_next)

        entries = _parse_log_lines(log_output)
        completed = next(e for e in entries if e["event"] == "tool_call.completed")
        assert "duration_seconds" in completed
        assert completed["status"] == "success"
        assert completed["tool_name"] == "search_queues"

    async def test_started_log_includes_arguments(self, middleware, log_output):
        context = _make_context(arguments={"name": "test"})
        tool_result = ToolResult(content=[mt.TextContent(type="text", text="ok")])
        call_next = AsyncMock(return_value=tool_result)

        await middleware.on_call_tool(context, call_next)

        entries = _parse_log_lines(log_output)
        started = next(e for e in entries if e["event"] == "tool_call.started")
        assert started["arguments"] == {"name": "test"}
