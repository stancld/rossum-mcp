from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rossum_agent.agent.models.tool_types import ToolCall, ToolResult


class StepType(Enum):
    """Type of streaming text step for distinguishing intermediate vs final answer."""

    INTERMEDIATE = "intermediate"
    FINAL_ANSWER = "final_answer"


@dataclass
class ReasoningStep:
    """Streaming reasoning/chain-of-thought tokens."""

    step_number: int
    reasoning: str
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
    is_hook_output: bool = False


@dataclass
class ErrorStep:
    """Agent execution error."""

    step_number: int
    error: str


AgentStep = ReasoningStep | TextDeltaStep | ToolStartStep | ToolResultStep | FinalAnswerStep | ErrorStep
