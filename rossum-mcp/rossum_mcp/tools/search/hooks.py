from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, Annotated

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.hook import HookRunData
from rossum_api.models.hook_template import HookTemplate

from rossum_mcp.logging_config import LogLevel  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
from rossum_mcp.models.hook import Hook
from rossum_mcp.tools.base import (
    build_filters,
    filter_by_workspace_id,
    graceful_list,
    resolve_queue_workspaces,
    resolve_workspaces_from_queues,
)

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

type Timestamp = Annotated[str, "ISO 8601 timestamp (e.g., '2024-01-15T10:30:00Z')"]
logger = logging.getLogger(__name__)


async def _list_hooks(
    client: AsyncRossumAPIClient,
    queue_id: int | None = None,
    workspace_id: int | None = None,
    active: bool | None = None,
    max_items: int | None = None,
) -> list[Hook]:
    logger.debug(f"Listing hooks: queue_id={queue_id}, workspace_id={workspace_id}, active={active}")
    filters = build_filters(queue=queue_id, active=active)
    result = await graceful_list(client, Resource.Hook, "hook", max_items=max_items, **filters)

    all_queue_urls = {url for hook in result.items for url in hook.queues}
    queue_workspace_map = await resolve_queue_workspaces(client, all_queue_urls)

    items = [
        Hook.from_base(hook, workspaces=resolve_workspaces_from_queues(hook.queues, queue_workspace_map))
        for hook in result.items
    ]
    return filter_by_workspace_id(items, workspace_id)


async def _list_hook_logs(
    client: AsyncRossumAPIClient,
    hook_id: int | None = None,
    queue_id: int | None = None,
    annotation_id: int | None = None,
    email_id: int | None = None,
    log_level: list[LogLevel] | LogLevel | None = None,
    status: str | None = None,
    status_code: int | None = None,
    request_id: str | None = None,
    timestamp_before: Timestamp | None = None,
    timestamp_after: Timestamp | None = None,
    start_before: Timestamp | None = None,
    start_after: Timestamp | None = None,
    end_before: Timestamp | None = None,
    end_after: Timestamp | None = None,
    search: str | None = None,
    page_size: int | None = None,
    max_items: int | None = None,
) -> list[HookRunData]:
    logger.debug(f"Listing hook logs: hook_id={hook_id}, queue_id={queue_id}")
    filters = build_filters(
        hook=hook_id,
        queue=queue_id,
        annotation=annotation_id,
        email=email_id,
        log_level=",".join(log_level) if isinstance(log_level, list) else log_level,
        status=status,
        status_code=status_code,
        request_id=request_id,
        timestamp_before=timestamp_before,
        timestamp_after=timestamp_after,
        start_before=start_before,
        start_after=start_after,
        end_before=end_before,
        end_after=end_after,
        search=search,
        page_size=page_size,
    )
    result = await graceful_list(client, Resource.HookRunData, "hook_log", max_items=max_items, **filters)
    return result.items


def _truncate_hook_template_for_list(template: HookTemplate) -> HookTemplate:
    """Keep only fields useful for browsing: id, name, url, type, events, description, use_token_owner."""
    return dataclasses.replace(
        template,
        sideload=[],
        metadata={},
        config={},
        test={},
        settings={},
        settings_schema=None,
        secrets_schema=None,
        guide=None,
        read_more_url=None,
        extension_image_url=None,
        settings_description=[],
        store_description=None,
        external_url=None,
    )


async def _list_hook_templates(client: AsyncRossumAPIClient, max_items: int | None = None) -> list[HookTemplate]:
    logger.debug("Listing hook templates")
    result = await graceful_list(client, Resource.HookTemplate, "hook_template", max_items=max_items)
    return [_truncate_hook_template_for_list(t) for t in result.items]
