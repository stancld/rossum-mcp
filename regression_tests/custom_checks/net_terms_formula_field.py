"""Check that Net Terms formula field was added to schema."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep

_REQUIRED_TERMS = ["Net 15", "Net 30", "Outstanding"]


def check_net_terms_formula_field_added(steps: list[AgentStep]) -> tuple[bool, str]:
    """Verify that a formula field for Net Terms was added to the schema."""
    for step in steps:
        for tr in step.tool_results:
            if tr.name != "suggest_formula_field":
                continue

            missing = [term for term in _REQUIRED_TERMS if term not in tr.content]
            if not missing:
                return True, "Formula field contains all required terms"
            return False, f"Missing terms in formula: {missing}"

    return False, "No suggest_formula_field tool result found"
