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
    get_mcp_connection,
    get_mcp_event_loop,
    get_output_dir,
    report_progress,
    report_text,
    set_mcp_connection,
    set_output_dir,
    set_progress_callback,
    set_text_callback,
)
from rossum_agent.tools.deploy import (
    DEPLOY_TOOLS,
    create_workspace,
    deploy_compare_workspaces,
    deploy_copy_org,
    deploy_copy_workspace,
    deploy_diff,
    deploy_pull,
    deploy_pull_workspace,
    deploy_push,
    deploy_to_org,
    get_deploy_tool_names,
    get_deploy_tools,
    get_workspace_credentials,
)
from rossum_agent.tools.file_tools import write_file
from rossum_agent.tools.hook_debug import debug_hook, evaluate_python_hook
from rossum_agent.tools.knowledge_base import OPUS_MODEL_ID, WebSearchError, search_knowledge_base
from rossum_agent.tools.skills import load_skill
from rossum_agent.tools.spawn_mcp import (
    SpawnedConnection,
    call_on_connection,
    cleanup_all_spawned_connections,
    clear_spawned_connections,
    close_connection,
    spawn_mcp_connection,
)

if TYPE_CHECKING:
    from anthropic._tools import BetaTool

INTERNAL_TOOLS: list[BetaTool[..., str]] = [
    write_file,
    search_knowledge_base,
    evaluate_python_hook,
    debug_hook,
    load_skill,
    spawn_mcp_connection,
    call_on_connection,
    close_connection,
]


def get_internal_tools() -> list[dict[str, object]]:
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
    "deploy_pull_workspace",
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
    "report_progress",
    "report_text",
    "search_knowledge_base",
    "set_mcp_connection",
    "set_output_dir",
    "set_progress_callback",
    "set_text_callback",
    "spawn_mcp_connection",
    "write_file",
]
