"""Core module with shared types, callbacks, and MCP state management.

This module provides the foundational types and state management used by
all internal tools. Uses contextvars for thread-safe state management.
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio

    from rossum_agent.rossum_mcp_integration import MCPConnection


@dataclass
class SubAgentProgress:
    """Progress information from a sub-agent (e.g., debug_hook's Opus sub-agent)."""

    tool_name: str
    iteration: int
    max_iterations: int
    current_tool: str | None = None
    tool_calls: list[str] = field(default_factory=list)
    status: str = "running"


@dataclass
class SubAgentText:
    """Text output from a sub-agent (e.g., debug_hook's Opus sub-agent)."""

    tool_name: str
    text: str
    is_final: bool = False


SubAgentProgressCallback = Callable[[SubAgentProgress], None]
SubAgentTextCallback = Callable[[SubAgentText], None]

# Context variables for thread-safe state management
_progress_callback: ContextVar[SubAgentProgressCallback | None] = ContextVar("progress_callback", default=None)
_text_callback: ContextVar[SubAgentTextCallback | None] = ContextVar("text_callback", default=None)
_mcp_connection: ContextVar[MCPConnection | None] = ContextVar("mcp_connection", default=None)
_mcp_event_loop: ContextVar[asyncio.AbstractEventLoop | None] = ContextVar("mcp_event_loop", default=None)
_output_dir: ContextVar[Path | None] = ContextVar("output_dir", default=None)


def set_progress_callback(callback: SubAgentProgressCallback | None) -> None:
    """Set the progress callback for sub-agent progress reporting."""
    _progress_callback.set(callback)


def set_text_callback(callback: SubAgentTextCallback | None) -> None:
    """Set the text callback for sub-agent text reporting."""
    _text_callback.set(callback)


def report_progress(progress: SubAgentProgress) -> None:
    """Report progress via the callback if set."""
    if (callback := _progress_callback.get()) is not None:
        callback(progress)


def report_text(text: SubAgentText) -> None:
    """Report text via the callback if set."""
    if (callback := _text_callback.get()) is not None:
        callback(text)


def set_output_dir(output_dir: Path | None) -> None:
    """Set the output directory for internal tools."""
    _output_dir.set(output_dir)


def get_output_dir() -> Path:
    """Get the output directory for internal tools."""
    if (output_dir := _output_dir.get()) is not None:
        return output_dir
    fallback = Path("./outputs")
    fallback.mkdir(exist_ok=True)
    return fallback


def set_mcp_connection(connection: MCPConnection | None, loop: asyncio.AbstractEventLoop | None) -> None:
    """Set the MCP connection for use by internal tools (pass None to clear)."""
    _mcp_connection.set(connection)
    _mcp_event_loop.set(loop)


def get_mcp_connection() -> MCPConnection | None:
    """Get the current MCP connection."""
    return _mcp_connection.get()


def get_mcp_event_loop() -> asyncio.AbstractEventLoop | None:
    """Get the current MCP event loop."""
    return _mcp_event_loop.get()
