"""Base utilities for Rossum MCP tools."""

from __future__ import annotations

import os

BASE_URL = os.environ.get("ROSSUM_API_BASE_URL", "").rstrip("/")
MODE = os.environ.get("ROSSUM_MCP_MODE", "read-write").lower()


def build_resource_url(resource_type: str, resource_id: int) -> str:
    """Build a full URL for a Rossum API resource."""
    return f"{BASE_URL}/{resource_type}/{resource_id}"


def is_read_write_mode() -> bool:
    """Check if server is in read-write mode."""
    return MODE == "read-write"
