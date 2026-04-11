from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.schema import Schema

from rossum_mcp.tools.base import (
    build_filters,
    get_multi_queue_urls,
    resolve_workspaces_from_queues,
    search_with_workspace_resolution,
)
from rossum_mcp.tools.search.models import SchemaListItem

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def _enrich_schema(schema: Schema, queue_workspace_map: dict[str, str]) -> SchemaListItem:
    """Convert to SchemaListItem with content omitted and workspaces resolved."""
    workspaces = resolve_workspaces_from_queues(schema.queues, queue_workspace_map)
    return SchemaListItem(
        id=schema.id,
        name=schema.name,
        queues=schema.queues,
        workspaces=workspaces or None,
        url=schema.url,
        metadata=schema.metadata,
        modified_by=schema.modified_by,
        modified_at=schema.modified_at,
    )


async def _list_schemas(
    client: AsyncRossumAPIClient,
    name: str | None = None,
    queue_id: int | None = None,
    workspace_id: int | None = None,
    use_regex: bool = False,
    max_items: int | None = None,
) -> list[SchemaListItem]:
    logger.debug(f"Listing schemas: name={name}, queue_id={queue_id}, workspace_id={workspace_id}")
    return await search_with_workspace_resolution(
        client,
        Resource.Schema,
        "schema",
        enrich=_enrich_schema,
        get_queue_urls=get_multi_queue_urls,
        workspace_id=workspace_id,
        name=name,
        use_regex=use_regex,
        max_items=max_items,
        filters=build_filters(name=None if use_regex else name, queue=queue_id),
    )
