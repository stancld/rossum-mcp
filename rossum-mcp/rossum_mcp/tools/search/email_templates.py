from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource

from rossum_mcp.models.email_template import EmailTemplate
from rossum_mcp.tools.base import (
    build_filters,
    filter_by_name_regex,
    filter_by_workspace_id,
    graceful_list,
    resolve_queue_workspaces,
    resolve_workspace_from_queue,
)

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _list_email_templates(
    client: AsyncRossumAPIClient,
    queue_id: int | None = None,
    workspace_id: int | None = None,
    type: str | None = None,
    name: str | None = None,
    use_regex: bool = False,
    max_items: int | None = None,
) -> list[EmailTemplate]:
    logger.debug(
        f"Listing email templates: queue_id={queue_id}, workspace_id={workspace_id}, type={type}, name={name}"
    )
    filters = build_filters(queue=queue_id, type=type, name=None if use_regex else name)
    result = await graceful_list(client, Resource.EmailTemplate, "email_template", max_items=max_items, **filters)

    all_queue_urls = {t.queue for t in result.items}
    queue_workspace_map = await resolve_queue_workspaces(client, all_queue_urls)

    items = [
        EmailTemplate.from_base(
            t, workspaces=[ws] if (ws := resolve_workspace_from_queue(t.queue, queue_workspace_map)) else []
        )
        for t in result.items
    ]
    return filter_by_name_regex(filter_by_workspace_id(items, workspace_id), name, use_regex)
