"""Hook operations handler for Rossum MCP Server"""

from __future__ import annotations

import dataclasses
import logging
import os
from typing import TYPE_CHECKING, Literal

from mcp.types import Tool

from rossum_mcp.handlers.base import BaseHandler

if TYPE_CHECKING:
    from typing import Any

    from rossum_api.models.hook import Hook

logger = logging.getLogger(__name__)


class HooksHandler(BaseHandler):
    """Handler for hook-related operations"""

    @classmethod
    def get_tool_definitions(cls) -> list[Tool]:
        """Get list of tool definitions for hook operations."""
        return [
            Tool(
                name="list_hooks",
                description="List all hooks/extensions. Returns: count, results array with hook details (id, name, url, active, config, test, guide, read_more_url, extension_image_url, type, metadata, queues, run_after, events, settings, settings_schema, secrets, extension_source, sideload, token_owner, token_lifetime_s, description).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "queue_id": {
                            "type": ["integer", "null"],
                            "description": "Optional queue ID to filter hooks by queue",
                        },
                        "active": {
                            "type": ["boolean", "null"],
                            "description": "Optional filter by active status (true/false)",
                        },
                        "first_n": {
                            "type": ["integer", "null"],
                            "description": "Optional parameter defining max number of outputs. Useful when getting just an example.",
                        },
                    },
                },
            ),
            Tool(
                name="create_hook",
                description="Create a new hook. Returns: id, name, url, active, config, test, guide, read_more_url, extension_image_url, type, metadata, queues, run_after, events, settings, settings_schema, secrets, extension_source, sideload, token_owner, token_lifetime_s, description, message.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Hook name",
                        },
                        "type": {
                            "type": "string",
                            "description": "Definition of whether a hook will call a url endpoint or call a python function.",
                            "enum": ["webhook", "function"],
                        },
                        "queues": {
                            "type": ["array", "null"],
                            "items": {"type": "string"},
                            "description": "List of queue URLs to attach the hook to. If not provided, hook applies to all queues. Format: ['https://api.elis.rossum.ai/v1/queues/12345']",
                        },
                        "events": {
                            "type": ["array", "null"],
                            "items": {"type": "string"},
                            "description": "List of events that trigger the hook. Common events: annotation_status, annotation_content, annotation_export, datapoint_value, annotation_content.initialize, annotation_content.confirm, annotation_content.export",
                        },
                        "config": {
                            "type": ["object", "null"],
                            "description": "Configuration dict - code for a function or URL for a webhook",
                        },
                        "settings": {
                            "type": ["object", "null"],
                            "description": "Specific settings that will be included in the payload when executing the hook.",
                        },
                        "secret": {
                            "type": ["string", "null"],
                            "description": "Secret key for securing webhook requests",
                        },
                    },
                    "required": ["name"],
                },
            ),
        ]

    async def list_hooks(
        self, queue_id: int | None = None, active: bool | None = None, first_n: int | None = None
    ) -> dict:
        """List all hooks/extensions, optionally filtered by queue and active status.

        Args:
            queue_id: Optional queue ID to filter hooks by queue
            active: Optional boolean to filter by active status
            first_n: Optional parameter defining max number of outputs

        Returns:
            Dictionary containing count and results list of hooks
        """
        logger.debug(f"Listing hooks: queue_id={queue_id}, active={active}")

        # Build filter parameters
        filters: dict = {}
        if queue_id is not None:
            filters["queue"] = queue_id
        if active is not None:
            filters["active"] = active

        if first_n is not None:
            hooks_iter = self.client.list_hooks(**filters)
            hooks_list: list[Hook] = []
            n = 0
            while n < first_n:
                hooks_list.append(await anext(hooks_iter))
                n + 1
        else:
            hooks_list = [hook async for hook in self.client.list_hooks(**filters)]

        return {"count": len(hooks_list), "results": [dataclasses.asdict(hook) for hook in hooks_list]}

    async def create_hook(
        self,
        name: str,
        type: Literal["webhook", "function"],
        queues: list[str] | None = None,
        events: list[str] | None = None,
        config: dict | None = None,
        settings: dict | None = None,
        secret: str | None = None,
    ) -> dict:
        """Create a new hook.

        Args:
            name: Hook name
            type: Definition of whether a hook will call a url endpoint or call a python function.
            queues: List of queue URLs to attach the hook to. If not provided, hook will apply to all queues.
                Format: ["https://api.elis.rossum.ai/v1/queues/12345", ...]
            events: List of events that trigger the hook. Common events:
                - "annotation_status"
                - "annotation_content"
                - "annotation_export"
                - "datapoint_value"
            config: Definition of whether a hook will call a url endpoint or call a python function.
            settings: Specific settings that will be included in the payload when executing the hook.
            secret: Secret key for securing webhook requests
            response_event: Configuration for response event handling

        Returns:
            Dictionary containing created hook details

        Example:
            create_hook(
                name="Splitting & Sortuing",
                queues=["https://api.elis.rossum.ai/v1/queues/12345"],
                events=["annotation_content.initialize", "annotation_content.confirm"],
                config={"runtime": "python3.12", "code": "import json"}
                settings: {"sorting_queues": {"A": 1, "B": 2}}
            )
        """
        logger.debug(f"Creating hook: name={name}")

        hook_data: dict[str, Any] = {
            "name": name,
            "type": type,
            "sideload": ["schemas"],
            "token_owner": os.environ["API_TOKEN_OWNER"],
        }

        # Add optional fields if provided
        if queues is not None:
            hook_data["queues"] = queues
        if events is not None:
            hook_data["events"] = events
        if config is None:
            config = {}
        # Claude sometimes fail :)
        if type == "function" and "source" in config:
            config["function"] = config.pop("source")
        if type == "function" and "runtime" not in config:
            config["runtime"] = "python3.12"
        hook_data["config"] = config
        if settings is not None:
            hook_data["settings"] = settings
        if secret is not None:
            hook_data["secret"] = secret

        hook: Hook = await self.client.create_new_hook(hook_data)

        result = dataclasses.asdict(hook)
        result["message"] = f"Hook '{hook.name}' created successfully with ID {hook.id}"
        return result
