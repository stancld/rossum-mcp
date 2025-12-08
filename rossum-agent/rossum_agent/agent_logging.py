"""Agent logging wrapper for tracking all agent calls and tool usage."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rossum_agent.agent import AgentStep

logger = logging.getLogger(__name__)


def log_agent_result(
    result: AgentStep, prompt: str = "", duration: float = 0, total_input_tokens: int = 0, total_output_tokens: int = 0
) -> None:
    """Log agent execution result.

    Args:
        result: The AgentStep to log.
        prompt: The original user prompt.
        duration: Time taken for the step in seconds.
        total_input_tokens: Total input tokens across all steps.
        total_output_tokens: Total output tokens across all steps.
    """
    extra_fields: dict[str, object] = {
        "event_type": "agent_call_complete",
        "prompt": prompt,
        "duration_seconds": duration,
        "step_number": result.step_number,
        "is_final": result.is_final,
        "input_tokens": total_input_tokens if total_input_tokens else result.input_tokens,
        "output_tokens": total_output_tokens if total_output_tokens else result.output_tokens,
    }

    if result.thinking:
        extra_fields["thinking"] = result.thinking[:500] if len(result.thinking) > 500 else result.thinking

    if result.tool_calls:
        extra_fields["tool_calls"] = json.dumps(
            [{"name": tc.name, "arguments": tc.arguments} for tc in result.tool_calls], default=str
        )

    if result.tool_results:
        extra_fields["tool_results"] = json.dumps(
            [{"name": tr.name, "is_error": tr.is_error} for tr in result.tool_results], default=str
        )

    if result.final_answer:
        extra_fields["final_answer"] = (
            result.final_answer[:500] if len(result.final_answer) > 500 else result.final_answer
        )

    if result.error:
        extra_fields["error"] = result.error

    logger.info("Agent step completed", extra=extra_fields)
