from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.organization_group import OrganizationGroup

from rossum_mcp.tools.base import build_filters, filter_by_name_regex, graceful_list

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _list_organization_groups(
    client: AsyncRossumAPIClient,
    name: str | None = None,
    use_regex: bool = False,
    max_items: int | None = None,
) -> list[OrganizationGroup]:
    logger.debug(f"Listing organization groups: name={name}")
    filters = build_filters(name=None if use_regex else name)
    items = (
        await graceful_list(client, Resource.OrganizationGroup, "organization_group", max_items=max_items, **filters)
    ).items
    return filter_by_name_regex(items, name, use_regex)
