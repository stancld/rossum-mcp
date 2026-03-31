from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from anthropic.types import ThinkingBlockParam


class StepType(Enum):
    """Type of streaming text step for distinguishing intermediate vs final answer."""

    INTERMEDIATE = "intermediate"
    FINAL_ANSWER = "final_answer"


if TYPE_CHECKING:
    from rossum_agent.tools.core import SubAgentProgress


@dataclass
class ToolCall:
    """Represents a single tool call made by the agent."""

    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCall:
        return cls(id=data["id"], name=data["name"], arguments=data.get("arguments", {}))


@dataclass
class ToolResult:
    """Represents the result of a tool call."""

    tool_call_id: str
    name: str
    content: str
    is_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "content": self.content,
            "is_error": self.is_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolResult:
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
        return ThinkingBlockParam(type="thinking", thinking=self.thinking, signature=self.signature)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThinkingBlockData:
        return cls(thinking=data["thinking"], signature=data["signature"])


# --- AgentStep discriminated union variants ---


@dataclass
class ThinkingStep:
    """Streaming thinking/chain-of-thought tokens."""

    step_number: int
    thinking: str
    is_streaming: bool = True


@dataclass
class TextDeltaStep:
    """Streaming text delta (intermediate response or final answer being streamed)."""

    step_number: int
    step_type: StepType
    text_delta: str
    accumulated_text: str
    thinking: str | None = None
    is_streaming: bool = True


@dataclass
class ToolStartStep:
    """Tool execution starting or in progress."""

    step_number: int
    tool_calls: list[ToolCall]
    tool_progress: tuple[int, int]
    current_tool: str | None = None
    current_tool_call_id: str | None = None
    sub_agent_progress: SubAgentProgress | None = None
    is_streaming: bool = True


@dataclass
class ToolResultStep:
    """Completed tool execution with results."""

    step_number: int
    tool_calls: list[ToolCall]
    tool_results: list[ToolResult]
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class FinalAnswerStep:
    """Final answer from the agent (no more tool calls)."""

    step_number: int
    final_answer: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ErrorStep:
    """Agent execution error."""

    step_number: int
    error: str


AgentStep = ThinkingStep | TextDeltaStep | ToolStartStep | ToolResultStep | FinalAnswerStep | ErrorStep


@dataclass
class AgentConfig:
    """Configuration for the RossumAgent."""

    max_output_tokens: int = 128000  # Opus 4.6 limit
    max_steps: int = 50
    temperature: float = 1.0  # Required for extended thinking
    request_delay: float = 3.0  # Delay in seconds between API calls to avoid rate limiting
    effort: Literal["max", "high", "medium", "low"] = "high"

    def __post_init__(self) -> None:
        if self.temperature != 1.0:
            msg = "temperature must be 1.0 when extended thinking is enabled"
            raise ValueError(msg)


MAX_TOOL_OUTPUT_LENGTH = 30000


def truncate_content(content: str, max_length: int = MAX_TOOL_OUTPUT_LENGTH) -> str:
    """Truncate content preserving head and tail."""
    if len(content) <= max_length:
        return content
    half = max_length // 2
    return content[:half] + f"\n..._Content truncated to stay below {max_length} characters_...\n" + content[-half:]
