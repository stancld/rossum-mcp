"""Data models for the agent module.

This module contains the core data classes used throughout the agent system
for representing tool calls, results, and agent steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rossum_agent.internal_tools import SubAgentProgress


@dataclass
class ToolCall:
    """Represents a single tool call made by the agent."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Represents the result of a tool call."""

    tool_call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass
class AgentStep:
    """Represents a single step in the agent's execution (for yielding to caller).

    This is the public-facing step object yielded during agent.run().
    Different from MemoryStep which is for internal storage.
    """

    step_number: int
    thinking: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    final_answer: str | None = None
    is_final: bool = False
    error: str | None = None
    is_streaming: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    current_tool: str | None = None
    tool_progress: tuple[int, int] | None = None
    sub_agent_progress: SubAgentProgress | None = None

    def has_tool_calls(self) -> bool:
        """Check if this step contains tool calls."""
        return len(self.tool_calls) > 0


@dataclass
class AgentConfig:
    """Configuration for the RossumAgent."""

    max_tokens: int = 128000
    max_steps: int = 50
    temperature: float = 0.0


MAX_TOOL_OUTPUT_LENGTH = 20000


def truncate_content(content: str, max_length: int = MAX_TOOL_OUTPUT_LENGTH) -> str:
    """Truncate content preserving head and tail."""
    if len(content) <= max_length:
        return content
    half = max_length // 2
    return content[:half] + f"\n..._Content truncated to stay below {max_length} characters_...\n" + content[-half:]
