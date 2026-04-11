from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.schema import Schema

from rossum_mcp.tools.base import (
    build_filters,
    filter_by_name_regex,
    filter_by_workspace_id,
    graceful_list,
    resolve_queue_workspaces,
    resolve_workspaces_from_queues,
)
from rossum_mcp.tools.search.models import SchemaListItem

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def _truncate_schema_for_list(schema: Schema, queue_workspace_map: dict[str, str]) -> SchemaListItem:
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
    filters = build_filters(name=None if use_regex else name, queue=queue_id)
    result = await graceful_list(client, Resource.Schema, "schema", max_items=max_items, **filters)

    all_queue_urls = {url for schema in result.items for url in schema.queues}
    queue_workspace_map = await resolve_queue_workspaces(client, all_queue_urls)

    items = [_truncate_schema_for_list(schema, queue_workspace_map) for schema in result.items]
    return filter_by_name_regex(filter_by_workspace_id(items, workspace_id), name, use_regex)
