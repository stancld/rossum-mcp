"""Base utilities for Rossum MCP tools."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

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
