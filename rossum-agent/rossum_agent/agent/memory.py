"""Memory management for the agent.

This module implements the memory storage system following the smolagents pattern:
- Store structured MemoryStep objects (not raw messages)
- Rebuild messages fresh each call via write_to_messages()
- Apply summary_mode for old steps to reduce token usage
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, cast

from anthropic.types import MessageParam, TextBlockParam, ThinkingBlockParam, ToolResultBlockParam, ToolUseBlockParam

from rossum_agent.agent.models import ThinkingBlockData, ToolCall, ToolResult

if TYPE_CHECKING:
    from rossum_agent.agent.types import UserContent


@dataclass
class MemoryStep:
    """A single step stored in agent memory."""

    step_number: int
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    thinking_blocks: list[ThinkingBlockData] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    def to_messages(self) -> list[MessageParam]:
        """Convert this step to Anthropic message format."""
        messages: list[MessageParam] = []

        if self.tool_calls:
            assistant_content: list[TextBlockParam | ToolUseBlockParam | ThinkingBlockParam] = [
                tb.to_dict() for tb in self.thinking_blocks
            ]

            if self.text:
                assistant_content.append(TextBlockParam(type="text", text=self.text))

            assistant_content.extend(
                ToolUseBlockParam(type="tool_use", id=tc.id, name=tc.name, input=tc.arguments)
                for tc in self.tool_calls
            )

            messages.append(MessageParam(role="assistant", content=assistant_content))

            if self.tool_results:
                tool_result_blocks = [
                    ToolResultBlockParam(
                        type="tool_result",
                        tool_use_id=tr.tool_call_id,
                        content=tr.content,
                        is_error=tr.is_error,
                    )
                    for tr in self.tool_results
                ]
                messages.append(MessageParam(role="user", content=tool_result_blocks))

        elif self.text:
            messages.append(MessageParam(role="assistant", content=self.text))

        return messages

    def to_dict(self) -> dict[str, Any]:
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
        return cls(
            step_number=data.get("step_number", 0),
            text=data.get("text"),
            tool_calls=[ToolCall.from_dict(tc) for tc in data.get("tool_calls", [])],
            tool_results=[ToolResult.from_dict(tr) for tr in data.get("tool_results", [])],
            thinking_blocks=[ThinkingBlockData.from_dict(tb) for tb in data.get("thinking_blocks", [])],
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
        )


_PRELOAD_PATTERN = re.compile(
    r"\n\n\[System: (Loaded .+?)\. Use these tools directly without calling list_tool_categories first\.\]$"
)


@dataclass
class TaskStep:
    """Represents the user prompt."""

    task: UserContent
    preload_info: str | None = None

    def to_messages(self) -> list[MessageParam]:
        content = self.task
        if self.preload_info:
            suffix = f"\n\n[System: {self.preload_info}. Use these tools directly without calling list_tool_categories first.]"
            if isinstance(content, str):
                content = content + suffix
            else:
                content = [*content, TextBlockParam(type="text", text=suffix)]
        return [MessageParam(role="user", content=content)]

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": "task_step", "task": self.task}
        if self.preload_info:
            d["preload_info"] = self.preload_info
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskStep:
        task = data["task"]
        # Backward compat: extract preload info baked into old-format tasks
        if (preload_info := data.get("preload_info")) is None:
            task, preload_info = cls._extract_legacy_preload_info(task)
        return cls(task=task, preload_info=preload_info)

    @staticmethod
    def _extract_legacy_preload_info(task: UserContent) -> tuple[UserContent, str | None]:
        if isinstance(task, str):
            if m := _PRELOAD_PATTERN.search(task):
                return task[: m.start()], m.group(1)
        elif isinstance(task, list) and task:
            last = task[-1]
            if isinstance(last, dict) and last.get("type") == "text":
                text = last.get("text", "")
                if m := _PRELOAD_PATTERN.search(text):
                    cleaned_text = text[: m.start()]
                    if cleaned_text:
                        cleaned_block = TextBlockParam(type="text", text=cleaned_text)
                        return [*task[:-1], cleaned_block], m.group(1)
                    return task[:-1] if len(task) > 1 else task, m.group(1)
        return task, None


@dataclass
class AgentMemory:
    """Memory storage for agent steps."""

    COLLAPSIBLE_TOOLS: ClassVar[frozenset[str]] = frozenset({"patch_schema"})

    steps: list[TaskStep | MemoryStep] = field(default_factory=list)

    def reset(self) -> None:
        """Clear all steps."""
        self.steps = []

    def add_task(self, task: UserContent, preload_info: str | None = None) -> None:
        """Add initial user task (text or multimodal content)."""
        self.steps.append(TaskStep(task=task, preload_info=preload_info))

    def add_step(self, step: MemoryStep) -> None:
        """Add a completed agent step."""
        self.steps.append(step)

    def write_to_messages(self) -> list[MessageParam]:
        """Convert all steps to messages.

        Collapses intermediate results of repeated collapsible tools
        to reduce context size — only the last result is kept in full.
        """
        messages = [msg for step in self.steps for msg in step.to_messages()]
        return self._collapse_tool_results(messages)

    def _collapse_tool_results(self, messages: list[MessageParam]) -> list[MessageParam]:
        """Replace earlier tool_result contents for collapsible tools with a short summary.

        Scans messages to find the last occurrence of each collapsible tool,
        then replaces all earlier occurrences' content strings.
        """
        tool_use_id_to_name = self._build_collapsible_tool_map(messages)
        if not tool_use_id_to_name:
            return messages

        positions = self._find_collapsible_positions(messages, tool_use_id_to_name)
        if len(positions) <= 1:
            return messages

        self._replace_earlier_results(messages, positions)
        return messages

    def _build_collapsible_tool_map(self, messages: list[MessageParam]) -> dict[str, str]:
        """Map tool_use_id -> tool_name for collapsible tools found in assistant messages."""
        mapping: dict[str, str] = {}
        for msg in messages:
            if msg["role"] != "assistant":
                continue
            content = msg["content"]
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name", "")
                    if name in self.COLLAPSIBLE_TOOLS:
                        mapping[cast("ToolUseBlockParam", block)["id"]] = name
        return mapping

    @staticmethod
    def _find_collapsible_positions(
        messages: list[MessageParam], tool_use_id_to_name: dict[str, str]
    ) -> list[tuple[int, int, str]]:
        """Find (msg_idx, block_idx, tool_name) for each collapsible tool_result block."""
        positions: list[tuple[int, int, str]] = []
        for msg_idx, msg in enumerate(messages):
            if msg["role"] != "user":
                continue
            content = msg["content"]
            if not isinstance(content, list):
                continue
            for block_idx, block in enumerate(content):
                if not isinstance(block, dict):
                    continue
                block_dict: dict[str, object] = block  # ty:ignore[invalid-assignment]
                if block_dict.get("type") == "tool_result":
                    tool_use_id = str(block_dict.get("tool_use_id", ""))
                    tool_name = tool_use_id_to_name.get(tool_use_id)
                    if tool_name:
                        positions.append((msg_idx, block_idx, tool_name))
        return positions

    @staticmethod
    def _replace_earlier_results(messages: list[MessageParam], positions: list[tuple[int, int, str]]) -> None:
        """Collapse all but the last result per tool name."""
        last_per_tool: dict[str, int] = {}
        for idx, (_, _, tool_name) in enumerate(positions):
            last_per_tool[tool_name] = idx
        last_indices = set(last_per_tool.values())

        for pos_idx, (msg_idx, block_idx, tool_name) in enumerate(positions):
            if pos_idx not in last_indices:
                content = messages[msg_idx]["content"]
                cast("list", content)[block_idx]["content"] = (
                    f"[Result collapsed — superseded by later {tool_name} call]"
                )

    def to_dict(self) -> list[dict[str, Any]]:
        return [step.to_dict() for step in self.steps]

    @classmethod
    def from_dict(cls, data: list[dict[str, Any]]) -> AgentMemory:
        memory = cls()
        for step_data in data:
            step_type = step_data.get("type")
            if step_type == "task_step":
                memory.steps.append(TaskStep.from_dict(step_data))
            elif step_type == "memory_step":
                memory.steps.append(MemoryStep.from_dict(step_data))
        return memory
