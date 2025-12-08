"""Workspace tools for Rossum MCP Server."""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from rossum_mcp.tools.base import build_resource_url, is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient
    from rossum_api.models.workspace import Workspace

logger = logging.getLogger(__name__)


def register_workspace_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register workspace-related tools with the FastMCP server."""

    @mcp.tool(
        description="Retrieve workspace details. Returns: id, name, url, organization, queues, autopilot, metadata."
    )
    async def get_workspace(workspace_id: int) -> dict:
        """Retrieve workspace details."""
        logger.debug(f"Retrieving workspace: workspace_id={workspace_id}")
        workspace: Workspace = await client.retrieve_workspace(workspace_id)
        return dataclasses.asdict(workspace)

    @mcp.tool(
        description="List all workspaces with optional filters. Returns: count, results array with workspace details (id, name, url, organization, queues)."
    )
    async def list_workspaces(organization_id: int | None = None, name: str | None = None) -> dict:
        """List all workspaces with optional filters."""
        logger.debug(f"Listing workspaces: organization_id={organization_id}, name={name}")
        filters: dict[str, int | str] = {}
        if organization_id is not None:
            filters["organization"] = organization_id
        if name is not None:
            filters["name"] = name

        workspaces_list = [
            workspace
            async for workspace in client.list_workspaces(**filters)  # type: ignore[arg-type]
        ]
        return {
            "count": len(workspaces_list),
            "results": [dataclasses.asdict(workspace) for workspace in workspaces_list],
        }

    @mcp.tool(description="Create a new workspace. Returns: id, name, url, organization, queues, message.")
    async def create_workspace(name: str, organization_id: int, metadata: dict | None = None) -> dict:
        """Create a new workspace."""
        if not is_read_write_mode():
            return {"error": "create_workspace is not available in read-only mode"}

        logger.debug(f"Creating workspace: name={name}, organization_id={organization_id}, metadata={metadata}")
        workspace_data: dict = {
            "name": name,
            "organization": build_resource_url("organizations", organization_id),
        }
        if metadata is not None:
            workspace_data["metadata"] = metadata

        workspace: Workspace = await client.create_new_workspace(workspace_data)
        result = dataclasses.asdict(workspace)
        result["message"] = f"Workspace '{workspace.name}' created successfully with ID {workspace.id}"
        return result
