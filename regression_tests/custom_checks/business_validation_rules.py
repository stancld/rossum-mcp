"""Check that business validation rules have correct trigger conditions and actions."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from regression_tests.custom_checks._utils import create_api_client, extract_id_from_final_answer

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep

EXPECTED_RULES = [
    {
        "name_hint": "total_amount_threshold",
        "trigger_fields": {"amount_total"},
        "trigger_operator": "inequality",
        "action_type": "error",
        "message_hint": "400",
    },
    {
        "name_hint": "line_items_sum",
        "trigger_fields": {"item_amount_total", "amount_total"},
        "trigger_operator": "sum_equality",
        "action_type": "error",
    },
    {
        "name_hint": "line_item_multiplication",
        "trigger_fields": {"item_quantity", "item_amount_total"},
        "alternative_fields": {"item_amount", "item_amount_base"},
        "trigger_operator": "mult_equality",
        "action_type": "error",
    },
]


def check_business_validation_rules(steps: list[AgentStep], api_base_url: str, api_token: str) -> tuple[bool, str]:
    """Verify that business validation rules were created with correct conditions."""
    rule_id = extract_id_from_final_answer(steps)
    if not rule_id:
        return False, "No rule ID found in final answer"

    client = create_api_client(api_base_url, api_token)

    try:
        rule = client.retrieve_rule(int(rule_id))
    except Exception as e:
        return False, f"Failed to retrieve rule {rule_id}: {e}"

    org_id_match = re.search(r"/(\d+)$", rule.organization)
    if not org_id_match:
        return False, f"Cannot parse organization ID from: {rule.organization}"
    org_id = int(org_id_match.group(1))
    rules = list(client.list_rules(organization=org_id))
    rule_queues = set(getattr(rule, "queues", None) or [])
    if rule_queues:
        rules = [r for r in rules if set(getattr(r, "queues", None) or []) & rule_queues]

    if len(rules) < len(EXPECTED_RULES):
        return False, f"Expected at least {len(EXPECTED_RULES)} rules, got {len(rules)}"

    for expected in EXPECTED_RULES:
        matching = [r for r in rules if _rule_matches(r, expected)]
        if not matching:
            return (
                False,
                f"Missing rule with fields {expected['trigger_fields']} and operator '{expected['trigger_operator']}'",
            )

        rule = matching[0]
        error_actions = [
            a
            for a in (rule.actions or [])
            if a.type == "show_message" and getattr(a.payload, "type", None) == expected["action_type"]
        ]
        if not error_actions:
            return False, f"Rule '{rule.name}' missing show_message action with type '{expected['action_type']}'"

    return True, "All business validation rules match expected configuration"


def _extract_fields(condition: str) -> set[str]:
    """Extract field names from a TxScript trigger condition (e.g., 'field.amount_total')."""
    return set(re.findall(r"field\.(\w+)", condition))


def _get_operator_type(condition: str) -> str:
    """Determine the operator type of a trigger condition."""
    if "sum(" in condition.lower() and "!=" in condition:
        return "sum_equality"
    if "sum(" in condition.lower() and "==" in condition:
        return "sum_equality"
    if "*" in condition and ("!=" in condition or "==" in condition):
        return "mult_equality"
    if any(op in condition for op in ["<", ">", "<=", ">="]) and "==" not in condition and "!=" not in condition:
        return "inequality"
    return "unknown"


def _rule_matches(rule: object, expected: dict) -> bool:
    """Check if a rule's trigger condition matches expected fields and operator."""
    condition = getattr(rule, "trigger_condition", "") or ""
    actual_fields = _extract_fields(condition)
    operator = _get_operator_type(condition)

    if operator != expected["trigger_operator"]:
        return False

    if "alternative_fields" in expected:
        required = expected["trigger_fields"]
        alternatives = expected["alternative_fields"]
        if not required.issubset(actual_fields):
            return False
        present_alts = actual_fields & alternatives
        if len(present_alts) != 1:
            return False
        return actual_fields == required | present_alts

    return actual_fields == expected["trigger_fields"]
