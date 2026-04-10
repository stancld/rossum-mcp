"""Discovery tools for exploring available tool categories for dynamic tool loading."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from rossum_mcp.tools.base import MCPMode  # noqa: TC001 - runtime import needed for FastMCP return type serialization
from rossum_mcp.tools.catalog import CATEGORY_META

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_discovery_tools(mcp: FastMCP, mcp_mode: MCPMode) -> None:
    @mcp.tool(description="Get the current MCP operation mode.")
    async def get_mcp_mode() -> dict[str, MCPMode]:
        return {"mode": mcp_mode}

    @mcp.tool(
        description="List tool categories (descriptions, tool names, keywords). Use load_tool to load tools by name. read_only=false indicates write tools."
    )
    async def list_tool_categories() -> list[dict[str, str | int | list]]:
        categories: dict[str, list[dict[str, str | bool]]] = defaultdict(list)

        for tool in await mcp.local_provider.list_tools():
            tool_tags = tool.tags or set()
            for cat_name in CATEGORY_META:
                if cat_name in tool_tags:
                    categories[cat_name].append(
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
                "tools": (tools := categories.get(cat_name, [])),
                "tool_count": len(tools),
                "keywords": meta.keywords,
            }
            for cat_name, meta in CATEGORY_META.items()
        ]
