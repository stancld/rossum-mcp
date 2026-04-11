from __future__ import annotations

import logging

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from rossum_api import AsyncRossumAPIClient
from rossum_api.models.rule import Rule, RuleAction

from rossum_mcp.tools.base import build_resource_url
from rossum_mcp.tools.validation import actions_to_dicts

logger = logging.getLogger(__name__)


async def _patch_rule(
    client: AsyncRossumAPIClient,
    base_url: str,
    rule_id: int,
    name: str | None = None,
    trigger_condition: str | None = None,
    actions: list[RuleAction] | None = None,
    enabled: bool | None = None,
    queue_ids: list[int] | None = None,
) -> Rule:
    """Partial update (PATCH) - only provided fields are updated."""
    logger.debug(f"Patching rule: rule_id={rule_id}")

    patch_data: dict = {}
    if name is not None:
        patch_data["name"] = name
    if trigger_condition is not None:
        patch_data["trigger_condition"] = trigger_condition
    if actions is not None:
        patch_data["actions"] = actions_to_dicts(actions)
    if enabled is not None:
        patch_data["enabled"] = enabled
    if queue_ids is not None:
        patch_data["queues"] = [build_resource_url(base_url, "queues", qid) for qid in queue_ids]

    if not patch_data:
        raise ToolError("No fields provided to update")

    updated_rule: Rule = await client.update_part_rule(rule_id, patch_data)
    logger.info(f"Rule {updated_rule.id} patched")
    return updated_rule


def register_rule_tools(mcp: FastMCP, client: AsyncRossumAPIClient, base_url: str) -> None:
    @mcp.tool(
        description="Patch a rule (PATCH); only provided fields change. queue_ids=[] clears queue scoping.",
        tags={"rules", "write"},
        annotations={"readOnlyHint": False},
    )
    async def patch_rule(
        rule_id: int,
        name: str | None = None,
        trigger_condition: str | None = None,
        actions: list[RuleAction] | None = None,
        enabled: bool | None = None,
        queue_ids: list[int] | None = None,
    ) -> Rule | dict:
        return await _patch_rule(client, base_url, rule_id, name, trigger_condition, actions, enabled, queue_ids)
