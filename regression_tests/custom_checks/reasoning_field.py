"""Check that reasoning field has correct type, context, and prompt."""

from __future__ import annotations

from typing import TYPE_CHECKING

from regression_tests.custom_checks._utils import (
    call_haiku_check,
    extract_field_json_from_final_answer,
    get_final_answer,
)

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep

_PROMPT_EVAL = """Evaluate the following LLM prompt configured for a reasoning field.

The field is supposed to: Take the month from the "date due" field and return it in Spanish.

Prompt to evaluate:
{prompt}

Does this prompt clearly instruct the LLM to:
1. Extract the month from the date due field
2. Return the month name in Spanish

Answer with a JSON object:
{{"passed": true/false, "reasoning": "Brief explanation"}}"""


def check_reasoning_field_configured(steps: list[AgentStep], _api_base_url: str, _api_token: str) -> tuple[bool, str]:
    """Verify reasoning field has correct ui_configuration type, context, and prompt."""
    final_answer = get_final_answer(steps)
    if not final_answer:
        return False, "No final answer found"

    field = extract_field_json_from_final_answer(final_answer, "month_in_spanish")
    if not field:
        return False, "No month_in_spanish field JSON found in final answer"

    ui_config = field.get("ui_configuration", {})
    if not isinstance(ui_config, dict) or ui_config.get("type") != "reasoning":
        return False, f"Field ui_configuration.type is not 'reasoning': {ui_config}"

    context = field.get("context")
    if not context:
        return False, "Reasoning field has no context configured"

    has_date_due_context = any("date_due" in c for c in context)
    if not has_date_due_context:
        return False, f"Context does not reference date_due: {context}"

    prompt = field.get("prompt")
    if not prompt:
        return False, "Reasoning field has no prompt configured"

    description = field.get("description")
    if not description:
        return False, "Reasoning field has no description configured"

    return call_haiku_check(_PROMPT_EVAL.format(prompt=prompt))
