"""Discovery tools for dynamic tool loading.

Provides MCP tool to explore available tool categories and their metadata.
Tool lists are derived from tags on @mcp.tool decorators rather than a static catalog.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_mcp.tools.catalog import CATEGORY_META

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from rossum_mcp.tools.base import McpMode


def register_discovery_tools(mcp: FastMCP, mcp_mode: McpMode) -> None:
    @mcp.tool(description="Get the current MCP operation mode (read-only or read-write).")
    async def get_mcp_mode() -> dict:
        return {"mode": mcp_mode}

    @mcp.tool(
        description="List tool categories (descriptions, tool names, keywords). Use load_tool to load tools by name. read_only=false indicates write tools."
    )
    async def list_tool_categories() -> list[dict]:
        all_tools = await mcp.local_provider.list_tools()

        # Group tools by category tag
        categories: dict[str, list[dict]] = {}
        for tool in all_tools:
            tool_tags = tool.tags or set()
            for cat_name in CATEGORY_META:
                if cat_name in tool_tags:
                    categories.setdefault(cat_name, []).append(
                        {
                            "name": tool.name,
                            "description": tool.description or "",
                            "read_only": "write" not in tool_tags,
                        }
                    )
                    break

        return [
            {
                "name": cat_name,
                "description": meta.description,
                "tool_count": len(categories.get(cat_name, [])),
                "tools": categories.get(cat_name, []),
                "keywords": meta.keywords,
            }
            for cat_name, meta in CATEGORY_META.items()
        ]
