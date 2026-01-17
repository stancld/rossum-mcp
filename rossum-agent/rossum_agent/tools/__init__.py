"""Tools for the Rossum Agent.

This package provides local tools executed directly by the agent (file operations, debugging, skills, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_agent.tools.core import (
    SubAgentProgress,
    SubAgentProgressCallback,
    SubAgentText,
    SubAgentTextCallback,
    SubAgentTokenCallback,
    SubAgentTokenUsage,
    get_mcp_connection,
    get_mcp_event_loop,
    get_output_dir,
    report_progress,
    report_text,
    report_token_usage,
    set_mcp_connection,
    set_output_dir,
    set_progress_callback,
    set_text_callback,
    set_token_callback,
)
from rossum_agent.tools.deploy import (
    DEPLOY_TOOLS,
    create_workspace,
    deploy_compare_workspaces,
    deploy_copy_org,
    deploy_copy_workspace,
    deploy_diff,
    deploy_pull,
    deploy_push,
    deploy_to_org,
    get_deploy_tool_names,
    get_deploy_tools,
    get_workspace_credentials,
)
from rossum_agent.tools.dynamic_tools import (
    DISCOVERY_TOOL_NAME,
    DynamicToolsState,
    get_dynamic_tools,
    get_load_tool_category_definition,
    get_loaded_categories,
    load_tool_category,
    preload_categories_for_request,
    reset_dynamic_tools,
    suggest_categories_for_request,
)
from rossum_agent.tools.file_tools import write_file
from rossum_agent.tools.formula import suggest_formula_field
from rossum_agent.tools.skills import load_skill
from rossum_agent.tools.spawn_mcp import (
    SpawnedConnection,
    call_on_connection,
    cleanup_all_spawned_connections,
    clear_spawned_connections,
    close_connection,
    spawn_mcp_connection,
)
from rossum_agent.tools.subagents import (
    OPUS_MODEL_ID,
    WebSearchError,
    debug_hook,
    evaluate_python_hook,
    patch_schema_with_subagent,
    search_knowledge_base,
)

if TYPE_CHECKING:
    from anthropic._tools import BetaTool  # ty: ignore[unresolved-import] - private API
    from anthropic.types import ToolParam

# Tools using @beta_tool decorator
_BETA_TOOLS: list[BetaTool[..., str]] = [
    write_file,
    search_knowledge_base,
    evaluate_python_hook,
    debug_hook,
    patch_schema_with_subagent,
    suggest_formula_field,
    load_skill,
    spawn_mcp_connection,
    call_on_connection,
    close_connection,
]


def get_internal_tools() -> list[ToolParam]:
    """Get all internal tools in Anthropic format."""
    return [tool.to_dict() for tool in _BETA_TOOLS] + [get_load_tool_category_definition()]


def get_internal_tool_names() -> set[str]:
    """Get the names of all internal tools."""
    return {tool.name for tool in _BETA_TOOLS} | {"load_tool_category"}


def execute_internal_tool(name: str, arguments: dict[str, object]) -> str:
    """Execute an internal tool by name.

    Args:
        name: The name of the tool to execute.
        arguments: The arguments to pass to the tool.

    Returns:
        The result of the tool execution as a string.

    Raises:
        ValueError: If the tool name is not recognized.
    """
    if name == "load_tool_category":
        raw_categories = arguments.get("categories", [])
        categories = [str(c) for c in raw_categories] if isinstance(raw_categories, list) else [str(raw_categories)]
        return load_tool_category(categories)

    for tool in _BETA_TOOLS:
        if tool.name == name:
            result: str = tool(**arguments)
            return result

    raise ValueError(f"Unknown internal tool: {name}")


# Legacy alias for backwards compatibility
def execute_tool(name: str, arguments: dict[str, object], tools: list[BetaTool[..., str]]) -> str:
    """Execute a tool by name from the given tool set (legacy API)."""
    for tool in tools:
        if tool.name == name:
            result: str = tool(**arguments)
            return result
    raise ValueError(f"Unknown tool: {name}")


# Legacy export for deploy tools execution
INTERNAL_TOOLS = _BETA_TOOLS

__all__ = [
    "DEPLOY_TOOLS",
    "DISCOVERY_TOOL_NAME",
    "INTERNAL_TOOLS",
    "OPUS_MODEL_ID",
    "DynamicToolsState",
    "SpawnedConnection",
    "SubAgentProgress",
    "SubAgentProgressCallback",
    "SubAgentText",
    "SubAgentTextCallback",
    "SubAgentTokenCallback",
    "SubAgentTokenUsage",
    "WebSearchError",
    "call_on_connection",
    "cleanup_all_spawned_connections",
    "clear_spawned_connections",
    "close_connection",
    "create_workspace",
    "debug_hook",
    "deploy_compare_workspaces",
    "deploy_copy_org",
    "deploy_copy_workspace",
    "deploy_diff",
    "deploy_pull",
    "deploy_push",
    "deploy_to_org",
    "evaluate_python_hook",
    "execute_internal_tool",
    "execute_tool",
    "get_deploy_tool_names",
    "get_deploy_tools",
    "get_dynamic_tools",
    "get_internal_tool_names",
    "get_internal_tools",
    "get_load_tool_category_definition",
    "get_loaded_categories",
    "get_mcp_connection",
    "get_mcp_event_loop",
    "get_output_dir",
    "get_workspace_credentials",
    "load_skill",
    "load_tool_category",
    "patch_schema_with_subagent",
    "preload_categories_for_request",
    "report_progress",
    "report_text",
    "report_token_usage",
    "reset_dynamic_tools",
    "search_knowledge_base",
    "set_mcp_connection",
    "set_output_dir",
    "set_progress_callback",
    "set_text_callback",
    "set_token_callback",
    "spawn_mcp_connection",
    "suggest_categories_for_request",
    "suggest_formula_field",
    "write_file",
]
