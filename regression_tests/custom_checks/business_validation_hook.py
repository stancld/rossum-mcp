"""Check that business validation hook has correct settings."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rossum_api import SyncRossumAPIClient
from rossum_api.dtos import Token

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep

# Expected checks defined by: required fields, operator type, and check type
# Operator types: "inequality" (<, >, <=, >=), "sum_equality" (sum() with ==), "mult_equality" (* with ==)
EXPECTED_CHECKS = [
    {"fields": {"amount_total"}, "operator": "inequality", "type": "error"},
    {"fields": {"item_amount_total", "amount_total"}, "operator": "sum_equality", "type": "error"},
    {
        "fields": {"item_quantity", "item_amount_base", "item_amount_total"},
        "operator": "mult_equality",
        "type": "error",
    },
]


def check_business_validation_hook_settings(
    steps: list[AgentStep], api_base_url: str, api_token: str
) -> tuple[bool, str]:
    """Verify that business validation hook has correct check settings."""
    hook_id = _extract_hook_id_from_final_answer(steps)
    if not hook_id:
        return False, "No hook_id found in final answer"

    client = SyncRossumAPIClient(base_url=api_base_url, credentials=Token(api_token))

    try:
        hook = client.retrieve_hook(int(hook_id))
    except Exception as e:
        return False, f"Failed to retrieve hook {hook_id}: {e}"

    settings = hook.settings or {}
    checks = settings.get("checks", [])

    if len(checks) != len(EXPECTED_CHECKS):
        return False, f"Expected {len(EXPECTED_CHECKS)} checks, got {len(checks)}"

    for expected in EXPECTED_CHECKS:
        matching = [c for c in checks if _check_matches(c, expected)]
        if not matching:
            return False, f"Missing check with fields {expected['fields']} and operator '{expected['operator']}'"

        check = matching[0]
        if check.get("type") != expected["type"]:
            return (False, f"Check type mismatch: expected '{expected['type']}', got '{check.get('type')}'")

    return True, "All business validation checks match expected configuration"


def _extract_hook_id_from_final_answer(steps: list[AgentStep]) -> str | None:
    """Extract hook_id from the final answer (expected to be one-word answer)."""
    for step in reversed(steps):
        if step.final_answer:
            match = re.search(r"\b(\d+)\b", step.final_answer)
            if match:
                return match.group(1)
    return None


def _extract_fields(rule: str) -> set[str]:
    """Extract field names from a rule (e.g., '{amount_total}' or '{amount_total, default=0}')."""
    # Match field name at start of braces, stopping at comma, space, or closing brace
    return set(re.findall(r"\{(\w+)[,}\s]", rule))


def _get_operator_type(rule: str) -> str:
    """Determine the operator type of a rule."""
    if "sum(" in rule.lower() and "==" in rule:
        return "sum_equality"
    if "*" in rule and "==" in rule:
        return "mult_equality"
    if any(op in rule for op in ["<", ">", "<=", ">="]) and "==" not in rule:
        return "inequality"
    if "==" in rule:
        return "equality"
    return "unknown"


def _check_matches(check: dict, expected: dict) -> bool:
    """Check if a rule matches expected fields and operator type."""
    rule = check.get("rule", "")
    return _extract_fields(rule) == expected["fields"] and _get_operator_type(rule) == expected["operator"]
