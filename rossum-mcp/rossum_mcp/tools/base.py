"""Base utilities for Rossum MCP tools."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Any

logger = logging.getLogger(__name__)

BASE_URL = os.environ.get("ROSSUM_API_BASE_URL", "").rstrip("/")
MODE = os.environ.get("ROSSUM_MCP_MODE", "read-write").lower()

# Marker used to indicate omitted fields in list responses
TRUNCATED_MARKER = "<omitted>"


def build_resource_url(resource_type: str, resource_id: int) -> str:
    """Build a full URL for a Rossum API resource."""
    return f"{BASE_URL}/{resource_type}/{resource_id}"


def is_read_write_mode() -> bool:
    """Check if server is in read-write mode."""
    return MODE == "read-write"


def truncate_dict_fields(data: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """Truncate specified fields in a dictionary to save context.

    Returns a new dictionary with specified fields replaced by TRUNCATED_MARKER.
    """
    if not data:
        return data

    result = dict(data)
    for field in fields:
        if field in result:
            result[field] = TRUNCATED_MARKER
    return result


async def delete_resource(
    resource_type: str,
    resource_id: int,
    delete_fn: Callable[[int], Awaitable[None]],
    success_message: str | None = None,
) -> dict:
    """Generic delete operation with read-only mode check.

    Args:
        resource_type: Name of the resource (e.g., "queue", "workspace")
        resource_id: ID of the resource to delete
        delete_fn: Async function that performs the deletion
        success_message: Custom success message. If None, uses default format.

    Returns:
        Dict with "message" on success or "error" in read-only mode.
    """
    tool_name = f"delete_{resource_type}"
    if not is_read_write_mode():
        return {"error": f"{tool_name} is not available in read-only mode"}

    logger.debug(f"Deleting {resource_type}: {resource_type}_id={resource_id}")
    await delete_fn(resource_id)

    if success_message is None:
        success_message = f"{resource_type.title()} {resource_id} deleted successfully"
    return {"message": success_message}
