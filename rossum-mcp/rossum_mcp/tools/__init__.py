"""FastMCP tool modules for Rossum MCP Server."""

from __future__ import annotations

from rossum_mcp.tools.annotations import register_annotation_tools
from rossum_mcp.tools.catalog import (
    TOOL_CATALOG,
    ToolCategory,
    ToolInfo,
    get_catalog_summary,
)
from rossum_mcp.tools.discovery import register_discovery_tools
from rossum_mcp.tools.document_relations import register_document_relation_tools
from rossum_mcp.tools.email_templates import register_email_template_tools
from rossum_mcp.tools.engines import register_engine_tools
from rossum_mcp.tools.hooks import register_hook_tools
from rossum_mcp.tools.queues import register_queue_tools
from rossum_mcp.tools.relations import register_relation_tools
from rossum_mcp.tools.rules import register_rule_tools
from rossum_mcp.tools.schemas import register_schema_tools
from rossum_mcp.tools.users import register_user_tools
from rossum_mcp.tools.workspaces import register_workspace_tools

__all__ = [
    "TOOL_CATALOG",
    "ToolCategory",
    "ToolInfo",
    "get_catalog_summary",
    "register_annotation_tools",
    "register_discovery_tools",
    "register_document_relation_tools",
    "register_email_template_tools",
    "register_engine_tools",
    "register_hook_tools",
    "register_queue_tools",
    "register_relation_tools",
    "register_rule_tools",
    "register_schema_tools",
    "register_user_tools",
    "register_workspace_tools",
]
