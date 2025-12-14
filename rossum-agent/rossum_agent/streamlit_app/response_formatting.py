"""Response formatting module for the Rossum Agent Streamlit application.

This module handles the formatting and display of agent responses,
including tool calls, tool results, and final answers.
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import json
import pathlib
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

    from rossum_agent.agent import AgentStep


class OutputRenderer(Protocol):
    def markdown(self, body: str, *, unsafe_allow_html: bool = False) -> None: ...


def parse_and_format_final_answer(answer: str) -> str:
    """Parse and format final answer if it's a dictionary."""
    answer = answer.strip()

    with contextlib.suppress(json.JSONDecodeError, ValueError):
        data = json.loads(answer)
        if isinstance(data, dict):
            return FinalResponse(data).get_formatted_response()

    with contextlib.suppress(ValueError, SyntaxError):
        data = ast.literal_eval(answer)
        if isinstance(data, dict):
            return FinalResponse(data).get_formatted_response()

    return answer


@dataclasses.dataclass
class FinalResponse:
    data: dict[str, Any]

    def __post_init__(self) -> None:
        self.lines: list[str] = []
        self.processed_keys: set[str] = set()

        self._called: bool = False

    def get_formatted_response(self) -> str:
        """Format dictionary response."""
        if self._called:
            return "\n".join(self.lines)

        if "status" in self.data:
            self.add_status()

        if "summary" in self.data:
            self.add_summary()

        self.add_generated_files()

        self.add_generic_items()

        self._called = True

        return "\n".join(self.lines)

    def add_status(self) -> None:
        status_emoji = "✅" if self.data["status"] == "success" else "❌"
        self.lines.append(f"### {status_emoji} Status: {self.data['status'].title()}\n")
        self.processed_keys.add("status")

    def add_summary(self) -> None:
        self.lines.append("### 📝 Summary")
        self.lines.append(self.data["summary"])
        self.lines.append("")
        self.processed_keys.add("summary")

    def add_generated_files(self) -> None:
        for key in self.data:
            if (
                key not in self.processed_keys
                and isinstance(self.data[key], list)
                and ("generated" in key.lower() or "files" in key.lower())
            ):
                self.lines.append(f"### 📁 {key.replace('_', ' ').title()}")
                for item in self.data[key]:
                    if isinstance(item, str):
                        file_name = pathlib.Path(item).name if "/" in item or "\\" in item else item
                        self.lines.append(f"- `{file_name}`")
                    else:
                        self.lines.append(f"- {item}")
                self.lines.append("")
                self.processed_keys.add(key)

    def add_generic_items(self) -> None:
        for key, value in self.data.items():
            if key in self.processed_keys:
                continue

            formatted_key = key.replace("_", " ").title()

            if isinstance(value, dict):
                self.lines.append(f"### {formatted_key}")
                for sub_key, sub_value in value.items():
                    self.lines.append(f"- **{sub_key.replace('_', ' ').title()}:** {sub_value}")
                self.lines.append("")
            elif isinstance(value, list):
                self.lines.append(f"### {formatted_key}")
                for item in value:
                    self.lines.append(f"- {item}")
                self.lines.append("")
            else:
                self.lines.append(f"**{formatted_key}:** {value}")


@dataclasses.dataclass
class ChatResponse:
    """Handles formatting and display of agent responses.

    This class processes AgentStep objects from the new Claude-based agent
    and renders them appropriately in the Streamlit UI. Supports streaming
    updates where thinking is displayed progressively.
    """

    prompt: str
    output_placeholder: OutputRenderer | DeltaGenerator

    def __post_init__(self) -> None:
        self.result: AgentStep | None = None
        self.completed_steps_markdown: list[str] = []
        self.current_step_markdown: str = ""
        self.final_answer_text: str | None = None
        self._current_step_num: int = 0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_tool_calls: int = 0
        self.total_steps: int = 0

    def process_step(self, step: AgentStep) -> None:
        """Process and display an agent step.

        Args:
            step: An AgentStep from the agent's execution.
        """
        if step.is_streaming:
            self._process_streaming_step(step)
        else:
            self._process_completed_step(step)

        self._render_display(step)

        if not step.is_streaming:
            self.result = step
            self.total_input_tokens += step.input_tokens
            self.total_output_tokens += step.output_tokens
            self.total_tool_calls += len(step.tool_calls)
            self.total_steps += 1

    def _process_streaming_step(self, step: AgentStep) -> None:
        """Process a streaming step (partial thinking or tool execution)."""
        if step.step_number != self._current_step_num:
            if self.current_step_markdown:
                self.completed_steps_markdown.append(self.current_step_markdown)
            self._current_step_num = step.step_number
            self.current_step_markdown = f"#### Step {step.step_number}\n"

        if step.current_tool and step.tool_progress:
            current, total = step.tool_progress
            progress_text = f"🔧 Running tool {current}/{total}: **{step.current_tool}**..."
            if step.thinking:
                self.current_step_markdown = f"#### Step {step.step_number}\n\n💭 {step.thinking}\n\n{progress_text}\n"
            else:
                self.current_step_markdown = f"#### Step {step.step_number}\n\n{progress_text}\n"
        elif step.thinking:
            self.current_step_markdown = f"#### Step {step.step_number}\n\n💭 {step.thinking}\n"

    def _process_completed_step(self, step: AgentStep) -> None:
        """Process a completed step with full content."""
        self._current_step_num = step.step_number
        step_md_parts: list[str] = [f"#### Step {step.step_number}\n"]

        if step.thinking and step.has_tool_calls():
            step_md_parts.append(f"💭 {step.thinking}\n")

        if step.tool_calls:
            tool_names = [tc.name for tc in step.tool_calls]
            step_md_parts.append(f"**Tools:** {', '.join(tool_names)}\n")

        for result in step.tool_results:
            content = result.content
            if result.is_error:
                step_md_parts.append(f"**❌ {result.name} Error:** {content}\n")
            elif len(content) > 200:
                step_md_parts.append(
                    f"<details><summary>📋 {result.name} result</summary>\n\n```\n{content}\n```\n</details>\n"
                )
            else:
                step_md_parts.append(f"**Result ({result.name}):** {content}\n")

        if step.error:
            step_md_parts.append(f"**❌ Error:** {step.error}\n")

        self.current_step_markdown = "\n".join(step_md_parts)
        self.completed_steps_markdown.append(self.current_step_markdown)
        self.current_step_markdown = ""

        if step.is_final and step.final_answer is not None:
            self.final_answer_text = parse_and_format_final_answer(step.final_answer)

    def _render_display(self, step: AgentStep) -> None:
        """Render the current display state."""
        all_steps = self.completed_steps_markdown.copy()
        if self.current_step_markdown:
            all_steps.append(self.current_step_markdown)

        display_md = "\n\n".join(all_steps)

        if step.is_streaming:
            display_md += "\n\n⏳ _Thinking..._"
        elif self.final_answer_text is None and not step.is_final:
            display_md += "\n\n⏳ _Processing..._"
        elif self.final_answer_text is not None:
            display_md += f"\n\n---\n\n### ✅ Final Answer\n\n{self.final_answer_text}"
        elif step.error:
            display_md += f"\n\n---\n\n### ❌ Error\n\n{step.error}"

        self.output_placeholder.markdown(display_md, unsafe_allow_html=True)
