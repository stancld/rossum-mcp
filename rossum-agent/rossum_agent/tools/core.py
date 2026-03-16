"""Core module with shared types, callbacks, and per-request state management.

This module provides the foundational types and state management used by
all internal tools. A single AgentContext dataclass replaces individual
ContextVars for cleaner setup/teardown.
"""

from __future__ import annotations

import contextvars
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from rossum_agent.api.models.schemas import Persona

if TYPE_CHECKING:
    import asyncio

    from anthropic.types import ToolParam

    from rossum_agent.change_tracking.store import CommitStore, SnapshotStore
    from rossum_agent.rossum_mcp_integration import MCPConnection
    from rossum_agent.tools.task_tracker import TaskTracker


# Shared constants for cautious persona write-gate contract.
# These strings couple core.py, agent_service.py, and the TUI — keep in sync.
CAUTIOUS_CONFIRMATION_MARKER = "requires user confirmation"
CAUTIOUS_APPROVAL_LABEL = "Yes, proceed"


@dataclass
class SubAgentProgress:
    """Progress information from a sub-agent (e.g., schema patching Opus sub-agent)."""

    tool_name: str
    iteration: int
    max_iterations: int
    current_tool: str | None = None
    tool_calls: list[str] = field(default_factory=list)
    status: str = "running"


@dataclass
class SubAgentTokenUsage:
    """Token usage from a sub-agent call."""

    tool_name: str
    input_tokens: int
    output_tokens: int
    iteration: int | None = None
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class SubAgentText:
    """Text output from a sub-agent (e.g., schema patching Opus sub-agent)."""

    tool_name: str
    text: str
    is_final: bool = False


@dataclass
class QuestionOption:
    """A single option for an agent question."""

    value: str
    label: str
    description: str = ""


@dataclass
class AgentQuestionItem:
    """A single question within an agent question event."""

    question: str
    options: list[QuestionOption] = field(default_factory=list)
    multi_select: bool = False


@dataclass
class AgentQuestion:
    """Structured question(s) from the agent to the user."""

    questions: list[AgentQuestionItem]


SubAgentProgressCallback = Callable[[SubAgentProgress], None]
SubAgentTextCallback = Callable[[SubAgentText], None]
SubAgentTokenCallback = Callable[[SubAgentTokenUsage], None]
TaskSnapshotCallback = Callable[[list[dict[str, object]]], None]
QuestionCallback = Callable[[AgentQuestion], None]


@dataclass
class DynamicToolsState:
    """Per-conversation state for dynamically loaded MCP tools.

    Tracks which tool categories/skills have been loaded and stores the
    converted Anthropic tool definitions. Lives on AgentContext so state
    is properly scoped per-request and doesn't leak between conversations.
    """

    loaded_categories: set[str] = field(default_factory=set)
    tools: list[ToolParam] = field(default_factory=list)
    loaded_skills: set[str] = field(default_factory=set)
    version: int = 0

    def reset(self) -> None:
        """Reset state for a new conversation."""
        self.loaded_categories.clear()
        self.tools.clear()
        self.loaded_skills.clear()
        self.version += 1


@dataclass
class AgentContext:
    """Per-request state for the agent, replacing 13 individual ContextVars."""

    # MCP
    mcp_connection: MCPConnection | None = None
    mcp_event_loop: asyncio.AbstractEventLoop | None = None
    mcp_mode: str = "read-only"
    # Credentials & environment
    rossum_credentials: tuple[str, str] | None = None
    rossum_environment: str | None = None
    # State
    output_dir: Path | None = None
    commit_store: CommitStore | None = None
    snapshot_store: SnapshotStore | None = None
    task_tracker: TaskTracker | None = None
    dynamic_tools: DynamicToolsState = field(default_factory=DynamicToolsState)
    # Persona
    persona: Persona = Persona.DEFAULT
    # Cautious persona: write confirmation tracking
    cautious_preapproved_writes: set[str] = field(default_factory=set)
    cautious_blocked_writes: set[str] = field(default_factory=set)
    # Callbacks
    progress_callback: SubAgentProgressCallback | None = None
    text_callback: SubAgentTextCallback | None = None
    token_callback: SubAgentTokenCallback | None = None
    task_snapshot_callback: TaskSnapshotCallback | None = None
    question_callback: QuestionCallback | None = None

    @property
    def is_read_only(self) -> bool:
        return self.mcp_mode != "read-write"

    def get_output_dir(self) -> Path:
        """Get the output directory, falling back to ./outputs."""
        if self.output_dir is not None:
            return self.output_dir
        fallback = Path("./outputs")
        fallback.mkdir(exist_ok=True)
        return fallback

    def get_rossum_credentials(self) -> tuple[str, str] | None:
        """Get Rossum API credentials from context or environment.

        Checks context first (set by API service), then falls back to environment variables.
        """
        if self.rossum_credentials is not None:
            return self.rossum_credentials

        api_base = os.getenv("ROSSUM_API_BASE_URL")
        token = os.getenv("ROSSUM_API_TOKEN")
        if api_base and token:
            return api_base, token

        return None

    def require_rossum_credentials(self) -> tuple[str, str]:
        """Get Rossum API credentials, raising if unavailable."""
        if (creds := self.get_rossum_credentials()) is not None:
            return creds
        raise ValueError("Rossum API credentials not available (neither in context nor environment variables)")

    def report_progress(self, progress: SubAgentProgress) -> None:
        if self.progress_callback is not None:
            self.progress_callback(progress)

    def report_token_usage(self, usage: SubAgentTokenUsage) -> None:
        if self.token_callback is not None:
            self.token_callback(usage)

    def report_task_snapshot(self, snapshot: list[dict[str, object]]) -> None:
        if self.task_snapshot_callback is not None:
            self.task_snapshot_callback(snapshot)

    def report_question(self, question: AgentQuestion) -> None:
        if self.question_callback is not None:
            self.question_callback(question)


_agent_context: contextvars.ContextVar[AgentContext | None] = contextvars.ContextVar("agent_context", default=None)


def get_context() -> AgentContext:
    """Get the current AgentContext, creating a default one if none is set."""
    if (ctx := _agent_context.get()) is not None:
        return ctx
    ctx = AgentContext()
    _agent_context.set(ctx)
    return ctx


def set_context(ctx: AgentContext) -> contextvars.Token[AgentContext | None]:
    """Set the AgentContext for the current async/thread context. Returns a reset token."""
    return _agent_context.set(ctx)


def reset_context(token: contextvars.Token[AgentContext | None]) -> None:
    """Reset the AgentContext to its previous value using the token from set_context."""
    _agent_context.reset(token)
