from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.models.workspace import Workspace

from rossum_mcp.tools.base import build_resource_url

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _create_workspace(
    client: AsyncRossumAPIClient, base_url: str, name: str, organization_id: int, metadata: dict | None = None
) -> Workspace | dict:
    organization_url = build_resource_url(base_url, "organizations", organization_id)
    logger.debug(f"Creating workspace: name={name}, organization_id={organization_id}, metadata={metadata}")
    workspace_data: dict = {"name": name, "organization": organization_url}
    if metadata is not None:
        workspace_data["metadata"] = metadata

    workspace: Workspace = await client.create_new_workspace(workspace_data)
    logger.info(f"Successfully created workspace: id={workspace.id}, name={workspace.name}")
    return workspace


def register_workspace_tools(mcp: FastMCP, client: AsyncRossumAPIClient, base_url: str) -> None:
    @mcp.tool(
        description="Create a new workspace.",
        tags={"workspaces", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_workspace(name: str, organization_id: int, metadata: dict | None = None) -> Workspace | dict:
        return await _create_workspace(client, base_url, name, organization_id, metadata)
