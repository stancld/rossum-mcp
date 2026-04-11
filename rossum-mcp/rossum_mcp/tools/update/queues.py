from __future__ import annotations

import logging
from typing import cast

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from rossum_api import AsyncRossumAPIClient
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.queue import Queue

from rossum_mcp.tools.update.models import (
    QueueUpdateData,  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
)

logger = logging.getLogger(__name__)

_VALID_META_NAMES = {
    "status",
    "original_file_name",
    "labels",
    "assignees",
    "queue",
    "details",
    "created_at",
    "modified_at",
    "confirmed_at",
    "exported_at",
    "rejected_at",
    "deleted_at",
    "assigned_at",
    "modifier",
    "confirmed_by",
    "exported_by",
    "export_failed_at",
    "rejected_by",
    "deleted_by",
}


def _validate_queue_column_settings(queue_data: QueueUpdateData) -> str | None:
    columns = queue_data.get("settings", {}).get("annotation_list_table", {}).get("columns", [])
    if not isinstance(columns, list):
        return None

    invalid = []
    for col in columns:
        if isinstance(col, dict) and col.get("column_type") == "meta":
            meta_name = col.get("meta_name")
            if meta_name and meta_name not in _VALID_META_NAMES:
                invalid.append(meta_name)

    if invalid:
        return f"Invalid meta_name value(s): {invalid}. Valid values: {sorted(_VALID_META_NAMES)}"
    return None


async def _update_queue(client: AsyncRossumAPIClient, queue_id: int, queue_data: QueueUpdateData) -> Queue:
    validation_error = _validate_queue_column_settings(queue_data)
    if validation_error:
        raise ToolError(validation_error)

    logger.debug(f"Updating queue: queue_id={queue_id}, data={queue_data}")
    updated_queue_data = await client._http_client.update(Resource.Queue, queue_id, dict(queue_data))
    return cast("Queue", client._deserializer(Resource.Queue, updated_queue_data))


def register_queue_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Update queue settings.",
        tags={"queues", "write"},
        annotations={"readOnlyHint": False},
    )
    async def update_queue(queue_id: int, queue_data: QueueUpdateData) -> Queue | dict:
        return await _update_queue(client, queue_id, queue_data)
