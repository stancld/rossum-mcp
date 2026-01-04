"""Workspace tools for Rossum MCP Server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.models.workspace import Workspace  # noqa: TC002 - needed at runtime for FastMCP

from rossum_mcp.tools.base import build_resource_url, is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_workspace(client: AsyncRossumAPIClient, workspace_id: int) -> Workspace:
    logger.debug(f"Retrieving workspace: workspace_id={workspace_id}")
    workspace: Workspace = await client.retrieve_workspace(workspace_id)
    return workspace


async def _list_workspaces(
    client: AsyncRossumAPIClient, organization_id: int | None = None, name: str | None = None
) -> list[Workspace]:
    logger.debug(f"Listing workspaces: organization_id={organization_id}, name={name}")
    filters: dict[str, int | str] = {}
    if organization_id is not None:
        filters["organization"] = organization_id
    if name is not None:
        filters["name"] = name

    return [
        workspace
        async for workspace in client.list_workspaces(**filters)  # type: ignore[arg-type]
    ]


async def _create_workspace(
    client: AsyncRossumAPIClient, name: str, organization_id: int, metadata: dict | None = None
) -> Workspace | dict:
    if not is_read_write_mode():
        return {"error": "create_workspace is not available in read-only mode"}

    organization_url = build_resource_url("organizations", organization_id)
    logger.info(
        f"Creating workspace: name={name}, organization_id={organization_id}, "
        f"organization_url={organization_url}, metadata={metadata}"
    )
    workspace_data: dict = {
        "name": name,
        "organization": organization_url,
    }
    if metadata is not None:
        workspace_data["metadata"] = metadata

    logger.debug(f"Workspace creation payload: {workspace_data}")
    workspace: Workspace = await client.create_new_workspace(workspace_data)
    logger.info(f"Successfully created workspace: id={workspace.id}, name={workspace.name}")
    return workspace


def register_workspace_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register workspace-related tools with the FastMCP server."""

    @mcp.tool(description="Retrieve workspace details.")
    async def get_workspace(workspace_id: int) -> Workspace:
        return await _get_workspace(client, workspace_id)

    @mcp.tool(description="List all workspaces with optional filters.")
    async def list_workspaces(organization_id: int | None = None, name: str | None = None) -> list[Workspace]:
        return await _list_workspaces(client, organization_id, name)

    @mcp.tool(description="Create a new workspace.")
    async def create_workspace(name: str, organization_id: int, metadata: dict | None = None) -> Workspace | dict:
        return await _create_workspace(client, name, organization_id, metadata)
