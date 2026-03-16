"""Pydantic models for API requests and responses."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Persona(StrEnum):
    DEFAULT = "default"
    CAUTIOUS = "cautious"


class CreateChatRequest(BaseModel):
    """Request body for creating a new chat session."""

    mcp_mode: Literal["read-only", "read-write"] = "read-only"
    persona: Persona = Persona.DEFAULT


class ChatResponse(BaseModel):
    """Response for chat creation."""

    chat_id: str
    created_at: datetime


class ChatSummary(BaseModel):
    """Summary of a chat session for list responses."""

    chat_id: str
    timestamp: int
    message_count: int
    first_message: str
    preview: str | None = None
    summary: str | None = None


class ChatListResponse(BaseModel):
    """Response for listing chat sessions."""

    chats: list[ChatSummary]
    total: int
    limit: int
    offset: int


class ImageContent(BaseModel):
    """Image content in a message."""

    type: Literal["image"] = "image"
    media_type: Literal["image/jpeg", "image/png", "image/gif", "image/webp"]
    data: str = Field(..., description="Base64-encoded image data")

    @field_validator("data")
    @classmethod
    def validate_base64_size(cls, v: str) -> str:
        max_size = 5 * 1024 * 1024  # 5 MB limit for base64 data
        if len(v) > max_size * 4 // 3:  # Base64 is ~4/3 larger than binary
            msg = "Image data exceeds maximum size of 5 MB"
            raise ValueError(msg)
        return v


class DocumentContent(BaseModel):
    """Document content in a message."""

    type: Literal["document"] = "document"
    media_type: Literal["application/pdf"]
    data: str = Field(..., description="Base64-encoded document data")
    filename: str = Field(..., description="Original filename of the document")

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        name = Path(v).name
        if not name:
            raise ValueError("filename must not be empty or a bare directory path")
        return name

    @field_validator("data")
    @classmethod
    def validate_base64_size(cls, v: str) -> str:
        max_size = 20 * 1024 * 1024  # 20 MB limit for base64 data
        if len(v) > max_size * 4 // 3:
            msg = "Document data exceeds maximum size of 20 MB"
            raise ValueError(msg)
        return v


class TextContent(BaseModel):
    """Text content in a message."""

    type: Literal["text"] = "text"
    text: str


class Message(BaseModel):
    """A single chat message."""

    role: Literal["user", "assistant"]
    content: str | list[TextContent | ImageContent]
    feedback: bool | None = None


class FileInfo(BaseModel):
    """Information about a file in a chat session."""

    filename: str
    size: int
    timestamp: str
    mime_type: str | None = None


class ChatDetail(BaseModel):
    """Detailed chat session information."""

    chat_id: str
    messages: list[Message]
    created_at: datetime
    files: list[FileInfo]


class DeleteResponse(BaseModel):
    """Response for delete operations."""

    deleted: bool


class CancelResponse(BaseModel):
    """Response for cancel operations."""

    cancelled: bool


class MessageRequest(BaseModel):
    """Request body for sending a message.

    Supports text-only messages or multimodal messages with images and documents.
    For image messages, use the `images` field with base64-encoded image data.
    For document messages, use the `documents` field with base64-encoded PDF data.
    """

    content: str = Field(..., min_length=1, max_length=50000, description="Text content of the message")
    images: list[ImageContent] | None = Field(
        default=None,
        max_length=5,
        description="Optional list of images (max 5) to include with the message",
    )
    documents: list[DocumentContent] | None = Field(
        default=None,
        max_length=5,
        description="Optional list of PDF documents (max 5) to include with the message",
    )
    rossum_url: str | None = Field(default=None, description="Optional Rossum app URL for context")
    mcp_mode: Literal["read-only", "read-write"] | None = Field(
        default=None,
        description="MCP mode to use for this message and all subsequent messages. If not specified, uses the chat's current mode.",
    )
    persona: Persona | None = Field(
        default=None,
        description="Agent persona to use for this message and all subsequent messages. If not specified, uses the chat's current persona.",
    )


class StepEvent(BaseModel):
    """Event emitted during agent execution via SSE.

    Extended thinking mode separates the model's internal reasoning from its final response:
    - "thinking": Model's chain-of-thought reasoning (from thinking blocks)
    - "intermediate": Model's response text before tool calls
    - "final_answer": Final response when no more tool calls needed
    """

    type: Literal["thinking", "intermediate", "tool_start", "tool_result", "final_answer", "error"]
    step_number: int
    content: str | None = None
    tool_name: str | None = None
    tool_arguments: dict | None = None
    tool_progress: tuple[int, int] | None = None
    result: str | None = None
    is_error: bool = False
    is_streaming: bool = False
    is_final: bool = False
    tool_call_id: str | None = None
    is_hook_output: bool = False
    context_usage_fraction: float | None = None


class SubAgentProgressEvent(BaseModel):
    """Event emitted during sub-agent execution via SSE."""

    type: Literal["sub_agent_progress"] = "sub_agent_progress"
    tool_name: str
    iteration: int
    max_iterations: int
    current_tool: str | None = None
    tool_calls: list[str] = Field(default_factory=list)
    status: Literal["thinking", "searching", "analyzing", "reasoning", "running_tool", "completed", "running"] = (
        "running"
    )


class SubAgentTextEvent(BaseModel):
    """Event emitted when sub-agent streams text output via SSE."""

    type: Literal["sub_agent_text"] = "sub_agent_text"
    tool_name: str
    text: str
    is_final: bool = False


class TaskSnapshotEvent(BaseModel):
    """Event emitted when task tracker state changes via SSE."""

    type: Literal["task_snapshot"] = "task_snapshot"
    tasks: list[dict[str, object]]


class QuestionOptionSchema(BaseModel):
    """A single option for an agent question."""

    value: str
    label: str
    description: str = ""


class AgentQuestionItemSchema(BaseModel):
    """A single question within an agent question event."""

    question: str
    options: list[QuestionOptionSchema] = Field(default_factory=list)
    multi_select: bool = False


class AgentQuestionEvent(BaseModel):
    """Event emitted when the agent asks the user a structured question."""

    type: Literal["agent_question"] = "agent_question"
    questions: list[AgentQuestionItemSchema]


class TokenUsageBySource(BaseModel):
    """Token usage for a specific source (main agent or sub-agent)."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @classmethod
    def from_counts(
        cls,
        input_tokens: int,
        output_tokens: int,
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
    ) -> TokenUsageBySource:
        """Create from input/output counts, computing total."""
        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cache_creation_input_tokens=cache_creation_input_tokens,
            cache_read_input_tokens=cache_read_input_tokens,
        )


