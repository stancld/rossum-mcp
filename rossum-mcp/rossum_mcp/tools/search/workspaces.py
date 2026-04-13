from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.workspace import Workspace

from rossum_mcp.tools.base import build_filters, filter_by_name_regex, graceful_list

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _list_workspaces(
    client: AsyncRossumAPIClient,
    organization_id: int | None = None,
    name: str | None = None,
    use_regex: bool = False,
    max_items: int | None = None,
) -> list[Workspace]:
    logger.debug(f"Listing workspaces: organization_id={organization_id}, name={name}")
    filters = build_filters(organization=organization_id, name=None if use_regex else name)
    items = (await graceful_list(client, Resource.Workspace, "workspace", max_items=max_items, **filters)).items
    return filter_by_name_regex(items, name, use_regex)
