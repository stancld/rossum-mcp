#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from fastmcp import FastMCP
from rossum_api import AsyncRossumAPIClient
from rossum_api.dtos import Token

from rossum_mcp.logging_config import setup_logging
from rossum_mcp.tools import (
    register_create_tools,
    register_delete_tools,
    register_discovery_tools,
    register_get_tools,
    register_update_tools,
)
from rossum_mcp.tools.base import VALID_MODES

if TYPE_CHECKING:
    from rossum_mcp.tools.base import McpMode

logger = logging.getLogger(__name__)


def create_app() -> FastMCP:
    """Create and configure the MCP server.

    Reads configuration from environment variables:

    - ``ROSSUM_API_BASE_URL`` (required)
    - ``ROSSUM_API_TOKEN`` (required)
    - ``ROSSUM_MCP_MODE`` (optional, default: read-write)
    - ``ROSSUM_MCP_LOG_LEVEL`` (optional, default: INFO)
    """
    setup_logging(log_level=os.environ.get("ROSSUM_MCP_LOG_LEVEL", "INFO"))

    base_url = os.environ["ROSSUM_API_BASE_URL"].rstrip("/")
    api_token = os.environ["ROSSUM_API_TOKEN"]
    mcp_mode = os.environ.get("ROSSUM_MCP_MODE", "read-write").lower()

    if mcp_mode not in VALID_MODES:
        raise ValueError(f"Invalid ROSSUM_MCP_MODE: {mcp_mode}. Must be one of: {VALID_MODES}")
    validated_mode: McpMode = mcp_mode  # type: ignore[assignment] - validated above

    logger.info(f"Rossum MCP Server starting in {validated_mode} mode")

    mcp = FastMCP("rossum-mcp-server")
    client = AsyncRossumAPIClient(base_url=base_url, credentials=Token(token=api_token))

    register_discovery_tools(mcp, validated_mode)
    register_get_tools(mcp, client)
    register_delete_tools(mcp, client)
    register_create_tools(mcp, client, base_url)
    register_update_tools(mcp, client, base_url)

    # Enforce read-only mode by hiding write tools via FastMCP visibility
    if validated_mode == "read-only":
        mcp.disable(tags={"write"})

    return mcp


def main() -> None:
    """Main entry point for console script."""
    app = create_app()
    app.run()


if __name__ == "__main__":
    main()
