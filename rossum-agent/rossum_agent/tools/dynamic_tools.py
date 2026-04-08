"""Dynamic tool loading for the Rossum Agent.

Provides functionality to load MCP tool categories on-demand to reduce context usage.
Catalog metadata is fetched from MCP server (single source of truth) and cached.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from rossum_agent.rossum_mcp_integration import mcp_tools_to_anthropic_format
from rossum_agent.tools.core import get_context

if TYPE_CHECKING:
    from anthropic.types import ToolParam
    from mcp.types import Tool as MCPTool

    from rossum_agent.rossum_mcp_integration import MCPConnection

logger = logging.getLogger(__name__)


@dataclass
class CatalogData:
    """Cached catalog data from MCP server."""

    catalog: dict[str, set[str]] = field(default_factory=dict)
    keywords: dict[str, list[str]] = field(default_factory=dict)
    write_tools: set[str] = field(default_factory=set)


# Cached catalog from MCP (fetched once per process)
_catalog_cache: CatalogData | None = None

# Discovery tool that's always loaded
DISCOVERY_TOOL_NAME = "list_tool_categories"

# Unified delete tool — always loaded in read-write mode (not part of any category)
DELETE_TOOL_NAME = "delete"


def reset_dynamic_tools() -> None:
    """Reset dynamic tool state for a new conversation."""
    get_context().dynamic_tools.reset()


def get_dynamic_tools() -> list[ToolParam]:
    """Get the list of dynamically loaded tools."""
    return get_context().dynamic_tools.tools


def mark_skill_loaded(name: str) -> None:
    """Mark a skill as loaded and increment version to invalidate tool cache."""
    state = get_context().dynamic_tools
    state.loaded_skills.add(name)
    state.version += 1


def get_tools_version() -> int:
    """Get current tools version for cache invalidation."""
    return get_context().dynamic_tools.version


def _parse_catalog_result(result: object) -> CatalogData:
    """Parse raw MCP catalog result into CatalogData."""
    # Handle various result formats from MCP
    if isinstance(result, str):
        result = json.loads(result)
    if isinstance(result, dict) and "result" in result:
        result = result["result"]  # ty:ignore[invalid-argument-type] - unwrapping FastMCP wrapper
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, list):
        logger.warning("Unexpected catalog result type: %s", type(result).__name__)
        return CatalogData()

    categories = cast("list[dict]", result)
    catalog: dict[str, set[str]] = {}
    keywords: dict[str, list[str]] = {}
    write_tools: set[str] = set()

    for category in categories:
        name = category["name"]
        catalog[name] = {tool["name"] for tool in category["tools"]}
        keywords[name] = category.get("keywords", [])
        for tool in category["tools"]:
            if not tool.get("read_only", True):
                write_tools.add(tool["name"])

    return CatalogData(catalog=catalog, keywords=keywords, write_tools=write_tools)


def _fetch_catalog_from_mcp() -> CatalogData:
    """Fetch tool catalog from MCP server (sync, uses global connection)."""
    global _catalog_cache

    if _catalog_cache is not None:
        return _catalog_cache

    ctx = get_context()

    if ctx.mcp_connection is None or ctx.mcp_event_loop is None:
        logger.warning("MCP connection not available, returning empty catalog")
        return CatalogData()

    try:
        result = asyncio.run_coroutine_threadsafe(
            ctx.mcp_connection.call_tool("list_tool_categories", {}), ctx.mcp_event_loop
        ).result(timeout=10)
        _catalog_cache = _parse_catalog_result(result)
        logger.info(f"Fetched catalog with {len(_catalog_cache.catalog)} categories from MCP")
        return _catalog_cache

    except Exception as e:
        logger.error(f"Failed to fetch catalog from MCP: {e}")
        return CatalogData()


async def _fetch_catalog_async(mcp_connection: MCPConnection) -> CatalogData:
    """Fetch tool catalog from MCP server (async, accepts connection directly)."""
    global _catalog_cache

    if _catalog_cache is not None:
        return _catalog_cache

    try:
        result = await mcp_connection.call_tool("list_tool_categories", {})
        _catalog_cache = _parse_catalog_result(result)
        logger.info(f"Fetched catalog with {len(_catalog_cache.catalog)} categories from MCP")
        return _catalog_cache
    except Exception as e:
        logger.error(f"Failed to fetch catalog from MCP: {e}")
        return CatalogData()


def get_category_tool_names() -> dict[str, set[str]]:
    """Get mapping of category names to tool names (fetched from MCP)."""
    return _fetch_catalog_from_mcp().catalog


def get_category_keywords() -> dict[str, list[str]]:
    """Get mapping of category names to keywords (fetched from MCP)."""
    return _fetch_catalog_from_mcp().keywords


def get_write_tools() -> set[str]:
    tools = _fetch_catalog_from_mcp().write_tools
    # The unified delete tool lives outside any category but is always a write tool
    tools.add(DELETE_TOOL_NAME)
    return tools


def is_mcp_write_tool(name: str) -> bool:
    """Check if a tool name is a write operation based on cached catalog."""
    if _catalog_cache is None:
        return False
    return name in _catalog_cache.write_tools or name == DELETE_TOOL_NAME


def get_cached_category_tool_names() -> dict[str, set[str]] | None:
    """Get cached category→tool mapping, or None if catalog not yet fetched."""
    return _catalog_cache.catalog if _catalog_cache is not None else None


async def get_write_tools_async(mcp_connection: MCPConnection) -> set[str]:
    tools = (await _fetch_catalog_async(mcp_connection)).write_tools
    # The unified delete tool lives outside any category but is always a write tool
    tools.add(DELETE_TOOL_NAME)
    return tools


def suggest_categories_for_request(request_text: str) -> list[str]:
    """Suggest tool categories based on keywords in the request.

    Uses word boundary matching to avoid false positives (e.g., "credit" matching "edit").
    """
    keywords = get_category_keywords()
    if not keywords:
        return []

    request_lower = request_text.lower()
    suggestions: list[str] = []

    for category, category_keywords in keywords.items():
        for keyword in category_keywords:
            pattern = rf"\b{re.escape(keyword)}\b"
            if re.search(pattern, request_lower):
                suggestions.append(category)
                break

    return suggestions


def _filter_mcp_tools_by_names(mcp_tools: list[MCPTool], tool_names: set[str]) -> list[MCPTool]:
    """Filter MCP tools to only those with names in the given set."""
    return [tool for tool in mcp_tools if tool.name in tool_names]


def _load_categories_impl(categories: list[str]) -> str:
    """Load multiple tool categories at once.

    In read-only mode, write tools (read_only=False) are excluded.
    """
    state = get_context().dynamic_tools

    catalog = get_category_tool_names()
    if not catalog:
        return "Error: Could not fetch tool catalog from MCP"

    valid_categories = set(catalog.keys())
    invalid = [c for c in categories if c not in valid_categories]
    if invalid:
        return f"Error: Unknown categories {invalid}. Valid: {sorted(valid_categories)}"

    to_load = [c for c in categories if c not in state.loaded_categories]

    if not to_load:
        return f"Categories already loaded: {categories}"

    ctx = get_context()
    if ctx.mcp_connection is None or ctx.mcp_event_loop is None:
        return "Error: MCP connection not available"

    tool_names_to_load: set[str] = set()
    for category in to_load:
        tool_names_to_load.update(catalog[category])

    read_only = ctx.is_read_only
    if read_only:
        tool_names_to_load -= get_write_tools()

    mcp_tools = asyncio.run_coroutine_threadsafe(ctx.mcp_connection.get_tools(), ctx.mcp_event_loop).result()
    tools_to_add = _filter_mcp_tools_by_names(mcp_tools, tool_names_to_load)

    if not tools_to_add:
        return f"No tools found for categories: {to_load}"

    anthropic_tools = mcp_tools_to_anthropic_format(tools_to_add)
    state.tools.extend(anthropic_tools)

    for category in to_load:
        state.loaded_categories.add(category)

    tool_names = [t.name for t in tools_to_add]
    logger.info(f"Loaded {len(tool_names)} tools from categories {to_load}: {tool_names}")

    mode_suffix = " (read-only mode)" if read_only else ""
    return f"Loaded {len(tool_names)} tools from {to_load}{mode_suffix}: {', '.join(sorted(tool_names))}"


def preload_categories_for_request(request_text: str) -> str | None:
    """Pre-load tool categories based on keywords in the user's request.

    The ``read`` category (``get``, ``search``) is always included because the
    unified read layer is needed by virtually every request.
    """
    suggestions = suggest_categories_for_request(request_text)
    if "read" not in suggestions:
        suggestions.insert(0, "read")

    result = _load_categories_impl(suggestions)
    if result.startswith("Error") or result.startswith("Categories already"):
        return None

    logger.info(f"Pre-loaded categories based on request keywords: {suggestions}")
    return result


def get_load_tool_definition() -> ToolParam:
    """Get the tool definition for load_tool."""
    return {
        "name": "load_tool",
        "description": (
            "Load specific MCP tools by name. Once loaded, the tools become "
            "available for use. Use list_tool_categories to see available tool names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tool names to load (e.g., ['get', 'search'])",
                },
            },
            "required": ["tool_names"],
        },
    }


def load_tool(tool_names: list[str]) -> str:
    """Load specific MCP tools by name. In read-only mode, write tools are excluded."""
    ctx = get_context()
    state = ctx.dynamic_tools
    if ctx.mcp_connection is None or ctx.mcp_event_loop is None:
        return "Error: MCP connection not available"

    mcp_tools = asyncio.run_coroutine_threadsafe(ctx.mcp_connection.get_tools(), ctx.mcp_event_loop).result()
    available_tool_names = {t.name for t in mcp_tools}

    invalid = [name for name in tool_names if name not in available_tool_names]
    if invalid:
        return f"Error: Unknown tools {invalid}"

    read_only = ctx.is_read_only
    if read_only:
        write_tools = get_write_tools()
        blocked = [name for name in tool_names if name in write_tools]
        if blocked:
            return f"Error: Write tools not available in read-only mode: {blocked}"

    already_loaded = {t["name"] for t in state.tools}
    to_load = [name for name in tool_names if name not in already_loaded]

    if not to_load:
        return f"Tools already loaded: {tool_names}"

    tools_to_add = _filter_mcp_tools_by_names(mcp_tools, set(to_load))
    anthropic_tools = mcp_tools_to_anthropic_format(tools_to_add)
    state.tools.extend(anthropic_tools)

    logger.info(f"Loaded {len(to_load)} tools by name: {to_load}")
    return f"Loaded tools: {', '.join(sorted(to_load))}"
