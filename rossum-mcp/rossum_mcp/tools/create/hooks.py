from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastmcp.exceptions import ToolError
from rossum_api.models.hook import Hook, HookEventAndAction, HookType

from rossum_mcp.models.hook import (
    HookSideload,  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
)
from rossum_mcp.tools.base import build_resource_url
from rossum_mcp.tools.validation import validate_hook_events

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _create_hook(
    client: AsyncRossumAPIClient,
    name: str,
    type: HookType,
    queues: list[str] | None = None,
    events: list[HookEventAndAction] | None = None,
    config: dict | None = None,
    settings: dict | None = None,
    secrets: dict[str, str] | None = None,
    token_owner: str | None = None,
    run_after: list[str] | None = None,
    sideload: list[HookSideload] | None = None,
) -> Hook:
    hook_data: dict[str, Any] = {"name": name, "type": type}

    if queues is not None:
        hook_data["queues"] = queues
    if events is not None:
        hook_data["events"] = validate_hook_events(events)
    if config is None:
        config = {}
    if type == "function" and "source" in config:
        config["code"] = config.pop("source")
    if type == "function" and "runtime" not in config:
        config["runtime"] = "python3.12"
    if "timeout_s" in config and config["timeout_s"] > 60:
        config["timeout_s"] = 60
    hook_data["config"] = config
    if settings is not None:
        hook_data["settings"] = settings
    if secrets is not None:
        hook_data["secrets"] = secrets
    if token_owner is not None:
        hook_data["token_owner"] = token_owner
    if run_after is not None:
        hook_data["run_after"] = run_after
    if sideload is not None:
        hook_data["sideload"] = sideload

    hook: Hook = await client.create_new_hook(hook_data)
    return hook


async def _create_hook_from_template(
    client: AsyncRossumAPIClient,
    name: str,
    hook_template_id: int,
    queues: list[str],
    events: list[HookEventAndAction] | None = None,
    token_owner: str | None = None,
) -> Hook:
    logger.debug(f"Creating hook from template: name={name}, template_id={hook_template_id}")

    hook_template_url = build_resource_url(
        client._http_client.base_url.rstrip("/"), "hook_templates", hook_template_id
    )

    hook_data: dict[str, Any] = {"name": name, "hook_template": hook_template_url, "queues": queues}
    if events is not None:
        hook_data["events"] = validate_hook_events(events)
    if token_owner is not None:
        hook_data["token_owner"] = token_owner

    result = await client._http_client.request_json("POST", "hooks/create", json=hook_data)

    if hook_id := result.get("id"):
        hook: Hook = await client.retrieve_hook(hook_id)
        return hook
    raise ToolError("Hook wasn't likely created. Hook ID not available.")
