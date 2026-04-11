from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_mcp.tools.get.annotations import register_annotation_tools
from rossum_mcp.tools.get.engines import register_engine_tools
from rossum_mcp.tools.get.handler import register_core_tools
from rossum_mcp.tools.get.schemas import register_schema_tools

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient


def register_get_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    register_core_tools(mcp, client)
    register_annotation_tools(mcp, client)
    register_schema_tools(mcp, client)
    register_engine_tools(mcp, client)
