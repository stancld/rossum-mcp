"""Data models for the agent module.

This module contains the core data classes used throughout the agent system
for representing tool calls, results, and agent steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from anthropic.types import ThinkingBlockParam


class StepType(Enum):
    """Type of streaming step for distinguishing UI rendering."""

    THINKING = "thinking"
    INTERMEDIATE = "intermediate"
    FINAL_ANSWER = "final_answer"


if TYPE_CHECKING:
    from rossum_agent.tools import SubAgentProgress


@dataclass
class ToolCall:
    """Represents a single tool call made by the agent."""

    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {"id": self.id, "name": self.name, "arguments": self.arguments}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCall:
        """Deserialize from dictionary."""
        return cls(id=data["id"], name=data["name"], arguments=data.get("arguments", {}))


@dataclass
class ToolResult:
    """Represents the result of a tool call."""

    tool_call_id: str
    name: str
    content: str
    is_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "content": self.content,
            "is_error": self.is_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolResult:
        """Deserialize from dictionary."""
        return cls(
            tool_call_id=data["tool_call_id"],
            name=data["name"],
            content=data.get("content", ""),
            is_error=data.get("is_error", False),
        )


@dataclass
class StreamDelta:
    """A tagged delta from stream processing - either thinking or text."""

    kind: Literal["thinking", "text"]
    content: str


@dataclass
class ThinkingBlockData:
    """Represents a thinking block from extended thinking.

    Must be preserved and passed back to the API when continuing tool use conversations.
    """

    thinking: str
    signature: str

    def to_dict(self) -> ThinkingBlockParam:
        """Serialize to dictionary for storage and API message format."""
        return ThinkingBlockParam(type="thinking", thinking=self.thinking, signature=self.signature)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThinkingBlockData:
        """Deserialize from dictionary."""
        return cls(thinking=data["thinking"], signature=data["signature"])


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
    text_delta: str | None = None
    accumulated_text: str | None = None
    step_type: StepType | None = None

    def has_tool_calls(self) -> bool:
        """Check if this step contains tool calls."""
        return bool(self.tool_calls)


@dataclass
class AgentConfig:
    """Configuration for the RossumAgent."""

    max_output_tokens: int = 64000  # Opus 4.5 limit
    max_steps: int = 50
    temperature: float = 1.0  # Required for extended thinking
    request_delay: float = 3.0  # Delay in seconds between API calls to avoid rate limiting
    thinking_budget_tokens: int = 10000  # Budget for extended thinking (min 1024)

    def __post_init__(self) -> None:
        if self.temperature != 1.0:
            msg = "temperature must be 1.0 when extended thinking is enabled"
            raise ValueError(msg)
        if self.thinking_budget_tokens < 1024:
            msg = "thinking_budget_tokens must be at least 1024"
            raise ValueError(msg)


MAX_TOOL_OUTPUT_LENGTH = 20000


def truncate_content(content: str, max_length: int = MAX_TOOL_OUTPUT_LENGTH) -> str:
    """Truncate content preserving head and tail."""
    if len(content) <= max_length:
        return content
    half = max_length // 2
    return content[:half] + f"\n..._Content truncated to stay below {max_length} characters_...\n" + content[-half:]
