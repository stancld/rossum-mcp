"""Hook tools for Rossum MCP Server."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Literal

from rossum_api.models.hook import Hook  # noqa: TC002 - needed at runtime for FastMCP

from rossum_mcp.tools.base import is_read_write_mode

# HookRunData is from ds-feat-hook-logs branch (not yet released)
try:
    from rossum_api.models.hook import HookRunData  # type: ignore[attr-defined]
except ImportError:
    HookRunData = None  # type: ignore[misc, assignment]

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def register_hook_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:  # noqa: C901
    """Register hook-related tools with the FastMCP server."""

    @mcp.tool(
        description="Retrieve a single hook by ID. Use list_hooks first to get all hooks for a queue - only use get_hook if you need additional details for a specific hook not returned by list_hooks. For Python-based function hooks, the source code is accessible via hook.config['code']."
    )
    async def get_hook(hook_id: int) -> Hook:
        """Retrieve hook details."""
        logger.debug(f"Retrieving hook: hook_id={hook_id}")
        hook: Hook = await client.retrieve_hook(hook_id)
        return hook

    @mcp.tool(
        description="List all hooks/extensions for a queue. ALWAYS use this first when you need information about hooks on a queue - it returns complete hook details including code, config, and settings in a single call. Only use get_hook afterward if you need details not present in the list response. For Python-based function hooks, the source code is accessible via hook.config['code']."
    )
    async def list_hooks(
        queue_id: int | None = None, active: bool | None = None, first_n: int | None = None
    ) -> list[Hook]:
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

        logger.info(hooks_list)
        return hooks_list

    @mcp.tool(description="Create a new hook.")
    async def create_hook(
        name: str,
        type: Literal["webhook", "function", "job"],
        queues: list[str] | None = None,
        events: list[str] | None = None,
        config: dict | None = None,
        settings: dict | None = None,
        secret: str | None = None,
    ) -> Hook | dict:
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
        return hook

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
        timestamp_before: str | None = None,
        timestamp_after: str | None = None,
        start_before: str | None = None,
        start_after: str | None = None,
        end_before: str | None = None,
        end_after: str | None = None,
        search: str | None = None,
        page_size: int | None = None,
    ) -> list[HookRunData]:
        """List hook execution logs with optional filters.

        Args:
            hook_id: Filter by hook ID.
            queue_id: Filter by queue ID.
            annotation_id: Filter by annotation ID.
            email_id: Filter by email ID.
            log_level: Filter by log level (INFO, ERROR, WARNING).
            status: Filter by execution status.
            status_code: Filter by HTTP status code.
            request_id: Filter by request ID.
            timestamp_before: ISO 8601 timestamp, filter logs triggered before this time.
            timestamp_after: ISO 8601 timestamp, filter logs triggered after this time.
            start_before: ISO 8601 timestamp, filter logs started before this time.
            start_after: ISO 8601 timestamp, filter logs started after this time.
            end_before: ISO 8601 timestamp, filter logs ended before this time.
            end_after: ISO 8601 timestamp, filter logs ended after this time.
            search: Full-text search across log messages.
            page_size: Number of results per page (default 100, max 100).
        """
        logger.debug(f"Listing hook logs: hook_id={hook_id}, queue_id={queue_id}")
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

        # list_hook_run_data is available from ds-feat-hook-logs branch
        return [
            log
            async for log in client.list_hook_run_data(**filters)  # type: ignore[attr-defined]
        ]
