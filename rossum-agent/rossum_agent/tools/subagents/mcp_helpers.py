"""Shared MCP helper functions for sub-agents.

Provides common utilities for calling MCP tools from synchronous thread contexts.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from rossum_agent.tools.core import get_mcp_connection, get_mcp_event_loop

logger = logging.getLogger(__name__)


def call_mcp_tool(name: str, arguments: dict[str, Any], timeout: int = 60) -> Any:
    """Call an MCP tool synchronously from within a thread.

    Uses run_coroutine_threadsafe to call async MCP tools from sync context.

    Args:
        name: MCP tool name to call.
        arguments: Arguments to pass to the tool.
        timeout: Timeout in seconds (default 60).

    Returns:
        The result from the MCP tool.

    Raises:
        RuntimeError: If MCP connection is not set.
    """
    mcp_connection = get_mcp_connection()
    mcp_event_loop = get_mcp_event_loop()
    if mcp_connection is None or mcp_event_loop is None:
        raise RuntimeError("MCP connection not set. Call set_mcp_connection first.")

    start = time.perf_counter()
    future = asyncio.run_coroutine_threadsafe(mcp_connection.call_tool(name, arguments), mcp_event_loop)
    result = future.result(timeout=timeout)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"MCP call '{name}' completed in {elapsed_ms:.1f}ms")
    return result
