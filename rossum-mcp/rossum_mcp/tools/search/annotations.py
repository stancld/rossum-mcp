from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource

from rossum_mcp.models.annotation import Annotation
from rossum_mcp.tools.base import (
    build_filters,
    filter_by_workspace_id,
    graceful_list,
    resolve_queue_workspaces,
    resolve_workspace_from_queue,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _list_annotations(
    client: AsyncRossumAPIClient,
    queue_id: int,
    workspace_id: int | None = None,
    status: str | None = "importing,to_review,confirmed,exported",
    ordering: Sequence[str] = (),
    max_items: int | None = None,
) -> list[Annotation]:
    logger.debug(
        f"Listing annotations: queue_id={queue_id}, workspace_id={workspace_id}, status={status}, ordering={ordering}"
    )
    filters = build_filters(queue=queue_id, page_size=100, status=status, ordering=ordering or None)
    result = await graceful_list(client, Resource.Annotation, "annotation", max_items=max_items, **filters)

    all_queue_urls = {a.queue for a in result.items if a.queue}
    queue_workspace_map = await resolve_queue_workspaces(client, all_queue_urls)

    items = [
        Annotation.from_base(
            a, workspaces=[ws] if (ws := resolve_workspace_from_queue(a.queue, queue_workspace_map)) else []
        )
        for a in result.items
    ]
    return filter_by_workspace_id(items, workspace_id)
