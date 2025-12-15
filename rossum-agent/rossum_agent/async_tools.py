"""Async tools for the Rossum Agent.

This module provides tools that require async execution, such as the Task tool
for spawning subagents.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_agent.agent.subagents.registry import get_subagent_registry
from rossum_agent.agent.subagents.runner import run_subagent
from rossum_agent.agent.subagents.types import SubagentType

if TYPE_CHECKING:
    from rossum_agent.agent.subagents.types import SubagentResult
    from rossum_agent.mcp_tools import MCPConnectionProtocol

logger = logging.getLogger(__name__)

TASK_TOOL_NAME = "delegate_task"


def get_task_tool_definition() -> dict[str, object]:
    """Get the Task tool definition in Anthropic format.

    Returns:
        Tool definition dict for the delegate_task tool.
    """
    registry = get_subagent_registry()
    subagent_descriptions = []
    for definition in registry.list_all():
        subagent_descriptions.append(f"- {definition.type.value}: {definition.description}")

    available_subagents = "\n".join(subagent_descriptions)

    return {
        "name": TASK_TOOL_NAME,
        "description": f"""Delegate a specialized task to a subagent. Use this when a task requires focused expertise.

Available subagent types:
{available_subagents}

The subagent will execute the task and return a summary of its findings.
Use this for complex analysis tasks that benefit from specialized focus.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "subagent_type": {
                    "type": "string",
                    "enum": [t.value for t in SubagentType],
                    "description": "The type of specialized subagent to use.",
                },
                "task": {
                    "type": "string",
                    "description": "A detailed description of the task for the subagent. "
                    "Include all relevant context such as IDs, specific questions, and expected output format.",
                },
            },
            "required": ["subagent_type", "task"],
        },
    }


async def execute_task_tool(mcp_connection: MCPConnectionProtocol, subagent_type: str, task: str) -> str:
    """Execute the Task tool by spawning a subagent.

    Args:
        mcp_connection: The MCP connection for tool access.
        subagent_type: The type of subagent to spawn.
        task: The task description for the subagent.

    Returns:
        A formatted string with the subagent's result.
    """
    logger.info(f"Delegating task to subagent: {subagent_type}")

    result: SubagentResult = await run_subagent(mcp_connection, subagent_type, task)

    if result.error:
        return f"Subagent failed: {result.error}"

    return _format_subagent_result(result)


def _format_subagent_result(result: SubagentResult) -> str:
    """Format a subagent result for display.

    Args:
        result: The SubagentResult to format.

    Returns:
        A formatted string representation.
    """
    output_parts = [
        f"## Subagent Report: {result.subagent_type.value}",
        "",
        f"**Task:** {result.task}",
        "",
        "### Result",
        result.result or "(No result)",
        "",
        "### Execution Summary",
        f"- Steps taken: {result.steps_taken}",
        f"- Tools used: {', '.join(result.tool_calls) if result.tool_calls else 'None'}",
        f"- Tokens: {result.input_tokens} input, {result.output_tokens} output",
    ]

    return "\n".join(output_parts)


def is_task_tool(name: str) -> bool:
    """Check if a tool name is the Task tool.

    Args:
        name: The tool name to check.

    Returns:
        True if this is the Task tool.
    """
    return name == TASK_TOOL_NAME


def get_async_tool_definitions() -> list[dict[str, object]]:
    """Get all async tool definitions.

    Returns:
        List of async tool definitions in Anthropic format.
    """
    return [get_task_tool_definition()]


def get_async_tool_names() -> set[str]:
    """Get the names of all async tools.

    Returns:
        Set of async tool names.
    """
    return {TASK_TOOL_NAME}
