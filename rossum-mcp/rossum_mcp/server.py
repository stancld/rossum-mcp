#!/usr/bin/env python3
"""Rossum MCP Server

Provides tools for uploading documents and retrieving annotations using Rossum API.
Built with FastMCP for a cleaner, more Pythonic interface.
"""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP
from rossum_api import AsyncRossumAPIClient
from rossum_api.dtos import Token

from rossum_mcp.logging_config import setup_logging
from rossum_mcp.tools import (
    register_annotation_tools,
    register_document_relation_tools,
    register_engine_tools,
    register_hook_tools,
    register_queue_tools,
    register_relation_tools,
    register_rule_tools,
    register_schema_tools,
    register_workspace_tools,
)

setup_logging(
    app_name="rossum-mcp-server",
    log_level="DEBUG",
    log_file="/tmp/rossum_mcp_debug.log",
    use_console=False,
)

logger = logging.getLogger(__name__)

BASE_URL = os.environ["ROSSUM_API_BASE_URL"]
API_TOKEN = os.environ["ROSSUM_API_TOKEN"]
MODE = os.environ.get("ROSSUM_MCP_MODE", "read-write").lower()

if MODE not in ("read-only", "read-write"):
    raise ValueError(f"Invalid ROSSUM_MCP_MODE: {MODE}. Must be 'read-only' or 'read-write'")

logger.info(f"Rossum MCP Server starting in {MODE} mode")

mcp = FastMCP("rossum-mcp-server")
client = AsyncRossumAPIClient(base_url=BASE_URL, credentials=Token(token=API_TOKEN))

register_annotation_tools(mcp, client)
register_queue_tools(mcp, client)
register_schema_tools(mcp, client)
register_engine_tools(mcp, client)
register_hook_tools(mcp, client)
register_document_relation_tools(mcp, client)
register_relation_tools(mcp, client)
register_rule_tools(mcp, client)
register_workspace_tools(mcp, client)


def main() -> None:
    """Main entry point for console script."""
    mcp.run()


if __name__ == "__main__":
    main()
