"""Discovery tools for dynamic tool loading.

Provides MCP tool to explore available tool categories and their metadata.
The agent uses this to fetch the catalog and load tools on-demand.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from rossum_mcp.tools.catalog import TOOL_CATALOG

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_discovery_tools(mcp: FastMCP) -> None:
    """Register discovery tools with the FastMCP server."""

    @mcp.tool(
        description="List all available tool categories with descriptions, tool names, and keywords. "
        "Use this to discover what tools are available, then use load_tool_category to load "
        "tools from specific categories before using them. Tools with read_only=false are write "
        "operations (create, update, delete)."
    )
    async def list_tool_categories() -> list[dict]:
        return [
            {
                "name": category.name,
                "description": category.description,
                "tool_count": len(category.tools),
                "tools": [asdict(tool) for tool in category.tools],
                "keywords": category.keywords,
            }
            for category in TOOL_CATALOG.values()
        ]
