from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.rule import Rule as RossumRule

from rossum_mcp.models.rule import Rule
from rossum_mcp.tools.base import (
    build_filters,
    get_multi_queue_urls,
    resolve_workspaces_from_queues,
    search_with_workspace_resolution,
)

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def _enrich_rule(rule: RossumRule, queue_workspace_map: dict[str, str]) -> Rule:
    return Rule.from_base(rule, workspaces=resolve_workspaces_from_queues(rule.queues, queue_workspace_map))


async def _list_rules(
    client: AsyncRossumAPIClient,
    queue_id: int | None = None,
    workspace_id: int | None = None,
    organization_id: int | None = None,
    enabled: bool | None = None,
    max_items: int | None = None,
) -> list[Rule]:
    logger.debug(
        f"Listing rules: queue_id={queue_id}, workspace_id={workspace_id}, organization_id={organization_id}, enabled={enabled}"
    )
    return await search_with_workspace_resolution(
        client,
        Resource.Rule,
        "rule",
        enrich=_enrich_rule,
        get_queue_urls=get_multi_queue_urls,
        workspace_id=workspace_id,
        max_items=max_items,
        filters=build_filters(queue=queue_id, organization=organization_id, enabled=enabled),
    )
