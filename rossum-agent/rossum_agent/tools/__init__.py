"""Tools for the Rossum Agent.

This package provides local tools executed directly by the agent (file operations, debugging, skills, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_agent.tools.ask_user import (
    ask_user_question,
    get_ask_user_question_definition,
)
from rossum_agent.tools.change_history import (
    diff_objects,
    restore_entity_version,
    revert_commit,
    show_change_history,
    show_commit_details,
    show_entity_history,
)
from rossum_agent.tools.core import get_context
from rossum_agent.tools.data_tools import run_grep, run_jq
from rossum_agent.tools.dynamic_tools import (
    get_load_tool_definition,
    load_tool,
)
from rossum_agent.tools.file_tools import write_file
from rossum_agent.tools.mock_pdf import generate_mock_pdf
from rossum_agent.tools.python_exec import execute_python, get_execute_python_definition
from rossum_agent.tools.skills import load_skill
from rossum_agent.tools.subagents import patch_schema_with_subagent, search_elis_docs, search_knowledge_base
from rossum_agent.tools.task_tracker import create_task, list_tasks, update_task

if TYPE_CHECKING:
    from anthropic._tools import BetaTool  # ty: ignore[unresolved-import] - private API
    from anthropic.types import ToolParam

# Internal tools that perform write operations against the Rossum API
INTERNAL_WRITE_TOOL_NAMES: set[str] = {"revert_commit", "restore_entity_version", "patch_schema_with_subagent"}

_ALWAYS_INTERNAL_TOOLS: list[BetaTool[..., str]] = [
    write_file,
    diff_objects,
    search_knowledge_base,
    search_elis_docs,
    patch_schema_with_subagent,
    load_skill,
    create_task,
    update_task,
    list_tasks,
    run_jq,
    run_grep,
    generate_mock_pdf,
    execute_python,
]

_CHANGE_HISTORY_TOOLS: list[BetaTool[..., str]] = [
    show_change_history,
    show_commit_details,
    show_entity_history,
    revert_commit,
    restore_entity_version,
]

_INTERNAL_TOOL_REGISTRY: dict[str, BetaTool[..., str]] = {
    t.name: t for t in (_ALWAYS_INTERNAL_TOOLS + _CHANGE_HISTORY_TOOLS)
}


def _get_active_internal_tools() -> list[BetaTool[..., str]]:
    """Get internal tools based on loaded skills and mode."""
    ctx = get_context()
    tools = _ALWAYS_INTERNAL_TOOLS
    if ctx.commit_store is not None:
        tools = tools + _CHANGE_HISTORY_TOOLS
    if ctx.is_read_only:
        tools = [t for t in tools if t.name not in INTERNAL_WRITE_TOOL_NAMES]
    return tools


def get_internal_tools() -> list[ToolParam]:
    """Get internal tools in Anthropic format (deployment tools only when skill is loaded)."""
    visible_tools: list[ToolParam] = []
    for tool in _get_active_internal_tools():
        if tool.name == "execute_python":
            visible_tools.append(get_execute_python_definition())
        else:
            visible_tools.append(tool.to_dict())
    return [
        *visible_tools,
        get_load_tool_definition(),
        get_ask_user_question_definition(),
    ]


def get_internal_tool_names() -> set[str]:
    """Get names of all executable internal tools (always includes all for dispatch)."""
    return set(_INTERNAL_TOOL_REGISTRY.keys()) | {
        "load_tool",
        "ask_user_question",
    }


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
    if name == "load_tool":
        raw_tool_names = arguments.get("tool_names", [])
        tool_names = [str(t) for t in raw_tool_names] if isinstance(raw_tool_names, list) else [str(raw_tool_names)]
        return load_tool(tool_names)

    if name == "ask_user_question":
        q = arguments.get("question")
        return ask_user_question(
            question=str(q) if q is not None else None,
            options=arguments.get("options"),  # type: ignore[arg-type]
            multi_select=bool(arguments.get("multi_select", False)),
            questions=arguments.get("questions"),  # type: ignore[arg-type]
        )

    if tool := _INTERNAL_TOOL_REGISTRY.get(name):
        return tool(**arguments)

    raise ValueError(f"Unknown internal tool: {name}")


def execute_tool(name: str, arguments: dict[str, object], tools: list[BetaTool[..., str]]) -> str:
    """Execute a tool by name from the given tool set."""
    for tool in tools:
        if tool.name == name:
            return tool(**arguments)
    raise ValueError(f"Unknown tool: {name}")


INTERNAL_TOOLS = _ALWAYS_INTERNAL_TOOLS + _CHANGE_HISTORY_TOOLS

__all__ = [
    "INTERNAL_TOOLS",
    "execute_internal_tool",
    "execute_tool",
    "get_context",
    "get_internal_tool_names",
    "get_internal_tools",
]
