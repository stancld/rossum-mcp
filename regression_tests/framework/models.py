from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from rossum_agent.agent.models import AgentStep

ToolMatchMode = Literal["exact_sequence", "subset", "subsequence"]


@dataclass
class ToolExpectation:
    """Expected tool calls for a regression test.

    Attributes:
        expected_tools: List of tool names expected to be called.
        mode: How to match tool calls:
            - "exact_sequence": must match exactly (order + multiplicity)
            - "subset": all expected must appear in actual (order not enforced)
            - "subsequence": expected must appear as ordered subsequence in actual
        allow_extras: Allow extra tools beyond expected (only for exact_sequence).
    """

    expected_tools: Sequence[str] = field(default_factory=list)
    mode: ToolMatchMode = "subset"
    allow_extras: bool = True


@dataclass
class TokenBudget:
    """Token budget constraints for a test.

    All values are optional bounds. Set to None to disable the check.
    """

    min_total_tokens: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None
    max_input_tokens_per_step: int | None = None
    max_output_tokens_per_step: int | None = None


@dataclass
class MermaidExpectation:
    """Expected mermaid diagram content validation.

    Attributes:
        descriptions: List of expected diagram descriptions. Each description
            explains what the diagram should represent. An LLM evaluates if
            the actual mermaid diagrams match these descriptions.
        min_diagrams: Minimum number of mermaid diagrams expected in the answer.
    """

    descriptions: Sequence[str] = field(default_factory=list)
    min_diagrams: int = 0


@dataclass
class FileExpectation:
    """Expected file outputs from a test.

    Attributes:
        expected_files: List of file patterns that should be created/modified.
            Supports glob wildcards (e.g., "*.md", "report_*.txt").
            Paths are relative to the outputs/ directory. Asserts exact count match.
        check_exists: If True, verify files exist after test.
        check_content: Optional dict mapping file path to expected content substring.
    """

    expected_files: Sequence[str] = field(default_factory=list)
    check_exists: bool = True
    check_content: dict[str, str] | None = None


@dataclass
class SuccessCriteria:
    """High-level success conditions for a task.

    Attributes:
        require_final_answer: Require final step to have a non-empty final_answer.
        forbid_error: Fail if any AgentStep has an error.
        forbid_tool_errors: Fail if any ToolResult has is_error=True.
        required_keywords: Keywords that must appear in the final answer.
        max_steps: Maximum number of steps allowed.
        require_subagent: Require that an Opus sub-agent was used during execution.
        mermaid_expectation: Expected mermaid diagram content.
        file_expectation: Expected file outputs.
        custom_check: Optional callable for domain-specific assertions.
            Should raise AssertionError on failure.
    """

    require_final_answer: bool = True
    forbid_error: bool = True
    forbid_tool_errors: bool = True
    required_keywords: Sequence[str] = field(default_factory=list)
    max_steps: int | None = None
    require_subagent: bool = False
    mermaid_expectation: MermaidExpectation = field(default_factory=MermaidExpectation)
    file_expectation: FileExpectation = field(default_factory=FileExpectation)
    custom_check: Callable[[list[AgentStep]], None] | None = None


@dataclass
class RegressionTestCase:
    """Definition of a regression test.

    Attributes:
        name: Unique identifier for this test case.
        api_base_url: Rossum API base URL.
        prompt: The prompt to send to the agent.
        api_token: Rossum API token (optional, can be provided via ROSSUM_API_TOKEN env var).
        rossum_url: Optional Rossum app URL for context extraction (e.g., queue/document URL).
        tool_expectation: Expected tool usage.
        token_budget: Token usage constraints.
        success_criteria: Success/failure conditions.
        description: Optional human-readable description.
    """

    name: str
    api_base_url: str
    prompt: str
    api_token: str | None = None
    rossum_url: str | None = None
    tool_expectation: ToolExpectation = field(default_factory=ToolExpectation)
    token_budget: TokenBudget = field(default_factory=TokenBudget)
    success_criteria: SuccessCriteria = field(default_factory=SuccessCriteria)
    description: str | None = None


@dataclass
class RegressionRun:
    """Results from running a regression test.

    Attributes:
        steps: All AgentStep objects yielded during execution.
        all_tools: Flattened list of tool names in call order.
        total_input_tokens: Sum of input tokens across all non-streaming steps.
        total_output_tokens: Sum of output tokens across all non-streaming steps.
        is_successful: Whether the agent completed without errors.
        final_answer: The final answer from the agent, if any.
        error: Error message if the agent failed.
    """

    steps: list[AgentStep]
    all_tools: list[str]
    total_input_tokens: int
    total_output_tokens: int
    is_successful: bool = True
    final_answer: str | None = None
    error: str | None = None

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def step_count(self) -> int:
        """Number of non-streaming steps."""
        return len([s for s in self.steps if not s.is_streaming])

    @property
    def tool_count(self) -> int:
        """Number of tool calls made."""
        return len(self.all_tools)
