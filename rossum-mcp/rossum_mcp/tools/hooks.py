"""Hook tools for Rossum MCP Server."""

from __future__ import annotations

import dataclasses
import logging
import os
from typing import TYPE_CHECKING, Any, Literal

from rossum_mcp.tools.base import is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient
    from rossum_api.models.hook import Hook

logger = logging.getLogger(__name__)


def register_hook_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:  # noqa: C901
    """Register hook-related tools with the FastMCP server."""

    @mcp.tool(
        description="Retrieve hook details. Returns: id, name, url, active, config, test, guide, read_more_url, extension_image_url, type, metadata, queues, run_after, events, settings, settings_schema, secrets, extension_source, sideload, token_owner, token_lifetime_s, description."
    )
    async def get_hook(hook_id: int) -> dict:
        """Retrieve hook details."""
        logger.debug(f"Retrieving hook: hook_id={hook_id}")
        hook: Hook = await client.retrieve_hook(hook_id)
        return dataclasses.asdict(hook)

    @mcp.tool(
        description="List all hooks/extensions. Returns: count, results array with hook details (id, name, url, active, config, test, guide, read_more_url, extension_image_url, type, metadata, queues, run_after, events, settings, settings_schema, secrets, extension_source, sideload, token_owner, token_lifetime_s, description)."
    )
    async def list_hooks(queue_id: int | None = None, active: bool | None = None, first_n: int | None = None) -> dict:
        """List all hooks/extensions, optionally filtered by queue and active status."""
        logger.debug(f"Listing hooks: queue_id={queue_id}, active={active}")
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

        return {"count": len(hooks_list), "results": [dataclasses.asdict(hook) for hook in hooks_list]}

    @mcp.tool(
        description="Create a new hook. Returns: id, name, url, active, config, test, guide, read_more_url, extension_image_url, type, metadata, queues, run_after, events, settings, settings_schema, secrets, extension_source, sideload, token_owner, token_lifetime_s, description, message."
    )
    async def create_hook(
        name: str,
        type: Literal["webhook", "function"],
        queues: list[str] | None = None,
        events: list[str] | None = None,
        config: dict | None = None,
        settings: dict | None = None,
        secret: str | None = None,
    ) -> dict:
        """Create a new hook."""
        if not is_read_write_mode():
            return {"error": "create_hook is not available in read-only mode"}

        logger.debug(f"Creating hook: name={name}")
        hook_data: dict[str, Any] = {
            "name": name,
            "type": type,
            "sideload": ["schemas"],
            "token_owner": os.environ["API_TOKEN_OWNER"],
        }

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
        hook_data["config"] = config
        if settings is not None:
            hook_data["settings"] = settings
        if secret is not None:
            hook_data["secret"] = secret

        hook: Hook = await client.create_new_hook(hook_data)
        result = dataclasses.asdict(hook)
        result["message"] = f"Hook '{hook.name}' created successfully with ID {hook.id}"
        return result
