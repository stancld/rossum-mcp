from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.email_template import EmailTemplate as RossumEmailTemplate

from rossum_mcp.models.email_template import EmailTemplate
from rossum_mcp.tools.base import (
    build_filters,
    get_single_queue_urls,
    resolve_workspace_from_queue,
    search_with_workspace_resolution,
)

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def _enrich_email_template(template: RossumEmailTemplate, queue_workspace_map: dict[str, str]) -> EmailTemplate:
    ws = resolve_workspace_from_queue(template.queue, queue_workspace_map)
    return EmailTemplate.from_base(template, workspaces=[ws] if ws else [])


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
    return await search_with_workspace_resolution(
        client,
        Resource.EmailTemplate,
        "email_template",
        enrich=_enrich_email_template,
        get_queue_urls=get_single_queue_urls,
        workspace_id=workspace_id,
        name=name,
        use_regex=use_regex,
        max_items=max_items,
        filters=build_filters(queue=queue_id, type=type, name=None if use_regex else name),
    )
