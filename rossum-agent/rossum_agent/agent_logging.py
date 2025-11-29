"""Agent logging wrapper for tracking all agent calls and tool usage."""

from __future__ import annotations

import json
import logging

from smolagents.memory import ActionStep, FinalAnswerStep

logger = logging.getLogger(__name__)


def log_agent_result(result: ActionStep | FinalAnswerStep, prompt: str = "", duration: float = 0) -> None:
    """Log agent execution result. Use after consuming streaming generators."""
    extra_fields = {
        "event_type": "agent_call_complete",
        "prompt": prompt,
        "duration_seconds": duration,
    }

    if isinstance(result, FinalAnswerStep):
        extra_fields["output"] = str(result.output)
    elif isinstance(result, ActionStep):
        extra_fields["step_number"] = result.step_number
        extra_fields["model_output"] = str(result.model_output) if result.model_output else None
        extra_fields["action_output"] = str(result.action_output) if result.action_output else None
        extra_fields["observations"] = str(result.observations) if result.observations else None
        extra_fields["tool_calls"] = json.dumps(result.tool_calls, default=str) if result.tool_calls else None
        extra_fields["error"] = str(result.error) if result.error else None
        extra_fields["token_usage"] = result.token_usage.__dict__ if result.token_usage else None
        extra_fields["timing"] = result.timing.__dict__ if result.timing else None
        extra_fields["is_final_answer"] = result.is_final_answer
    else:
        extra_fields["response"] = str(result)[:500]

    logger.info("Agent call completed", extra=extra_fields)
