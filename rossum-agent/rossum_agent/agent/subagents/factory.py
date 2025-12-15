"""Factory module for creating agent instances in subagents.

This module provides factory functions to break circular import dependencies
between the subagent runner and the core agent module.

The factory pattern is used here to allow registration of the agent class
at runtime, avoiding import-time circular dependencies.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anthropic import AnthropicBedrock

    from rossum_agent.agent.core import RossumAgent
    from rossum_agent.mcp_tools import MCPConnectionProtocol

AgentFactory = Callable[
    ["AnthropicBedrock", "MCPConnectionProtocol", str, int],
    "RossumAgent",
]

_agent_factory: AgentFactory | None = None


def register_agent_factory(factory: AgentFactory) -> None:
    """Register the agent factory function.

    This should be called by core.py at import time to register itself.

    Args:
        factory: A callable that creates RossumAgent instances.
    """
    global _agent_factory
    _agent_factory = factory


def create_agent(
    client: AnthropicBedrock,
    mcp_connection: MCPConnectionProtocol,
    system_prompt: str,
    max_steps: int,
) -> RossumAgent:
    """Create a RossumAgent instance using the registered factory.

    Args:
        client: The Bedrock client.
        mcp_connection: The MCP connection for tool access.
        system_prompt: The system prompt for the agent.
        max_steps: Maximum steps for the agent.

    Returns:
        A configured RossumAgent instance.

    Raises:
        RuntimeError: If no agent factory has been registered.
    """
    if _agent_factory is None:
        raise RuntimeError("Agent factory not registered. Ensure core.py is imported before using subagents.")
    return _agent_factory(client, mcp_connection, system_prompt, max_steps)
