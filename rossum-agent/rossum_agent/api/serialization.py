"""Step serialization for rossum-agent API."""

from __future__ import annotations

from typing import Any, cast

from smolagents.memory import ActionStep, FinalAnswerStep, PlanningStep

from rossum_agent.api.models import ActionStepResponse, FinalAnswerStepResponse, PlanningStepResponse, ToolCallInfo


def serialize_step(
    step: ActionStep | PlanningStep | FinalAnswerStep,
) -> dict[str, Any]:
    """Convert a smolagents step to a JSON-serializable dictionary."""
    if isinstance(step, PlanningStep):
        return cast("dict[str, Any]", PlanningStepResponse(plan=step.plan).model_dump())

    if isinstance(step, ActionStep):
        tool_calls = []
        if step.tool_calls:
            for tc in step.tool_calls:
                tool_calls.append(
                    ToolCallInfo(
                        name=tc.name,
                        arguments=tc.arguments if isinstance(tc.arguments, dict) else {},
                    )
                )

        response = ActionStepResponse(
            step_number=step.step_number,
            model_output=step.model_output if isinstance(step.model_output, str) else None,
            tool_calls=tool_calls,
            observations=step.observations,
            is_final_answer=step.is_final_answer,
            action_output=str(step.action_output) if step.action_output is not None else None,
            error=str(step.error) if step.error else None,
        )
        return cast("dict[str, Any]", response.model_dump())

    if isinstance(step, FinalAnswerStep):
        return cast(
            "dict[str, Any]",
            FinalAnswerStepResponse(output=str(step.output) if step.output is not None else "").model_dump(),
        )

    # Fallback for unknown types
    return {"type": "unknown", "data": str(step)}
