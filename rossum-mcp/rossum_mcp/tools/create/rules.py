from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.models.rule import Rule, RuleAction

from rossum_mcp.tools.base import build_resource_url
from rossum_mcp.tools.validation import actions_to_dicts

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _create_rule(
    client: AsyncRossumAPIClient,
    base_url: str,
    name: str,
    trigger_condition: str,
    actions: list[RuleAction],
    enabled: bool = True,
    queue_ids: list[int] | None = None,
) -> Rule:
    logger.debug(f"Creating rule: name={name}, enabled={enabled}")

    rule_data: dict = {
        "name": name,
        "trigger_condition": trigger_condition,
        "actions": actions_to_dicts(actions),
        "enabled": enabled,
    }

    if queue_ids is not None:
        rule_data["queues"] = [build_resource_url(base_url, "queues", qid) for qid in queue_ids]

    rule: Rule = await client.create_new_rule(rule_data)
    logger.info(f"Rule {rule.id} '{rule.name}' created")
    return rule
