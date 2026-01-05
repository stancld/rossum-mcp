"""Memory management for the agent.

This module implements the memory storage system following the smolagents pattern:
- Store structured MemoryStep objects (not raw messages)
- Rebuild messages fresh each call via write_to_messages()
- Apply summary_mode for old steps to reduce token usage
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from rossum_agent.agent.models import ThinkingBlockData, ToolCall, ToolResult

if TYPE_CHECKING:
    from anthropic.types import MessageParam

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
    thinking_blocks: list[ThinkingBlockData] = field(default_factory=list)
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

            for tb in self.thinking_blocks:
                assistant_content.append(tb.to_dict())

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

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "type": "memory_step",
            "step_number": self.step_number,
            "text": self.text,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "tool_results": [tr.to_dict() for tr in self.tool_results],
            "thinking_blocks": [tb.to_dict() for tb in self.thinking_blocks],
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryStep:
        """Deserialize from dictionary."""
        return cls(
            step_number=data.get("step_number", 0),
            text=data.get("text"),
            tool_calls=[ToolCall.from_dict(tc) for tc in data.get("tool_calls", [])],
            tool_results=[ToolResult.from_dict(tr) for tr in data.get("tool_results", [])],
            thinking_blocks=[ThinkingBlockData.from_dict(tb) for tb in data.get("thinking_blocks", [])],
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
        )


@dataclass
class TaskStep:
    """Represents the initial user task/prompt.

    Supports both text-only and multimodal content (with images).
    """

    task: UserContent

    def to_messages(self) -> list[MessageParam]:
        return [{"role": "user", "content": self.task}]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {"type": "task_step", "task": self.task}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskStep:
        """Deserialize from dictionary."""
        return cls(task=data["task"])


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

    def to_dict(self) -> list[dict[str, Any]]:
        """Serialize all steps to a list of dictionaries for storage."""
        return [step.to_dict() for step in self.steps]

    @classmethod
    def from_dict(cls, data: list[dict[str, Any]]) -> AgentMemory:
        """Deserialize from a list of step dictionaries."""
        memory = cls()
        for step_data in data:
            step_type = step_data.get("type")
            if step_type == "task_step":
                memory.steps.append(TaskStep.from_dict(step_data))
            elif step_type == "memory_step":
                memory.steps.append(MemoryStep.from_dict(step_data))
        return memory
