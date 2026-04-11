"""Observability middleware for FastMCP tool calls.

Binds correlation context (session_id, request_id) to structlog contextvars
so that all downstream log lines include trace identifiers. Emits structured
tool-call metrics (started/completed/failed with duration).
"""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING

import structlog
from fastmcp.server.middleware import Middleware

if TYPE_CHECKING:
    import mcp.types as mt
    from fastmcp.server.middleware import CallNext, MiddlewareContext
    from fastmcp.tools.base import ToolResult

logger = structlog.get_logger("rossum_mcp.middleware")


class ObservabilityMiddleware(Middleware):
    """Binds correlation IDs and emits structured tool-call events."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        tool_name = context.message.name

        # Extract correlation IDs from FastMCP context.
        session_id = None
        request_id = None
        ctx = context.fastmcp_context
        if ctx is not None and ctx.request_context is not None:
            with contextlib.suppress(RuntimeError, AttributeError):
                session_id = ctx.session_id
            with contextlib.suppress(RuntimeError, AttributeError):
                request_id = ctx.request_id

        bound_keys = ["tool_name"]
        bind_kwargs: dict[str, str] = {"tool_name": tool_name}
        if session_id is not None:
            bind_kwargs["session_id"] = session_id
            bound_keys.append("session_id")
        if request_id is not None:
            bind_kwargs["request_id"] = request_id
            bound_keys.append("request_id")

        structlog.contextvars.bind_contextvars(**bind_kwargs)

        start = time.perf_counter()
        try:
            logger.debug("tool_call.started", arguments=context.message.arguments)
            result = await call_next(context)
            duration = time.perf_counter() - start
            logger.info(
                "tool_call.completed",
                duration_seconds=round(duration, 3),
                status="success",
            )
            return result
        except Exception as exc:
            duration = time.perf_counter() - start
            logger.error(
                "tool_call.failed",
                duration_seconds=round(duration, 3),
                status="error",
                error_type=type(exc).__name__,
            )
            raise
        finally:
            structlog.contextvars.unbind_contextvars(*bound_keys)
