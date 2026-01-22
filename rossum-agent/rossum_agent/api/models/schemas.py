"""Pydantic models for API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CreateChatRequest(BaseModel):
    """Request body for creating a new chat session."""

    mcp_mode: Literal["read-only", "read-write"] = "read-only"


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


class SubAgentProgressEvent(BaseModel):
    """Event emitted during sub-agent (e.g., debug_hook Opus) execution via SSE."""

    type: Literal["sub_agent_progress"] = "sub_agent_progress"
    tool_name: str
    iteration: int
    max_iterations: int
    current_tool: str | None = None
    tool_calls: list[str] = Field(default_factory=list)
    status: Literal["thinking", "searching", "analyzing", "running_tool", "completed", "running"] = "running"


class SubAgentTextEvent(BaseModel):
    """Event emitted when sub-agent streams text output via SSE."""

    type: Literal["sub_agent_text"] = "sub_agent_text"
    tool_name: str
    text: str
    is_final: bool = False


class TokenUsageBySource(BaseModel):
    """Token usage for a specific source (main agent or sub-agent)."""

    input_tokens: int
    output_tokens: int
    total_tokens: int

    @classmethod
    def from_counts(cls, input_tokens: int, output_tokens: int) -> TokenUsageBySource:
        """Create from input/output counts, computing total."""
        return cls(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens + output_tokens)


class SubAgentTokenUsageDetail(BaseModel):
    """Token usage breakdown for sub-agents."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    by_tool: dict[str, TokenUsageBySource]

    @classmethod
    def from_counts(
        cls, input_tokens: int, output_tokens: int, by_tool: dict[str, tuple[int, int]]
    ) -> SubAgentTokenUsageDetail:
        """Create from input/output counts, computing total."""
        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            by_tool={name: TokenUsageBySource.from_counts(inp, out) for name, (inp, out) in by_tool.items()},
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
    ) -> TokenUsageBreakdown:
        """Create breakdown from raw token counts."""
        return cls(
            total=TokenUsageBySource.from_counts(total_input, total_output),
            main_agent=TokenUsageBySource.from_counts(main_input, main_output),
            sub_agents=SubAgentTokenUsageDetail.from_counts(sub_input, sub_output, sub_by_tool),
        )

    def format_summary_lines(self) -> list[str]:
        """Format token usage as human-readable lines."""
        lines = [
            "",
            "=" * 60,
            "TOKEN USAGE SUMMARY",
            "=" * 60,
            f"{'Category':<25} {'Input':>12} {'Output':>12} {'Total':>12}",
            "-" * 60,
            f"{'Main Agent':<25} {self.main_agent.input_tokens:>12,} {self.main_agent.output_tokens:>12,} {self.main_agent.total_tokens:>12,}",
            f"{'Sub-agents (total)':<25} {self.sub_agents.input_tokens:>12,} {self.sub_agents.output_tokens:>12,} {self.sub_agents.total_tokens:>12,}",
        ]
        for tool_name, usage in self.sub_agents.by_tool.items():
            lines.append(
                f"  └─ {tool_name:<21} {usage.input_tokens:>12,} {usage.output_tokens:>12,} {usage.total_tokens:>12,}"
            )
        lines.extend(
            [
                "-" * 60,
                f"{'TOTAL':<25} {self.total.input_tokens:>12,} {self.total.output_tokens:>12,} {self.total.total_tokens:>12,}",
                "=" * 60,
            ]
        )
        return lines


class StreamDoneEvent(BaseModel):
    """Final event emitted when streaming completes."""

    total_steps: int
    input_tokens: int
    output_tokens: int
    token_usage_breakdown: TokenUsageBreakdown | None = None


class FileCreatedEvent(BaseModel):
    """Event emitted when a file is created and stored."""

    type: Literal["file_created"] = "file_created"
    filename: str
    url: str


class HealthResponse(BaseModel):
    """Response for health check endpoint."""

    status: Literal["healthy", "unhealthy"]
    redis_connected: bool
    version: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    error_code: str | None = None


class FileListResponse(BaseModel):
    """Response for listing files in a chat session."""

    files: list[FileInfo]
    total: int
