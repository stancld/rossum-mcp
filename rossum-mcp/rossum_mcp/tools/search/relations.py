from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource

from rossum_mcp.tools.base import build_filters, graceful_list

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient


async def _list_relations(
    client: AsyncRossumAPIClient, max_items: int | None = None, **kwargs: object
) -> list[object]:
    filters = build_filters(**kwargs)
    result = await graceful_list(client, Resource.Relation, "relation", max_items=max_items, **filters)
    return result.items


async def _list_document_relations(
    client: AsyncRossumAPIClient, max_items: int | None = None, **kwargs: object
) -> list[object]:
    filters = build_filters(**kwargs)
    result = await graceful_list(
        client, Resource.DocumentRelation, "document_relation", max_items=max_items, **filters
    )
    return result.items
