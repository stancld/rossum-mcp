from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from anthropic.types import ThinkingBlockParam

if TYPE_CHECKING:
    from typing import Any, Literal


@dataclass
class ToolCall:
    """Represents a single tool call made by the agent."""

    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCall:
        return cls(id=data["id"], name=data["name"], arguments=data.get("arguments", {}))


@dataclass
class ToolResult:
    """Represents the result of a tool call."""

    tool_call_id: str
    name: str
    content: str
    is_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "content": self.content,
            "is_error": self.is_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolResult:
        return cls(
            tool_call_id=data["tool_call_id"],
            name=data["name"],
            content=data.get("content", ""),
            is_error=data.get("is_error", False),
        )


@dataclass
class StreamDelta:
    """A tagged delta from stream processing - either thinking or text."""

    kind: Literal["thinking", "text"]
    content: str


@dataclass
class ThinkingBlockData:
    """Represents a thinking block from extended thinking.

    Must be preserved and passed back to the API when continuing tool use conversations.
    """

    thinking: str
    signature: str

    def to_dict(self) -> ThinkingBlockParam:
        return ThinkingBlockParam(type="thinking", thinking=self.thinking, signature=self.signature)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThinkingBlockData:
        return cls(thinking=data["thinking"], signature=data["signature"])
