from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.queue import Queue

from rossum_mcp.tools.base import build_filters, filter_by_name_regex, graceful_list
from rossum_mcp.tools.search.models import QueueListItem

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def _queue_to_list_item(queue: Queue) -> QueueListItem:
    return QueueListItem(
        id=queue.id,
        name=queue.name,
        url=queue.url,
        workspace=queue.workspace,
        schema=queue.schema,
        inbox=queue.inbox,
        connector=queue.connector,
        automation_enabled=queue.automation_enabled,
        automation_level=queue.automation_level,
        status=queue.status,
        counts=queue.counts or None,
    )


async def _list_queues(
    client: AsyncRossumAPIClient,
    workspace_id: int | None = None,
    name: str | None = None,
    use_regex: bool = False,
    max_items: int | None = None,
) -> list[QueueListItem]:
    logger.debug(f"Listing queues: workspace_id={workspace_id}, name={name}")
    filters = build_filters(workspace=workspace_id, name=None if use_regex else name)
    result = await graceful_list(client, Resource.Queue, "queue", max_items=max_items, **filters)
    items = [_queue_to_list_item(queue) for queue in result.items]
    return filter_by_name_regex(items, name, use_regex)
