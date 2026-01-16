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

INTERNAL_TOOLS: list[BetaTool[..., str]] = [
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
    return [tool.to_dict() for tool in INTERNAL_TOOLS]


def get_internal_tool_names() -> set[str]:
    """Get the names of all internal tools."""
    return {tool.name for tool in INTERNAL_TOOLS}


def execute_tool(name: str, arguments: dict[str, object], tools: list[BetaTool[..., str]]) -> str:
    """Execute a tool by name from the given tool set.

    Args:
        name: The name of the tool to execute.
        arguments: The arguments to pass to the tool.
        tools: The list of tools to search in.

    Returns:
        The result of the tool execution as a string.

    Raises:
        ValueError: If the tool name is not recognized.
    """
    for tool in tools:
        if tool.name == name:
            result: str = tool(**arguments)
            return result

    raise ValueError(f"Unknown tool: {name}")


__all__ = [
    "DEPLOY_TOOLS",
    "INTERNAL_TOOLS",
    "OPUS_MODEL_ID",
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
    "execute_tool",
    "get_deploy_tool_names",
    "get_deploy_tools",
    "get_internal_tool_names",
    "get_internal_tools",
    "get_mcp_connection",
    "get_mcp_event_loop",
    "get_output_dir",
    "get_workspace_credentials",
    "load_skill",
    "patch_schema_with_subagent",
    "report_progress",
    "report_text",
    "report_token_usage",
    "search_knowledge_base",
    "set_mcp_connection",
    "set_output_dir",
    "set_progress_callback",
    "set_text_callback",
    "set_token_callback",
    "spawn_mcp_connection",
    "suggest_formula_field",
    "write_file",
]
