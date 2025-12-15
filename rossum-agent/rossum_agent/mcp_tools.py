"""MCP Tools Integration Module.

Provides functionality to connect to the rossum-mcp server and convert MCP tools
to Anthropic tool format for use with the Claude API.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from mcp.types import Tool as MCPTool


@runtime_checkable
class MCPConnectionProtocol(Protocol):
    """Protocol for MCP connection-like objects.

    This protocol allows for duck typing of MCP connections, enabling
    subagents to use filtered connection wrappers.
    """

    async def get_tools(self) -> list[Any]:
        """Get the list of available tools."""
        ...

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a tool by name with the given arguments."""
        ...


@dataclass
class MCPConnection:
    """Holds the MCP client and provides tool operations."""

    client: Client
    _tools: list[MCPTool] | None = None

    async def get_tools(self) -> list[MCPTool]:
        """Get the list of available MCP tools (cached)."""
        if self._tools is None:
            self._tools = await self.client.list_tools()
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call an MCP tool by name with the given arguments.

        Args:
            name: The name of the tool to call.
            arguments: Optional dictionary of arguments to pass to the tool.

        Returns:
            The result of the tool call.
        """
        result = await self.client.call_tool(name, arguments or {})
        if result.data is not None:
            return result.data
        if result.content:
            text_parts = [block.text for block in result.content if hasattr(block, "text") and block.text]
            if len(text_parts) == 1:
                return text_parts[0]
            return "\n".join(text_parts) if text_parts else None
        return None


def create_mcp_transport(
    rossum_api_token: str, rossum_api_base_url: str, mcp_mode: Literal["read-only", "read-write"] = "read-only"
) -> StdioTransport:
    """Create a StdioTransport for the rossum-mcp server.

    Args:
        rossum_api_token: Rossum API token for authentication.
        rossum_api_base_url: Rossum API base URL.

    Returns:
        Configured StdioTransport for the rossum-mcp server.
    """
    return StdioTransport(
        command="rossum-mcp",
        args=[],
        env={
            "ROSSUM_API_BASE_URL": rossum_api_base_url,
            "ROSSUM_API_TOKEN": rossum_api_token,
            "ROSSUM_MCP_MODE": mcp_mode,
            **os.environ,
        },
    )


@asynccontextmanager
async def connect_mcp_server(
    rossum_api_token: str, rossum_api_base_url: str, mcp_mode: Literal["read-only", "read-write"] = "read-only"
) -> AsyncIterator[MCPConnection]:
    """Connect to the rossum-mcp server and yield an MCPConnection.

    This context manager handles the lifecycle of the MCP client connection.
    Tools are cached after the first retrieval for efficiency.

    Args:
        rossum_api_token: Rossum API token for authentication.
        rossum_api_base_url: Rossum API base URL.

    Yields:
        MCPConnection with the connected client.
    """
    transport = create_mcp_transport(
        rossum_api_token=rossum_api_token, rossum_api_base_url=rossum_api_base_url, mcp_mode=mcp_mode
    )

    client = Client(transport)
    async with client:
        yield MCPConnection(client=client)


def mcp_tool_to_anthropic_format(mcp_tool: MCPTool) -> dict[str, object]:
    """Convert a single MCP tool to Anthropic tool format.

    Args:
        mcp_tool: An MCP tool object.

    Returns:
        Tool definition dict in Anthropic format.
    """
    return {"name": mcp_tool.name, "description": mcp_tool.description or "", "input_schema": mcp_tool.inputSchema}


def mcp_tools_to_anthropic_format(mcp_tools: list[MCPTool]) -> list[dict[str, object]]:
    """Convert MCP tools to Anthropic tool format.

    Anthropic's tool format requires:
    - name: The name of the tool
    - description: A description of what the tool does
    - input_schema: JSON Schema describing the tool's parameters

    Args:
        mcp_tools: List of MCP tool objects from list_tools().

    Returns:
        List of tool dicts suitable for the tools parameter in messages.create().
    """
    return [mcp_tool_to_anthropic_format(tool) for tool in mcp_tools]
