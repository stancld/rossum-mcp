"""Subagent runner for executing specialized agents.

This module provides the functionality to run subagents with filtered tool access.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_agent.agent.subagents.factory import create_agent
from rossum_agent.agent.subagents.registry import get_subagent_registry
from rossum_agent.agent.subagents.types import SubagentResult, SubagentType
from rossum_agent.bedrock_client import create_bedrock_client

if TYPE_CHECKING:
    from rossum_agent.mcp_tools import MCPConnectionProtocol

logger = logging.getLogger(__name__)


class FilteredMCPConnection:
    """MCP connection wrapper that filters available tools.

    This wrapper restricts the tools available to a subagent to only those
    specified in its definition.
    """

    def __init__(self, mcp_connection: MCPConnectionProtocol, allowed_tools: list[str]) -> None:
        """Initialize the filtered connection.

        Args:
            mcp_connection: The underlying MCP connection.
            allowed_tools: List of tool names the subagent is allowed to use.
        """
        self._mcp_connection = mcp_connection
        self._allowed_tools = set(allowed_tools)
        self._filtered_tools_cache: list[object] | None = None

    async def get_tools(self) -> list[object]:
        """Get filtered list of tools available to the subagent."""
        if self._filtered_tools_cache is None:
            all_tools = await self._mcp_connection.get_tools()
            self._filtered_tools_cache = [t for t in all_tools if t.name in self._allowed_tools]
        return self._filtered_tools_cache

    async def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> object:
        """Call a tool if it's in the allowed list.

        Args:
            name: The tool name.
            arguments: The tool arguments.

        Returns:
            The tool result.

        Raises:
            ValueError: If the tool is not allowed for this subagent.
        """
        if name not in self._allowed_tools:
            raise ValueError(f"Tool '{name}' is not allowed for this subagent. Allowed: {self._allowed_tools}")
        return await self._mcp_connection.call_tool(name, arguments)


class SubagentRunner:
    """Runner for executing specialized subagents.

    Handles the creation and execution of subagents with their specific
    tool access and prompts.
    """

    def __init__(self, mcp_connection: MCPConnectionProtocol) -> None:
        """Initialize the subagent runner.

        Args:
            mcp_connection: The MCP connection for tool access.
        """
        self._mcp_connection = mcp_connection
        self._registry = get_subagent_registry()

    async def run(self, subagent_type: SubagentType | str, task: str) -> SubagentResult:
        """Run a subagent with the given task.

        Args:
            subagent_type: The type of subagent to run (enum or string).
            task: The task description for the subagent.

        Returns:
            SubagentResult with the execution outcome.
        """
        if isinstance(subagent_type, str):
            definition = self._registry.get_by_name(subagent_type)
            subagent_type = definition.type
        else:
            definition = self._registry.get(subagent_type)

        logger.info(f"Starting subagent {subagent_type.value} with task: {task[:100]}...")

        filtered_connection = FilteredMCPConnection(self._mcp_connection, definition.tools)

        client = create_bedrock_client()

        filtered_mcp_tools = await filtered_connection.get_tools()

        class SubagentMCPConnection:
            """Minimal MCP connection for subagent that provides pre-filtered tools."""

            def __init__(
                self,
                filtered_conn: FilteredMCPConnection,
                preloaded_tools: list[object],
            ) -> None:
                self._filtered_conn = filtered_conn
                self._preloaded_tools = preloaded_tools

            async def get_tools(self) -> list[object]:
                return self._preloaded_tools

            async def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> object:
                return await self._filtered_conn.call_tool(name, arguments)

        subagent_mcp = SubagentMCPConnection(filtered_connection, filtered_mcp_tools)

        agent = create_agent(
            client=client,
            mcp_connection=subagent_mcp,
            system_prompt=definition.system_prompt,
            max_steps=definition.max_steps,
        )

        tool_calls_made: list[str] = []
        final_answer: str | None = None
        error: str | None = None
        steps_taken = 0
        total_input_tokens = 0
        total_output_tokens = 0

        try:
            async for step in agent.run(task):
                if not step.is_streaming:
                    steps_taken = step.step_number
                    total_input_tokens = agent._total_input_tokens
                    total_output_tokens = agent._total_output_tokens

                    for tc in step.tool_calls:
                        tool_calls_made.append(tc.name)

                    if step.is_final:
                        if step.error:
                            error = step.error
                        else:
                            final_answer = step.final_answer

        except Exception as e:
            logger.error(f"Subagent {subagent_type.value} failed: {e}", exc_info=True)
            error = str(e)

        result = SubagentResult(
            subagent_type=subagent_type,
            task=task,
            result=final_answer,
            steps_taken=steps_taken,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            error=error,
            tool_calls=tool_calls_made,
        )

        logger.info(
            f"Subagent {subagent_type.value} completed: "
            f"steps={steps_taken}, success={result.success}, tools_used={len(tool_calls_made)}"
        )

        return result


async def run_subagent(
    mcp_connection: MCPConnectionProtocol, subagent_type: SubagentType | str, task: str
) -> SubagentResult:
    """Convenience function to run a subagent.

    Args:
        mcp_connection: The MCP connection for tool access.
        subagent_type: The type of subagent to run.
        task: The task description.

    Returns:
        SubagentResult with the execution outcome.
    """
    runner = SubagentRunner(mcp_connection)
    return await runner.run(subagent_type, task)
