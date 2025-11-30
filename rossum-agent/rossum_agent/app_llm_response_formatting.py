from __future__ import annotations

import ast
import contextlib
import dataclasses
import json
import pathlib
import re
import time
from typing import TYPE_CHECKING, Any, Protocol

import streamlit.components.v1 as components
from smolagents.memory import ActionStep, PlanningStep

from rossum_agent.agent_logging import log_agent_result

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

    type AgentStep = ActionStep | PlanningStep


MERMAID_DIAGRAM_HEIGHT = 600  # px


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


def extract_mermaid_blocks(text: str) -> tuple[str, list[str]]:
    """Extract Mermaid diagram blocks and return cleaned text with diagram codes."""
    mermaid_pattern = r"```mermaid\n(.*?)\n```"
    matches = re.findall(mermaid_pattern, text, re.DOTALL)

    if not matches:
        return text, []

    # Replace mermaid blocks with placeholders
    result = text
    for i, mermaid_code in enumerate(matches):
        placeholder = f"\n\n[MERMAID_DIAGRAM_{i}]\n\n"
        result = result.replace(f"```mermaid\n{mermaid_code}\n```", placeholder, 1)

    return result, matches


def render_mermaid_diagram(mermaid_code: str) -> None:
    """Render a Mermaid diagram using Streamlit components."""
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
        </script>
    </head>
    <body>
        <div class="mermaid">
{mermaid_code.strip()}
        </div>
    </body>
    </html>
    """
    components.html(html_code, height=MERMAID_DIAGRAM_HEIGHT, scrolling=True)


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
    prompt: str
    output_placeholder: OutputRenderer | DeltaGenerator
    start_time: float = dataclasses.field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.result: AgentStep

        type TextAndDiagram = tuple[str, list[str]]

        self.steps_markdown: list[TextAndDiagram] = []
        self.final_answer_text: str | None = None
        self.final_answer_diagrams: list[str] = []

    def process_step(self, step: AgentStep) -> None:
        if isinstance(step, PlanningStep):
            self.process_planning_step(step)

        if isinstance(step, ActionStep):
            self.process_action_step(step)

        self.result = step

    def process_planning_step(self, step: PlanningStep) -> None:
        plan_text, mermaid_diagrams = extract_mermaid_blocks(step.plan.strip())
        plan_md = f"#### 🧠 Plan\n\n{plan_text}\n"
        self.steps_markdown.append((plan_md, mermaid_diagrams))

    def process_action_step(self, step: ActionStep) -> None:
        self.step_md_parts: list[str] = []
        self.step_md_parts.append(f"#### Step {step.step_number}\n")

        self._process_tool_calls(step)
        self._process_model_output(step)
        self._process_observations(step)

        self.step_md = "\n".join(self.step_md_parts)
        self.steps_markdown.append((self.step_md, []))

        # Detect final answer
        if step.is_final_answer and step.action_output is not None:
            raw_answer = str(step.action_output)
            formatted_answer = parse_and_format_final_answer(raw_answer)
            self.final_answer_text, self.final_answer_diagrams = extract_mermaid_blocks(formatted_answer)

        # Build current display
        display_parts = []
        for md_text, diagrams in self.steps_markdown:
            display_parts.append(md_text)
            for _diagram in diagrams:
                display_parts.append(f"[MERMAID_DIAGRAM: {len(display_parts)}]")

        display_md = "\n\n".join(display_parts)

        if self.final_answer_text is None:
            display_md += "\n\n⏳ _Processing..._"
        else:
            display_md += f"\n\n---\n\n### ✅ Final Answer\n\n{self.final_answer_text}"

        self.output_placeholder.markdown(display_md, unsafe_allow_html=True)

        for _md_text, diagrams in self.steps_markdown:
            for diagram in diagrams:
                render_mermaid_diagram(diagram)

        if self.final_answer_diagrams:
            for diagram in self.final_answer_diagrams:
                render_mermaid_diagram(diagram)

        # Log each completed step
        duration = time.time() - self.start_time
        log_agent_result(step, self.prompt, duration)

    def _process_model_output(self, step: ActionStep) -> None:
        if isinstance(step.model_output, str) and step.model_output.strip():
            model_output = step.model_output.strip()

            # Extract code blocks (everything between <code> and </code>)
            code_pattern = r"<code>(.*?)</code>"
            code_blocks = re.findall(code_pattern, model_output, re.DOTALL)

            # Extract thinking (everything outside code blocks)
            thinking = re.sub(code_pattern, "", model_output, flags=re.DOTALL).strip()

            # If no explicit thinking, try to extract first comment from code
            if not thinking and code_blocks:
                for code_block in code_blocks:
                    # Look for first comment line (# comment)
                    comment_match = re.search(r"^\s*#\s*(.+)$", code_block, re.MULTILINE)
                    if comment_match:
                        thinking = comment_match.group(1).strip()
                        break

            # Display thinking directly
            if thinking:
                self.step_md_parts.append(f"💭 {thinking}\n")

            # Display code in collapsible section
            if code_blocks:
                combined_code = "\n\n".join(block.strip() for block in code_blocks)
                self.step_md_parts.append(
                    f"<details><summary>🔍 View code</summary>\n\n```python\n{combined_code}\n```\n</details>\n"
                )

    def _process_tool_calls(self, step: ActionStep) -> None:
        # Tools used (skip python_interpreter as it's the default)
        if not step.tool_calls:
            return

        tool_names = [tc.name for tc in step.tool_calls if tc.name != "python_interpreter"]
        if tool_names:
            self.step_md_parts.append(f"**Tools:** {', '.join(tool_names)}\n")

    def _process_observations(self, step: ActionStep) -> None:
        if not step.observations:
            return

        obs_text = step.observations.strip()
        # Only show if there's meaningful output
        if obs_text and obs_text != "None" and len(obs_text) > 0:
            # Extract just the key output, skip verbose logs for demo
            if "Last output from code snippet:" in obs_text:
                output_part = obs_text.split("Last output from code snippet:")[-1].strip()
                if output_part and output_part != "None":
                    self.step_md_parts.append(f"**Result:** {output_part}\n")
            else:
                self.step_md_parts.append(
                    f"<details><summary>📋 View logs</summary>\n\n```\n{obs_text}\n```\n</details>\n"
                )
