"""Response models for Rossum Agent API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from rossum_agent_client.models.requests import ImageContent

# JSON-compatible value type for tool arguments
type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]


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


class StepEvent(BaseModel):
    """Event emitted during agent execution via SSE."""

    type: Literal["thinking", "intermediate", "tool_start", "tool_result", "final_answer", "error"]
    step_number: int
    content: str | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, JsonValue] | None = None
    tool_progress: list[int] | None = None
    result: str | None = None
    is_error: bool = False
    is_streaming: bool = False
    is_final: bool = False


class SubAgentProgressEvent(BaseModel):
    """Event emitted during sub-agent execution via SSE."""

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
    """Token usage for a specific source."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class SubAgentTokenUsageDetail(BaseModel):
    """Token usage breakdown for sub-agents."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    by_tool: dict[str, TokenUsageBySource]


class TokenUsageBreakdown(BaseModel):
    """Token usage breakdown by agent vs sub-agents."""

    total: TokenUsageBySource
    main_agent: TokenUsageBySource
    sub_agents: SubAgentTokenUsageDetail

    def format_summary_lines(self) -> list[str]:
        """Format token usage as human-readable lines."""
        main = self.main_agent
        subs = self.sub_agents
        total = self.total
        lines = [
            "",
            "=" * 60,
            "TOKEN USAGE SUMMARY",
            "=" * 60,
            f"{'Category':<25} {'Input':>12} {'Output':>12} {'Total':>12}",
            "-" * 60,
            f"{'Main Agent':<25} {main.input_tokens:>12,} {main.output_tokens:>12,} {main.total_tokens:>12,}",
            f"{'Sub-agents (total)':<25} {subs.input_tokens:>12,} {subs.output_tokens:>12,} {subs.total_tokens:>12,}",
        ]
        for tool_name, usage in subs.by_tool.items():
            lines.append(
                f"  └─ {tool_name:<21} {usage.input_tokens:>12,} {usage.output_tokens:>12,} {usage.total_tokens:>12,}"
            )
        lines.extend(
            [
                "-" * 60,
                f"{'TOTAL':<25} {total.input_tokens:>12,} {total.output_tokens:>12,} {total.total_tokens:>12,}",
                "=" * 60,
            ]
        )
        return lines


class StreamDoneEvent(BaseModel):
    """Final event emitted when streaming completes."""

    type: Literal["done"] = "done"
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


class FileListResponse(BaseModel):
    """Response for listing files in a chat session."""

    files: list[FileInfo]
    total: int
