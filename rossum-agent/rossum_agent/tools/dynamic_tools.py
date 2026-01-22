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
from typing import TYPE_CHECKING

from rossum_agent.rossum_mcp_integration import mcp_tools_to_anthropic_format
from rossum_agent.tools.core import get_mcp_connection, get_mcp_event_loop

if TYPE_CHECKING:
    from anthropic.types import ToolParam
    from mcp.types import Tool as MCPTool

logger = logging.getLogger(__name__)


@dataclass
class CatalogData:
    """Cached catalog data from MCP server."""

    catalog: dict[str, set[str]] = field(default_factory=dict)
    keywords: dict[str, list[str]] = field(default_factory=dict)
    destructive_tools: set[str] = field(default_factory=set)


# Cached catalog from MCP (fetched once per process)
_catalog_cache: CatalogData | None = None

# Discovery tool that's always loaded
DISCOVERY_TOOL_NAME = "list_tool_categories"


@dataclass
class DynamicToolsState:
    """Mutable state container for dynamically loaded tools.

    Stored on RossumAgent instance and passed to functions that need to modify
    tool state. Using a class allows modifications in thread pool executors to
    be visible in the main context (unlike context variables which are copied).
    """

    loaded_categories: set[str] = field(default_factory=set)
    tools: list[ToolParam] = field(default_factory=list)

    def reset(self) -> None:
        """Reset state for a new conversation."""
        self.loaded_categories.clear()
        self.tools.clear()


# Global state for backwards compatibility (used when agent instance not available)
_global_state: DynamicToolsState | None = None


def get_global_state() -> DynamicToolsState:
    """Get or create global state for backwards compatibility."""
    global _global_state
    if _global_state is None:
        _global_state = DynamicToolsState()
    return _global_state


def reset_dynamic_tools() -> None:
    """Reset dynamic tool state for a new conversation (global state)."""
    get_global_state().reset()


def get_loaded_categories() -> set[str]:
    """Get the set of currently loaded categories (global state)."""
    return get_global_state().loaded_categories


def get_dynamic_tools() -> list[ToolParam]:
    """Get the list of dynamically loaded tools (global state)."""
    return get_global_state().tools


def _fetch_catalog_from_mcp() -> CatalogData:
    """Fetch tool catalog from MCP server."""
    global _catalog_cache

    if _catalog_cache is not None:
        return _catalog_cache

    mcp_connection = get_mcp_connection()
    loop = get_mcp_event_loop()

    if mcp_connection is None or loop is None:
        logger.warning("MCP connection not available, returning empty catalog")
        return CatalogData()

    # Call list_tool_categories MCP tool to get catalog
    try:
        result = asyncio.run_coroutine_threadsafe(mcp_connection.call_tool("list_tool_categories", {}), loop).result(
            timeout=10
        )

        # Handle various result formats from MCP
        # 1. String (JSON) - parse it
        if isinstance(result, str):
            result = json.loads(result)

        # 2. FastMCP wraps list returns in {"result": [...]}
        if isinstance(result, dict) and "result" in result:
            result = result["result"]

        # 3. The unwrapped result might also be a JSON string
        if isinstance(result, str):
            result = json.loads(result)

        catalog: dict[str, set[str]] = {}
        keywords: dict[str, list[str]] = {}
        destructive_tools: set[str] = set()

        for category in result:
            name = category["name"]
            catalog[name] = {tool["name"] for tool in category["tools"]}
            keywords[name] = category.get("keywords", [])
            for tool in category["tools"]:
                if tool.get("destructive", False):
                    destructive_tools.add(tool["name"])

        _catalog_cache = CatalogData(catalog=catalog, keywords=keywords, destructive_tools=destructive_tools)
        logger.info(f"Fetched catalog with {len(catalog)} categories from MCP")
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


def get_destructive_tools() -> set[str]:
    """Get set of destructive tool names (fetched from MCP)."""
    return _fetch_catalog_from_mcp().destructive_tools


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


def _filter_discovery_tools(mcp_tools: list[MCPTool]) -> list[MCPTool]:
    """Filter MCP tools to only discovery tools."""
    return [tool for tool in mcp_tools if tool.name == DISCOVERY_TOOL_NAME]


