from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.annotation import Annotation as RossumAnnotation

from rossum_mcp.models.annotation import Annotation
from rossum_mcp.tools.base import (
    build_filters,
    get_single_queue_urls,
    resolve_workspace_from_queue,
    search_with_workspace_resolution,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def _enrich_annotation(annotation: RossumAnnotation, queue_workspace_map: dict[str, str]) -> Annotation:
    ws = resolve_workspace_from_queue(annotation.queue, queue_workspace_map)
    return Annotation.from_base(annotation, workspaces=[ws] if ws else [])


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
    return await search_with_workspace_resolution(
        client,
        Resource.Annotation,
        "annotation",
        enrich=_enrich_annotation,
        get_queue_urls=get_single_queue_urls,
        workspace_id=workspace_id,
        max_items=max_items,
        filters=build_filters(queue=queue_id, page_size=100, status=status, ordering=ordering or None),
    )
