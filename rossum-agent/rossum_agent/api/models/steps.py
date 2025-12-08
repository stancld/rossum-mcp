"""Agent step response Pydantic models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ToolCallInfo(BaseModel):
    """Information about a tool call."""

    name: str
    arguments: dict[str, Any]


class PlanningStepResponse(BaseModel):
    """Serialized planning step for WebSocket."""

    type: Literal["planning"] = "planning"
    plan: str


class ActionStepResponse(BaseModel):
    """Serialized action step for WebSocket."""

    type: Literal["action"] = "action"
    step_number: int
    model_output: str | None = None
    tool_calls: list[ToolCallInfo] = []
    observations: str | None = None
    is_final_answer: bool = False
    action_output: str | None = None
    error: str | None = None


class FinalAnswerStepResponse(BaseModel):
    """Serialized final answer step for WebSocket."""

    type: Literal["final_answer"] = "final_answer"
    output: str
