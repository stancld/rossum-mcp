"""Workspace operations handler for Rossum MCP Server"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp.types import Tool

from rossum_mcp.handlers.base import BaseHandler

if TYPE_CHECKING:
    from rossum_api.models.workspace import Workspace

logger = logging.getLogger(__name__)


class WorkspacesHandler(BaseHandler):
    """Handler for workspace-related operations"""

    @classmethod
    def get_tool_definitions(cls) -> list[Tool]:
        """Get list of tool definitions for workspace operations."""
        return [
            Tool(
                name="get_workspace",
                description="Retrieve workspace details. Returns: id, name, url, organization, queues, autopilot, metadata.",
                inputSchema={
                    "type": "object",
                    "properties": {"workspace_id": {"type": "integer", "description": "Workspace ID"}},
                    "required": ["workspace_id"],
                },
            ),
            Tool(
                name="list_workspaces",
                description="List all workspaces with optional filters. Returns: list of workspaces with id, name, url, organization, queues.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "organization_id": {
                            "type": ["integer", "null"],
                            "description": "Optional organization ID filter",
                        },
                        "name": {
                            "type": ["string", "null"],
                            "description": "Optional name filter",
                        },
                    },
                },
            ),
            Tool(
                name="create_workspace",
                description="Create a new workspace. Returns: id, name, url, organization, queues, message.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Workspace name"},
                        "organization_id": {"type": "integer", "description": "Organization ID"},
                        "metadata": {
                            "type": ["object", "null"],
                            "description": "Optional metadata dictionary",
                        },
                    },
                    "required": ["name", "organization_id"],
                },
            ),
        ]

    async def get_workspace(self, workspace_id: int) -> dict:
        """Retrieve workspace details.

        Args:
            workspace_id: Rossum workspace ID to retrieve

        Returns:
            Dictionary containing workspace details
        """
        logger.debug(f"Retrieving workspace: workspace_id={workspace_id}")

        workspace: Workspace = await self.client.retrieve_workspace(workspace_id)
        return {
            "id": workspace.id,
            "name": workspace.name,
            "url": workspace.url,
            "organization": workspace.organization,
            "queues": workspace.queues,
            "autopilot": workspace.autopilot,
            "metadata": workspace.metadata,
        }

    async def list_workspaces(self, organization_id: int | None = None, name: str | None = None) -> dict:
        """List all workspaces with optional filters.

        Args:
            organization_id: Optional organization ID filter
            name: Optional name filter

        Returns:
            Dictionary containing list of workspaces
        """
        logger.debug(f"Listing workspaces: organization_id={organization_id}, name={name}")

        filters: dict[str, int | str] = {}
        if organization_id is not None:
            filters["organization"] = organization_id
        if name is not None:
            filters["name"] = name

        workspaces_list = []
        async for workspace in self.client.list_workspaces(**filters):  # type: ignore[arg-type]
            workspaces_list.append(
                {
                    "id": workspace.id,
                    "name": workspace.name,
                    "url": workspace.url,
                    "organization": workspace.organization,
                    "queues": workspace.queues,
                    "autopilot": workspace.autopilot,
                    "metadata": workspace.metadata,
                }
            )

        return {
            "workspaces": workspaces_list,
            "count": len(workspaces_list),
            "message": f"Retrieved {len(workspaces_list)} workspace(s)",
        }

    async def create_workspace(self, name: str, organization_id: int, metadata: dict | None = None) -> dict:
        """Create a new workspace.

        Args:
            name: Workspace name
            organization_id: Organization ID where the workspace should be created
            metadata: Optional metadata dictionary

        Returns:
            Dictionary containing created workspace details
        """
        logger.debug(f"Creating workspace: name={name}, organization_id={organization_id}, metadata={metadata}")

        # Build workspace data with required fields
        workspace_data: dict = {
            "name": name,
            "organization": self._build_resource_url("organizations", organization_id),
        }

        # Add optional metadata if provided
        if metadata is not None:
            workspace_data["metadata"] = metadata

        # Create the workspace
        workspace: Workspace = await self.client.create_new_workspace(workspace_data)

        return {
            "id": workspace.id,
            "name": workspace.name,
            "url": workspace.url,
            "organization": workspace.organization,
            "queues": workspace.queues,
            "autopilot": workspace.autopilot,
            "metadata": workspace.metadata,
            "message": f"Workspace '{workspace.name}' created successfully with ID {workspace.id}",
        }
