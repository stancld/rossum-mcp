"""MCP connection management.

Provides MCPConnection (the main client wrapper), transport creation,
and the connect_mcp_server context manager.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from rossum_agent.rossum_mcp_integration.change_tracking import ChangeTrackingMixin
from rossum_agent.rossum_mcp_integration.tools import unwrap

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import valkey
    from mcp.types import Tool as MCPTool

    from rossum_agent.api.models.schemas import MCPMode
    from rossum_agent.change_tracking.models import EntityChange
    from rossum_agent.change_tracking.store import CommitStore, SnapshotStore

logger = logging.getLogger(__name__)


@dataclass
class MCPConnection(ChangeTrackingMixin):
    """MCP client connection with optional change tracking.

    When write_tools is provided, the connection intercepts write operations,
    caches read results, and tracks entity changes for version control.
    """

    client: Client
    write_tools: set[str] = field(default_factory=set)
    chat_id: str | None = None
    valkey_client: valkey.Valkey | None = None
    cache_ttl_seconds: int = 30 * 24 * 3600
    _tools: list[MCPTool] | None = field(default=None, init=False, repr=False)
    _read_cache: dict[tuple[str, str], dict] = field(default_factory=dict, init=False, repr=False)
    _changes: list[EntityChange] = field(default_factory=list, init=False, repr=False)
    _commit_store: CommitStore | None = field(default=None, init=False, repr=False)
    _snapshot_store: SnapshotStore | None = field(default=None, init=False, repr=False)
    _environment: str | None = field(default=None, init=False, repr=False)

    async def get_tools(self) -> list[MCPTool]:
        """Get the list of available MCP tools (cached)."""
        if self._tools is None:
            self._tools = await self.client.list_tools()
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call an MCP tool by name with the given arguments."""
        arguments = arguments or {}

        if name in self.write_tools:
            return await self._handle_write(name, arguments)

        result = await self._call_mcp(name, arguments)
        self._try_cache_read(name, arguments, result)
        return result

    async def _call_mcp(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute the raw MCP tool call and extract the result."""
        logger.info(f"Calling MCP tool {name}")

        result = await self.client.call_tool(name, arguments)
        # Prefer structured_content (raw dict) over data (parsed pydantic model)
        # because FastMCP's json_schema_to_type has a bug where nested dict fields
        # like config: dict[str, Any] become empty dataclasses, losing all data.
        if result.structured_content is not None:
            raw = result.structured_content
            # FastMCP sometimes wraps return values in {"result": ...}
            if isinstance(raw, dict):
                return unwrap(raw)
            return raw
        if result.data is not None:
            return result.data
        if result.content:
            text_parts = [str(block.text) for block in result.content if hasattr(block, "text") and block.text]
            if len(text_parts) == 1:
                return text_parts[0]
            return "\n".join(text_parts) if text_parts else None
        return None


def create_mcp_transport(
    rossum_api_token: str, rossum_api_base_url: str, mcp_mode: MCPMode = "read-only"
) -> StdioTransport:
    """Create a StdioTransport for the rossum-mcp server."""
    return StdioTransport(
        command="rossum-mcp",
        args=[],
        env={
            **os.environ,
            "ROSSUM_API_BASE_URL": rossum_api_base_url.rstrip("/"),
            "ROSSUM_API_TOKEN": rossum_api_token,
            "ROSSUM_MCP_MODE": mcp_mode,
        },
    )


@asynccontextmanager
async def connect_mcp_server(
    rossum_api_token: str, rossum_api_base_url: str, mcp_mode: MCPMode = "read-only"
) -> AsyncIterator[MCPConnection]:
    """Connect to the rossum-mcp server and yield an MCPConnection.

    This context manager handles the lifecycle of the MCP client connection.
    Tools are cached after the first retrieval for efficiency.
    """
    transport = create_mcp_transport(
        rossum_api_token=rossum_api_token, rossum_api_base_url=rossum_api_base_url, mcp_mode=mcp_mode
    )
    async with (client := Client(transport)):
        yield MCPConnection(client=client)
