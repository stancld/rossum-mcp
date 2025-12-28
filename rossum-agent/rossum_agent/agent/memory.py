"""Memory management for the agent.

This module implements the memory storage system following the smolagents pattern:
- Store structured MemoryStep objects (not raw messages)
- Rebuild messages fresh each call via write_to_messages()
- Apply summary_mode for old steps to reduce token usage
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anthropic.types import MessageParam

    from rossum_agent.agent.models import ToolCall, ToolResult
    from rossum_agent.agent.types import UserContent


@dataclass
class MemoryStep:
    """A single step stored in agent memory.

    This is the structured storage format. Steps are converted to messages
    on-the-fly via to_messages(), allowing summary_mode to compress old steps.

    Attributes:
        text: Model's text output (reasoning before tool calls, or final answer).
    """

    step_number: int
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    def to_messages(self) -> list[MessageParam]:
        """Convert this step to Anthropic message format.

        For tool-use steps: Includes text block followed by tool_use blocks.
        For final answer steps: Includes text as assistant content.

        Returns:
            List of message dicts for the Anthropic API.
        """
        messages: list[MessageParam] = []

        if self.tool_calls:
            assistant_content: list[dict[str, object]] = []

            if self.text:
                assistant_content.append({"type": "text", "text": self.text})

            for tc in self.tool_calls:
                assistant_content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})

            messages.append({"role": "assistant", "content": assistant_content})

            if self.tool_results:
                tool_result_blocks: list[dict[str, object]] = []
                for tr in self.tool_results:
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tr.tool_call_id,
                            "content": tr.content,
                            "is_error": tr.is_error,
                        }
                    )

                messages.append({"role": "user", "content": tool_result_blocks})

        elif self.text:
            messages.append({"role": "assistant", "content": self.text})

        return messages


@dataclass
class TaskStep:
    """Represents the initial user task/prompt.

    Supports both text-only and multimodal content (with images).
    """

    task: UserContent

    def to_messages(self) -> list[MessageParam]:
        return [{"role": "user", "content": self.task}]


@dataclass
class AgentMemory:
    """Memory storage for agent steps.

    Stores structured step objects and rebuilds messages on demand.
    """

    steps: list[TaskStep | MemoryStep] = field(default_factory=list)

    def reset(self) -> None:
        """Clear all steps."""
        self.steps = []

    def add_task(self, task: UserContent) -> None:
        """Add initial user task (text or multimodal content)."""
        self.steps.append(TaskStep(task=task))

    def add_step(self, step: MemoryStep) -> None:
        """Add a completed agent step."""
        self.steps.append(step)

    def write_to_messages(self) -> list[MessageParam]:
        """Convert all steps to messages.

        Returns:
            List of message dicts ready for Anthropic API.
        """
        messages: list[MessageParam] = []

        for step in self.steps:
            step_messages = step.to_messages()
            messages.extend(step_messages)

        return messages
