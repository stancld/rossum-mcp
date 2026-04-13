from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_mcp.tools.create.annotations import register_annotation_tools
from rossum_mcp.tools.create.email_templates import register_email_template_tools
from rossum_mcp.tools.create.engines import register_engine_tools
from rossum_mcp.tools.create.hooks import register_hook_tools
from rossum_mcp.tools.create.queues import register_queue_tools
from rossum_mcp.tools.create.rules import register_rule_tools
from rossum_mcp.tools.create.users import register_user_tools
from rossum_mcp.tools.create.workspaces import register_workspace_tools

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient


def register_create_tools(mcp: FastMCP, client: AsyncRossumAPIClient, base_url: str) -> None:
    register_annotation_tools(mcp, client, base_url)
    register_queue_tools(mcp, client, base_url)
    register_engine_tools(mcp, client, base_url)
    register_hook_tools(mcp, client)
    register_rule_tools(mcp, client, base_url)
    register_user_tools(mcp, client)
    register_workspace_tools(mcp, client, base_url)
    register_email_template_tools(mcp, client, base_url)