def _load_categories_impl(
    categories: list[str],
    state: DynamicToolsState | None = None,
    exclude_destructive: bool = True,
) -> str:
    """Load multiple tool categories at once.

    Args:
        categories: List of category names to load
        state: Optional state container. Uses global state if not provided.
        exclude_destructive: If True (default), skip destructive tools (delete operations).
            Destructive tools can only be loaded via explicit load_tool call.

    Returns:
        Message indicating which tools were loaded or an error message.
    """
    if state is None:
        state = get_global_state()

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

    mcp_connection = get_mcp_connection()
    if mcp_connection is None:
        return "Error: MCP connection not available"

    loop = get_mcp_event_loop()
    if loop is None:
        return "Error: Event loop not available"

    # Collect all tool names to load
    tool_names_to_load: set[str] = set()
    for category in to_load:
        tool_names_to_load.update(catalog[category])

    # Exclude destructive tools if requested (e.g., during automatic pre-loading)
    if exclude_destructive:
        destructive_tools = get_destructive_tools()
        tool_names_to_load -= destructive_tools

    # Get all MCP tools and filter
    mcp_tools = asyncio.run_coroutine_threadsafe(mcp_connection.get_tools(), loop).result()
    tools_to_add = _filter_mcp_tools_by_names(mcp_tools, tool_names_to_load)

    if not tools_to_add:
        return f"No tools found for categories: {to_load}"

    # Convert to Anthropic format and add to dynamic tools
    anthropic_tools = mcp_tools_to_anthropic_format(tools_to_add)
    state.tools.extend(anthropic_tools)

    # Mark categories as loaded
    for category in to_load:
        state.loaded_categories.add(category)

    tool_names = [t.name for t in tools_to_add]
    logger.info(f"Loaded {len(tool_names)} tools from categories {to_load}: {tool_names}")

    return f"Loaded {len(tool_names)} tools from {to_load}: {', '.join(sorted(tool_names))}"


def preload_categories_for_request(request_text: str) -> str | None:
    """Pre-load tool categories based on keywords in the user's request.

    Called automatically on first user message to reduce tool discovery friction.
    Destructive tools (delete operations) are excluded - they can only be loaded
    via explicit load_tool call.

    Returns:
        Message about loaded categories, or None if nothing was loaded.
    """
    suggestions = suggest_categories_for_request(request_text)
    if not suggestions:
        return None

    result = _load_categories_impl(suggestions)
    if result.startswith("Error") or result.startswith("Categories already"):
        return None

    logger.info(f"Pre-loaded categories based on request keywords: {suggestions}")
    return result


def get_load_tool_category_definition() -> ToolParam:
    """Get the tool definition for load_tool_category."""
    return {
        "name": "load_tool_category",
        "description": (
            "Load MCP tools from one or more categories. Once loaded, the tools become "
            "available for use. Use list_tool_categories first to see available categories.\n"
            "Categories: annotations, queues, schemas, engines, hooks, email_templates, "
            "document_relations, relations, rules, users, workspaces"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Category names to load (e.g., ['queues', 'schemas'])",
                }
            },
            "required": ["categories"],
        },
    }


def load_tool_category(categories: list[str]) -> str:
    """Load MCP tools from specified categories."""
    return _load_categories_impl(categories)


def get_load_tool_definition() -> ToolParam:
    """Get the tool definition for load_tool."""
    return {
        "name": "load_tool",
        "description": (
            "Load specific MCP tools by name. Use this to load destructive tools "
            "(delete operations) which are excluded from load_tool_category. "
            "Example: load_tool(['delete_hook']) to enable hook deletion."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tool names to load (e.g., ['delete_hook', 'delete_queue'])",
                }
            },
            "required": ["tool_names"],
        },
    }


def load_tool(tool_names: list[str], state: DynamicToolsState | None = None) -> str:
    """Load specific MCP tools by name.

    Use this to load destructive tools (delete operations) that are excluded
    from category loading for safety.
    """
    if state is None:
        state = get_global_state()

    mcp_connection = get_mcp_connection()
    if mcp_connection is None:
        return "Error: MCP connection not available"

    loop = get_mcp_event_loop()
    if loop is None:
        return "Error: Event loop not available"

    # Get all MCP tools
    mcp_tools = asyncio.run_coroutine_threadsafe(mcp_connection.get_tools(), loop).result()
    available_tool_names = {t.name for t in mcp_tools}

    # Validate requested tool names
    invalid = [name for name in tool_names if name not in available_tool_names]
    if invalid:
        return f"Error: Unknown tools {invalid}"

    # Filter to already-loaded tools
    already_loaded = {t["name"] for t in state.tools}
    to_load = [name for name in tool_names if name not in already_loaded]

    if not to_load:
        return f"Tools already loaded: {tool_names}"

    # Filter MCP tools and convert to Anthropic format
    tools_to_add = _filter_mcp_tools_by_names(mcp_tools, set(to_load))
    anthropic_tools = mcp_tools_to_anthropic_format(tools_to_add)
    state.tools.extend(anthropic_tools)

    logger.info(f"Loaded {len(to_load)} tools by name: {to_load}")
    return f"Loaded tools: {', '.join(sorted(to_load))}"
