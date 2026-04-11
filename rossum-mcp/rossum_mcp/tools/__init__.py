"""FastMCP tool modules for Rossum MCP Server."""

from __future__ import annotations

from rossum_mcp.tools.catalog import (
    CATEGORY_META,
    CategoryMeta,
)
from rossum_mcp.tools.create import register_create_tools
from rossum_mcp.tools.delete.handler import register_delete_tools
from rossum_mcp.tools.discovery import register_discovery_tools
from rossum_mcp.tools.get.handler import register_get_tools
from rossum_mcp.tools.update import register_update_tools

__all__ = [
    "CATEGORY_META",
    "CategoryMeta",
    "register_create_tools",
    "register_delete_tools",
    "register_discovery_tools",
    "register_get_tools",
    "register_update_tools",
]