class SubAgentTokenUsageDetail(BaseModel):
    """Token usage breakdown for sub-agents."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    by_tool: dict[str, TokenUsageBySource]

    @classmethod
    def from_counts(
        cls,
        input_tokens: int,
        output_tokens: int,
        by_tool: dict[str, tuple[int, int]],
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
        cache_by_tool: dict[str, tuple[int, int]] | None = None,
    ) -> SubAgentTokenUsageDetail:
        """Create from input/output counts, computing total."""
        _cache_by_tool = cache_by_tool or {}
        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cache_creation_input_tokens=cache_creation_input_tokens,
            cache_read_input_tokens=cache_read_input_tokens,
            by_tool={
                name: TokenUsageBySource.from_counts(
                    inp,
                    out,
                    cache_creation_input_tokens=_cache_by_tool.get(name, (0, 0))[0],
                    cache_read_input_tokens=_cache_by_tool.get(name, (0, 0))[1],
                )
                for name, (inp, out) in by_tool.items()
            },
        )


class TokenUsageBreakdown(BaseModel):
    """Token usage breakdown by agent vs sub-agents."""

    total: TokenUsageBySource
    main_agent: TokenUsageBySource
    sub_agents: SubAgentTokenUsageDetail

    @classmethod
    def from_raw_counts(
        cls,
        total_input: int,
        total_output: int,
        main_input: int,
        main_output: int,
        sub_input: int,
        sub_output: int,
        sub_by_tool: dict[str, tuple[int, int]],
        main_cache_creation: int = 0,
        main_cache_read: int = 0,
        sub_cache_creation: int = 0,
        sub_cache_read: int = 0,
        sub_cache_by_tool: dict[str, tuple[int, int]] | None = None,
    ) -> TokenUsageBreakdown:
        """Create breakdown from raw token counts."""
        total_cache_creation = main_cache_creation + sub_cache_creation
        total_cache_read = main_cache_read + sub_cache_read
        return cls(
            total=TokenUsageBySource.from_counts(
                total_input,
                total_output,
                cache_creation_input_tokens=total_cache_creation,
                cache_read_input_tokens=total_cache_read,
            ),
            main_agent=TokenUsageBySource.from_counts(
                main_input,
                main_output,
                cache_creation_input_tokens=main_cache_creation,
                cache_read_input_tokens=main_cache_read,
            ),
            sub_agents=SubAgentTokenUsageDetail.from_counts(
                sub_input,
                sub_output,
                sub_by_tool,
                cache_creation_input_tokens=sub_cache_creation,
                cache_read_input_tokens=sub_cache_read,
                cache_by_tool=sub_cache_by_tool,
            ),
        )

    def format_summary_lines(self) -> list[str]:
        """Format token usage as human-readable lines."""
        has_cache = self.total.cache_read_input_tokens > 0 or self.total.cache_creation_input_tokens > 0

        if not has_cache:
            return self._format_summary_no_cache()
        return self._format_summary_with_cache()

    def _format_table_lines(self) -> list[str]:
        """Build the shared header and per-agent rows (used by both summary variants)."""
        w = 60
        lines = [
            "",
            "=" * w,
            "TOKEN USAGE SUMMARY",
            "=" * w,
            f"{'Category':<25} {'Input':>12} {'Output':>12} {'Total':>12}",
            "-" * w,
            f"{'Main Agent':<25} {self.main_agent.input_tokens:>12,} {self.main_agent.output_tokens:>12,} {self.main_agent.total_tokens:>12,}",
            f"{'Sub-agents (total)':<25} {self.sub_agents.input_tokens:>12,} {self.sub_agents.output_tokens:>12,} {self.sub_agents.total_tokens:>12,}",
        ]
        for tool_name, usage in self.sub_agents.by_tool.items():
            lines.append(
                f"  └─ {tool_name:<21} {usage.input_tokens:>12,} {usage.output_tokens:>12,} {usage.total_tokens:>12,}"
            )
        lines.extend(
            [
                "-" * w,
                f"{'TOTAL':<25} {self.total.input_tokens:>12,} {self.total.output_tokens:>12,} {self.total.total_tokens:>12,}",
            ]
        )
        return lines

    def _format_summary_no_cache(self) -> list[str]:
        w = 60
        return [*self._format_table_lines(), "=" * w]

    def _format_summary_with_cache(self) -> list[str]:
        w = 60

        def _new_input(source: TokenUsageBySource | SubAgentTokenUsageDetail) -> int:
            return source.input_tokens - source.cache_creation_input_tokens - source.cache_read_input_tokens

        lines = self._format_table_lines()
        lines.extend(
            [
                "-" * w,
                "",
                "Input token breakdown:",
                f"  {'Uncached (new)':<23} {_new_input(self.total):>12,}",
                f"  {'Cache read':<23} {self.total.cache_read_input_tokens:>12,}",
                f"  {'Cache write (creation)':<23} {self.total.cache_creation_input_tokens:>12,}",
            ]
        )
        if self.sub_agents.cache_creation_input_tokens:
            lines.extend(
                [
                    f"    {'Main Agent':<21} {self.main_agent.cache_creation_input_tokens:>12,}",
                    f"    {'Sub-agents':<21} {self.sub_agents.cache_creation_input_tokens:>12,}",
                ]
            )
        lines.append("=" * w)
        return lines


class StreamDoneEvent(BaseModel):
    """Final event emitted when streaming completes."""

    type: Literal["done"] = "done"
    total_steps: int
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    token_usage_breakdown: TokenUsageBreakdown | None = None
    max_input_tokens: int = 0
    context_usage_fraction: float = 0.0
    config_commit_hash: str | None = None
    config_commit_message: str | None = None
    config_changes_count: int = 0


class FileCreatedEvent(BaseModel):
    """Event emitted when a file is created and stored."""

    type: Literal["file_created"] = "file_created"
    filename: str
    url: str


class ReportToSlackRequest(BaseModel):
    rossum_url: str | None = Field(default=None, description="Optional Rossum app URL for context (queue, etc.)")


class ReportToSlackResponse(BaseModel):
    chat_id: str
    channel: str
    slack_ts: str


class HealthResponse(BaseModel):
    """Response for health check endpoint."""

    status: Literal["healthy", "unhealthy"]
    storage_connected: bool
    storage_backend: str
    version: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    error_code: str | None = None


class FileListResponse(BaseModel):
    """Response for listing files in a chat session."""

    files: list[FileInfo]
    total: int


class EntityChangeInfo(BaseModel):
    """A single entity change within a config commit."""

    entity_type: str
    entity_id: str
    entity_name: str
    operation: Literal["create", "update", "delete"]


class CommitInfo(BaseModel):
    """A configuration commit with its changes."""

    hash: str
    timestamp: datetime
    message: str
    user_request: str
    changes: list[EntityChangeInfo]


class CommitListResponse(BaseModel):
    """Response for listing config commits in a chat."""

    commits: list[CommitInfo]


class ArgumentSuggestion(BaseModel):
    """A suggested value for a slash command argument."""

    value: str
    description: str


class CommandInfo(BaseModel):
    """Information about an available slash command."""

    name: str
    description: str
    argument_suggestions: list[ArgumentSuggestion] = []


class CommandListResponse(BaseModel):
    """Response for listing available slash commands."""

    commands: list[CommandInfo]


class FeedbackRequest(BaseModel):
    turn_index: int = Field(..., ge=0)
    is_positive: bool


class FeedbackResponse(BaseModel):
    turn_index: int
    is_positive: bool


class FeedbackListResponse(BaseModel):
    feedback: dict[int, bool]
