from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource

from rossum_mcp.models.rule import Rule
from rossum_mcp.tools.base import (
    build_filters,
    filter_by_workspace_id,
    graceful_list,
    resolve_queue_workspaces,
    resolve_workspaces_from_queues,
)

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


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
    filters = build_filters(queue=queue_id, organization=organization_id, enabled=enabled)
    result = await graceful_list(client, Resource.Rule, "rule", max_items=max_items, **filters)

    all_queue_urls = {url for rule in result.items for url in rule.queues}
    queue_workspace_map = await resolve_queue_workspaces(client, all_queue_urls)

    items = [
        Rule.from_base(rule, workspaces=resolve_workspaces_from_queues(rule.queues, queue_workspace_map))
        for rule in result.items
    ]
    return filter_by_workspace_id(items, workspace_id)
