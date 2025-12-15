"""Type definitions for the subagent system.

This module defines the core types used for subagent orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SubagentType(str, Enum):
    """Types of specialized subagents available."""

    DOCUMENT_ANALYZER = "document_analyzer"
    HOOK_DEBUGGER = "hook_debugger"
    SCHEMA_EXPERT = "schema_expert"
    RULE_OPTIMIZER = "rule_optimizer"


@dataclass
class SubagentDefinition:
    """Definition of a specialized subagent.

    Attributes:
        type: The type of subagent.
        description: Human-readable description of the subagent's purpose.
        tools: List of tool names this subagent is allowed to use.
        system_prompt: The system prompt for this subagent.
        max_steps: Maximum number of steps the subagent can take.
    """

    type: SubagentType
    description: str
    tools: list[str]
    system_prompt: str
    max_steps: int = 15


@dataclass
class SubagentResult:
    """Result from a subagent execution.

    Attributes:
        subagent_type: The type of subagent that was executed.
        task: The task that was given to the subagent.
        result: The final result/answer from the subagent.
        steps_taken: Number of steps taken to complete the task.
        input_tokens: Total input tokens used.
        output_tokens: Total output tokens used.
        error: Error message if the subagent failed.
        tool_calls: List of tool calls made during execution.
    """

    subagent_type: SubagentType
    task: str
    result: str | None = None
    steps_taken: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    tool_calls: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if the subagent completed successfully."""
        return self.error is None and self.result is not None
