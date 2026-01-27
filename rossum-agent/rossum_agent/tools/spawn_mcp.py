"""Tools for spawning, calling, and closing MCP connections to different Rossum environments.

This module provides tools to manage secondary MCP connections to different Rossum
environments at runtime, enabling cross-environment operations like deployments.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass

from anthropic import beta_tool
from fastmcp import Client

from rossum_agent.rossum_mcp_integration import MCPConnection, create_mcp_transport
from rossum_agent.tools.core import get_mcp_event_loop

logger = logging.getLogger(__name__)


@dataclass
class SpawnedConnection:
    """Record for a spawned MCP connection to a different environment."""

    connection: MCPConnection
    client: Client
    api_base_url: str


# Secondary MCP connections spawned at runtime for different environments
_spawned_connections: dict[str, SpawnedConnection] = {}
_spawned_connections_lock = threading.Lock()


def get_spawned_connections() -> dict[str, SpawnedConnection]:
    """Get the spawned connections dict (for internal use only)."""
    return _spawned_connections


def get_spawned_connections_lock() -> threading.Lock:
    """Get the spawned connections lock (for internal use only)."""
    return _spawned_connections_lock


def clear_spawned_connections() -> None:
    """Clear all spawned connections. Called when MCP connection is reset."""
    with _spawned_connections_lock:
        _spawned_connections.clear()


async def _spawn_connection_async(
    connection_id: str, api_token: str, api_base_url: str, mcp_mode: str = "read-write"
) -> SpawnedConnection:
    """Spawn a new MCP connection asynchronously.

    Raises:
        ValueError: If connection_id already exists.
    """
    with _spawned_connections_lock:
        if connection_id in _spawned_connections:
            raise ValueError(f"Connection '{connection_id}' already exists")

    transport = create_mcp_transport(api_token, api_base_url, mcp_mode)  # type: ignore[arg-type]
    client = Client(transport)

    await client.__aenter__()
    connection = MCPConnection(client=client)

    record = SpawnedConnection(connection=connection, client=client, api_base_url=api_base_url)

    with _spawned_connections_lock:
        _spawned_connections[connection_id] = record

    return record


async def _close_spawned_connection_async(connection_id: str) -> None:
    """Close a spawned MCP connection."""
    with _spawned_connections_lock:
        record = _spawned_connections.pop(connection_id, None)

    if record is not None:
        await record.client.__aexit__(None, None, None)


def cleanup_all_spawned_connections() -> None:
    """Cleanup all spawned connections. Call this when the agent session ends.

    Should only be called once at session teardown, after no more tool calls are expected.
    """
    if (mcp_event_loop := get_mcp_event_loop()) is None:
        return

    with _spawned_connections_lock:
        conn_ids = list(_spawned_connections.keys())

    for conn_id in conn_ids:
        try:
            future = asyncio.run_coroutine_threadsafe(_close_spawned_connection_async(conn_id), mcp_event_loop)
            future.result(timeout=10)
        except FuturesTimeoutError:
            future.cancel()
            logger.warning(f"Timeout cleaning up connection {conn_id}")
        except Exception as e:
            logger.warning(f"Failed to cleanup connection {conn_id}: {e}")


@beta_tool
def spawn_mcp_connection(connection_id: str, api_token: str, api_base_url: str, mcp_mode: str = "read-write") -> str:
    """Spawn a new MCP connection to a different Rossum environment.

    Use this when you need to make changes to a different Rossum environment than the one the agent was initialized with.
    For example, when deploying changes from a source environment to a target environment.

    Args:
        connection_id: A unique identifier for this connection (e.g., 'target', 'sandbox')

    Returns:
        Success message with available tools, or error message if failed.
    """
    if (mcp_event_loop := get_mcp_event_loop()) is None:
        return "Error: MCP event loop not set. Agent not properly initialized."

    if not connection_id or not connection_id.strip():
        return "Error: connection_id must be non-empty."

    if not api_base_url or not api_base_url.startswith("https://"):
        return "Error: api_base_url must start with https://"

    try:
        future = asyncio.run_coroutine_threadsafe(
            _spawn_connection_async(connection_id, api_token, api_base_url, mcp_mode),
            mcp_event_loop,
        )
        record = future.result(timeout=30)

        tools_future = asyncio.run_coroutine_threadsafe(record.connection.get_tools(), mcp_event_loop)
        tools = tools_future.result(timeout=30)
        tool_names = [t.name for t in tools]

        return f"Successfully spawned MCP connection '{connection_id}' to {api_base_url}. Available tools: {', '.join(tool_names[:10])}{'...' if len(tool_names) > 10 else ''}"
    except ValueError as e:
        return f"Error: {e}"
    except FuturesTimeoutError:
        future.cancel()
        return "Error: Timed out while spawning MCP connection."
    except RuntimeError as e:
        logger.exception("Error scheduling MCP call")
        return f"Error: Failed to schedule MCP call: {e}"
    except Exception as e:
        logger.error(f"Failed to spawn connection: {e}")
        return f"Error spawning connection: {e}"


@beta_tool
def call_on_connection(connection_id: str, tool_name: str, arguments: str | dict) -> str:
    """Call a tool on a spawned MCP connection.

    Use this to execute MCP tools on a connection that was previously spawned with spawn_mcp_connection.

    Args:
        connection_id: The identifier of the spawned connection.
        tool_name: The name of the MCP tool to call.
        arguments: Arguments to pass to the tool (JSON string or dict).

    Returns:
        The result of the tool call as a JSON string, or error message.
    """
    if (mcp_event_loop := get_mcp_event_loop()) is None:
        return "Error: MCP event loop not set."

    with _spawned_connections_lock:
        if connection_id not in _spawned_connections:
            available = list(_spawned_connections.keys())
            return f"Error: Connection '{connection_id}' not found. Available: {available}"
        record = _spawned_connections[connection_id]

    logger.debug(f"call_on_connection: Using connection '{connection_id}' - API URL: {record.api_base_url}")

    if isinstance(arguments, dict):
        args = arguments
    elif arguments:
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError as e:
            return f"Error parsing arguments JSON: {e}"
    else:
        args = {}

    try:
        future = asyncio.run_coroutine_threadsafe(record.connection.call_tool(tool_name, args), mcp_event_loop)
        result = future.result(timeout=60)

        if isinstance(result, (dict, list)):
            return f"[{tool_name}] {json.dumps(result, indent=2, default=str)}"
        return f"[{tool_name}] {result}" if result is not None else f"[{tool_name}] Tool executed successfully"
    except FuturesTimeoutError:
        future.cancel()
        return f"Error: Timed out calling {tool_name} after 60 seconds."
    except Exception as e:
        logger.error(f"Error calling tool on connection: {e}")
        return f"Error calling {tool_name}: {e}"


@beta_tool
def close_connection(connection_id: str) -> str:
    """Close a spawned MCP connection."""
    if (mcp_event_loop := get_mcp_event_loop()) is None:
        return "Error: MCP event loop not set."

    with _spawned_connections_lock:
        if connection_id not in _spawned_connections:
            return f"Connection '{connection_id}' not found."

    try:
        future = asyncio.run_coroutine_threadsafe(_close_spawned_connection_async(connection_id), mcp_event_loop)
        future.result(timeout=10)
        return f"Successfully closed connection '{connection_id}'."
    except FuturesTimeoutError:
        future.cancel()
        return f"Error: Timed out closing connection '{connection_id}'."
    except Exception as e:
        return f"Error closing connection: {e}"
