from __future__ import annotations

from fastmcp import FastMCP
from rossum_api import AsyncRossumAPIClient

from rossum_mcp.tools.update.annotations import register_annotation_tools
from rossum_mcp.tools.update.engines import register_engine_tools
from rossum_mcp.tools.update.hooks import register_hook_tools
from rossum_mcp.tools.update.queues import register_queue_tools
from rossum_mcp.tools.update.rules import register_rule_tools
from rossum_mcp.tools.update.schemas.handler import register_schema_tools
from rossum_mcp.tools.update.users import register_user_tools


def register_update_tools(mcp: FastMCP, client: AsyncRossumAPIClient, base_url: str) -> None:
    register_annotation_tools(mcp, client)
    register_queue_tools(mcp, client)
    register_schema_tools(mcp, client)
    register_engine_tools(mcp, client)
    register_hook_tools(mcp, client)
    register_rule_tools(mcp, client, base_url)
    register_user_tools(mcp, client)
