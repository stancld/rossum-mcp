"""Hook tools for Rossum MCP Server."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any, Literal

from rossum_api.models.hook import Hook, HookRunData, HookType

from rossum_mcp.tools.base import is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

type Timestamp = Annotated[str, "ISO 8601 timestamp (e.g., '2024-01-15T10:30:00Z')"]

logger = logging.getLogger(__name__)


@dataclass
class HookTemplate:
    """Represents a hook template from Rossum Store.

    Hook templates provide pre-built extension configurations that can be
    used to quickly create hooks with standard functionality.
    """

    id: int
    url: str
    name: str
    description: str
    type: str
    events: list[str]
    config: dict[str, Any]
    settings_schema: dict[str, Any] | None
    guide: str | None
    use_token_owner: bool


async def _get_hook(client: AsyncRossumAPIClient, hook_id: int) -> Hook:
    hook: Hook = await client.retrieve_hook(hook_id)
    return hook


async def _list_hooks(
    client: AsyncRossumAPIClient,
    queue_id: int | None = None,
    active: bool | None = None,
    first_n: int | None = None,
) -> list[Hook]:
    filters: dict = {}
    if queue_id is not None:
        filters["queue"] = queue_id
    if active is not None:
        filters["active"] = active

    if first_n is not None:
        hooks_iter = client.list_hooks(**filters)
        hooks_list: list[Hook] = []
        n = 0
        while n < first_n:
            hooks_list.append(await anext(hooks_iter))
            n += 1
    else:
        hooks_list = [hook async for hook in client.list_hooks(**filters)]

    return hooks_list


async def _create_hook(
    client: AsyncRossumAPIClient,
    name: str,
    type: HookType,
    queues: list[str] | None = None,
    events: list[str] | None = None,
    config: dict | None = None,
    settings: dict | None = None,
    secret: str | None = None,
) -> Hook | dict:
    if not is_read_write_mode():
        return {"error": "create_hook is not available in read-only mode"}

    hook_data: dict[str, Any] = {"name": name, "type": type, "sideload": ["schemas"]}

    if queues is not None:
        hook_data["queues"] = queues
    if events is not None:
        hook_data["events"] = events
    if config is None:
        config = {}
    if type == "function" and "source" in config:
        config["function"] = config.pop("source")
    if type == "function" and "runtime" not in config:
        config["runtime"] = "python3.12"
    if "timeout_s" in config and config["timeout_s"] > 60:
        config["timeout_s"] = 60
    hook_data["config"] = config
    if settings is not None:
        hook_data["settings"] = settings
    if secret is not None:
        hook_data["secret"] = secret

    hook: Hook = await client.create_new_hook(hook_data)
    return hook


async def _update_hook(
    client: AsyncRossumAPIClient,
    hook_id: int,
    name: str | None = None,
    queues: list[str] | None = None,
    events: list[str] | None = None,
    config: dict | None = None,
    settings: dict | None = None,
    active: bool | None = None,
) -> Hook | dict:
    if not is_read_write_mode():
        return {"error": "update_hook is not available in read-only mode"}

    logger.debug(f"Updating hook: hook_id={hook_id}")

    existing_hook: Hook = await client.retrieve_hook(hook_id)
    hook_data: dict[str, Any] = {
        "name": existing_hook.name,
        "queues": existing_hook.queues,
        "events": list(existing_hook.events),
        "config": dict(existing_hook.config) if existing_hook.config else {},
    }

    if name is not None:
        hook_data["name"] = name
    if queues is not None:
        hook_data["queues"] = queues
    if events is not None:
        hook_data["events"] = events
    if config is not None:
        hook_data["config"] = config
    if settings is not None:
        hook_data["settings"] = settings
    if active is not None:
        hook_data["active"] = active

    updated_hook: Hook = await client.update_part_hook(hook_id, hook_data)
    return updated_hook


async def _list_hook_logs(
    client: AsyncRossumAPIClient,
    hook_id: int | None = None,
    queue_id: int | None = None,
    annotation_id: int | None = None,
    email_id: int | None = None,
    log_level: Literal["INFO", "ERROR", "WARNING"] | None = None,
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
) -> list[HookRunData]:
    filter_mapping: dict[str, Any] = {
        "hook": hook_id,
        "queue": queue_id,
        "annotation": annotation_id,
        "email": email_id,
        "log_level": log_level,
        "status": status,
        "status_code": status_code,
        "request_id": request_id,
        "timestamp_before": timestamp_before,
        "timestamp_after": timestamp_after,
        "start_before": start_before,
        "start_after": start_after,
        "end_before": end_before,
        "end_after": end_after,
        "search": search,
        "page_size": page_size,
    }
    filters = {k: v for k, v in filter_mapping.items() if v is not None}

    return [log async for log in client.list_hook_run_data(**filters)]


async def _list_hook_templates(client: AsyncRossumAPIClient) -> list[HookTemplate]:
    templates: list[HookTemplate] = []
    async for item in client.request_paginated("hook_templates"):
        url = item["url"]
        templates.append(
            HookTemplate(
                id=int(url.split("/")[-1]),
                url=url,
                name=item["name"],
                description=item.get("description", ""),
                type=item["type"],
                events=[],
                config={},
                settings_schema=item.get("settings_schema"),
                guide="<truncated>",
                use_token_owner=item.get("use_token_owner", False),
            )
        )
    return templates


async def _create_hook_from_template(
    client: AsyncRossumAPIClient,
    name: str,
    hook_template_id: int,
    queues: list[str],
    events: list[str] | None = None,
    token_owner: str | None = None,
) -> Hook | dict:
    if not is_read_write_mode():
        return {"error": "create_hook_from_template is not available in read-only mode"}

    logger.debug(f"Creating hook from template: name={name}, template_id={hook_template_id}")

    hook_template_url = f"{client._http_client.base_url.rstrip('/')}/hook_templates/{hook_template_id}"

    hook_data: dict[str, Any] = {"name": name, "hook_template": hook_template_url, "queues": queues}
    if events is not None:
        hook_data["events"] = events
    if token_owner is not None:
        hook_data["token_owner"] = token_owner

    result = await client._http_client.request_json("POST", "hooks/create", json=hook_data)

    if hook_id := result.get("id"):
        hook: Hook = await client.retrieve_hook(hook_id)
        return hook
    return {"error": "Hook wasn't likely created. Hook ID not available."}


def register_hook_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register hook-related tools with the FastMCP server."""

    @mcp.tool(
        description="Retrieve a single hook by ID. Use list_hooks first to get all hooks for a queue - only use get_hook if you need additional details for a specific hook not returned by list_hooks. For Python-based function hooks, the source code is accessible via hook.config['code']."
    )
    async def get_hook(hook_id: int) -> Hook:
        return await _get_hook(client, hook_id)

    @mcp.tool(
        description="List all hooks/extensions for a queue. ALWAYS use this first when you need information about hooks on a queue - it returns complete hook details including code, config, and settings in a single call. Only use get_hook afterward if you need details not present in the list response. For Python-based function hooks, the source code is accessible via hook.config['code']."
    )
    async def list_hooks(
        queue_id: int | None = None, active: bool | None = None, first_n: int | None = None
    ) -> list[Hook]:
        return await _list_hooks(client, queue_id, active, first_n)

    @mcp.tool(
        description="Create a new hook. If token_owner is provided, organization_group_admin users CANNOT be used (API will reject)."
    )
    async def create_hook(
        name: str,
        type: HookType,
        queues: list[str] | None = None,
        events: list[str] | None = None,
        config: dict | None = None,
        settings: dict | None = None,
        secret: str | None = None,
    ) -> Hook | dict:
        return await _create_hook(client, name, type, queues, events, config, settings, secret)

    @mcp.tool(
        description="Update an existing hook. Use this to modify hook properties like name, queues, config, events, or settings. Only provide the fields you want to change - other fields will remain unchanged."
    )
    async def update_hook(
        hook_id: int,
        name: str | None = None,
        queues: list[str] | None = None,
        events: list[str] | None = None,
        config: dict | None = None,
        settings: dict | None = None,
        active: bool | None = None,
    ) -> Hook | dict:
        return await _update_hook(client, hook_id, name, queues, events, config, settings, active)

    @mcp.tool(
        description="List hook execution logs. Use this to debug hook executions, monitor performance, and troubleshoot errors. Logs are retained for 7 days. Returns at most 100 logs per call."
    )
    async def list_hook_logs(
        hook_id: int | None = None,
        queue_id: int | None = None,
        annotation_id: int | None = None,
        email_id: int | None = None,
        log_level: Literal["INFO", "ERROR", "WARNING"] | None = None,
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
    ) -> list[HookRunData]:
        return await _list_hook_logs(
            client,
            hook_id,
            queue_id,
            annotation_id,
            email_id,
            log_level,
            status,
            status_code,
            request_id,
            timestamp_before,
            timestamp_after,
            start_before,
            start_after,
            end_before,
            end_after,
            search,
            page_size,
        )

    @mcp.tool(
        description="List available hook templates from Rossum Store. Hook templates provide pre-built extension configurations (e.g., data validation, field mapping, notifications) that can be used to quickly create hooks instead of writing code from scratch. Use list_hook_templates first to find a suitable template, then use create_hook_from_template to create a hook based on that template."
    )
    async def list_hook_templates() -> list[HookTemplate]:
        return await _list_hook_templates(client)

    @mcp.tool(
        description="Create a hook from a Rossum Store template. Uses pre-built configurations from the Rossum Store. The 'events' parameter is optional and can override template defaults. If the template has 'use_token_owner=True', a valid 'token_owner' user URL is required - use list_users to find one. CRITICAL RESTRICTION: organization_group_admin users are FORBIDDEN as token_owner - the API returns HTTP 400 error."
    )
    async def create_hook_from_template(
        name: str,
        hook_template_id: int,
        queues: list[str],
        events: list[str] | None = None,
        token_owner: str | None = None,
    ) -> Hook | dict:
        return await _create_hook_from_template(client, name, hook_template_id, queues, events, token_owner)
