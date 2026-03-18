"""AI SDK-compatible streaming schemas for the v2 chat transport."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from rossum_agent.api.models.schemas import AgentQuestionItemSchema, TokenUsageBreakdown

type JSONPrimitive = str | int | float | bool | None
type JSONValue = JSONPrimitive | list[JSONValue] | dict[str, JSONValue]


class _CamelModel(BaseModel):
    """Base for v2 models — serializes to camelCase with ``model_dump(by_alias=True)``."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class V2SubAgentProgressData(_CamelModel):
    """Payload for `data-sub-agent-progress` parts."""

    tool_name: str
    iteration: int
    max_iterations: int
    current_tool: str | None = None
    tool_calls: list[str] = Field(default_factory=list)
    status: Literal["thinking", "searching", "analyzing", "reasoning", "running_tool", "completed", "running"] = (
        "running"
    )


class V2TaskSnapshotData(_CamelModel):
    """Payload for `data-task-snapshot` parts."""

    tasks: list["V2TaskSnapshotTask"]


class V2TaskSnapshotTask(_CamelModel):
    """Single task item carried by `data-task-snapshot` parts."""

    id: str
    subject: str
    status: Literal["pending", "in_progress", "completed"]
    description: str = ""


class V2AgentQuestionData(_CamelModel):
    """Payload for `data-agent-question` parts."""

    questions: list[AgentQuestionItemSchema]


class V2FileCreatedData(_CamelModel):
    """Payload for `data-file-created` parts."""

    filename: str
    url: str


class V2CommitInfoData(_CamelModel):
    """Payload for `data-commit-info` parts."""

    hash: str
    message: str | None = None
    changes_count: int = 0


class V2MessageMetadata(_CamelModel):
    """Assistant message metadata emitted alongside v2 stream parts."""

    model: str | None = None
    finish_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    token_usage_breakdown: TokenUsageBreakdown | None = None
    max_input_tokens: int | None = None
    context_usage_fraction: float | None = None

    @model_validator(mode="after")
    def populate_total_tokens(self) -> V2MessageMetadata:
        """Fill `total_tokens` when the caller only provides input/output counts."""
        if self.total_tokens is None and self.input_tokens is not None and self.output_tokens is not None:
            self.total_tokens = self.input_tokens + self.output_tokens
        return self


class V2TextPart(_CamelModel):
    """Plain assistant text content."""

    type: Literal["text"] = "text"
    text: str


class V2ReasoningPart(_CamelModel):
    """Visible reasoning content."""

    type: Literal["reasoning"] = "reasoning"
    text: str


class V2ToolCallPart(_CamelModel):
    """Tool invocation represented as an AI SDK-compatible part."""

    type: Literal["tool-call"] = "tool-call"
    tool_call_id: str
    tool_name: str
    input: JSONValue | None = None


class V2ToolResultPart(_CamelModel):
    """Tool result represented as an AI SDK-compatible part."""

    type: Literal["tool-result"] = "tool-result"
    tool_call_id: str
    output: JSONValue | None = None
    is_error: bool = False


class V2SubAgentProgressPart(_CamelModel):
    """Rossum-specific sub-agent progress side channel."""

    type: Literal["data-sub-agent-progress"] = "data-sub-agent-progress"
    id: str | None = None
    data: V2SubAgentProgressData


class V2TaskSnapshotPart(_CamelModel):
    """Rossum-specific task tracking side channel."""

    type: Literal["data-task-snapshot"] = "data-task-snapshot"
    id: str | None = None
    data: V2TaskSnapshotData


class V2AgentQuestionPart(_CamelModel):
    """Rossum-specific structured question side channel."""

    type: Literal["data-agent-question"] = "data-agent-question"
    id: str | None = None
    data: V2AgentQuestionData


class V2FileCreatedPart(_CamelModel):
    """Rossum-specific file creation side channel."""

    type: Literal["data-file-created"] = "data-file-created"
    id: str | None = None
    data: V2FileCreatedData


class V2CommitInfoPart(_CamelModel):
    """Rossum-specific config commit side channel."""

    type: Literal["data-commit-info"] = "data-commit-info"
    id: str | None = None
    data: V2CommitInfoData


class V2MessageMetadataChunk(_CamelModel):
    """Final metadata chunk emitted on the v2 stream."""

    type: Literal["message-metadata"] = "message-metadata"
    metadata: V2MessageMetadata


V2MessagePart = Annotated[
    V2TextPart
    | V2ReasoningPart
    | V2ToolCallPart
    | V2ToolResultPart
    | V2SubAgentProgressPart
    | V2TaskSnapshotPart
    | V2AgentQuestionPart
    | V2FileCreatedPart
    | V2CommitInfoPart,
    Field(discriminator="type"),
]

V2StreamChunk = Annotated[V2MessagePart | V2MessageMetadataChunk, Field(discriminator="type")]


class V2AssistantMessage(_CamelModel):
    """Fully assembled assistant message for the v2 transport."""

    role: Literal["assistant"] = "assistant"
    parts: list[V2MessagePart]
    metadata: V2MessageMetadata | None = None
