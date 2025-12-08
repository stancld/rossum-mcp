"""Schema tools for Rossum MCP Server."""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource

from rossum_mcp.tools.base import is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient
    from rossum_api.models.schema import Schema

logger = logging.getLogger(__name__)


def register_schema_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register schema-related tools with the FastMCP server."""

    @mcp.tool(
        description="Retrieve schema details. Returns: id, name, queues, url, content (sections with datapoints), metadata, modified_by, modified_at."
    )
    async def get_schema(schema_id: int) -> dict:
        """Retrieve schema details."""
        logger.debug(f"Retrieving schema: schema_id={schema_id}")
        schema: Schema = await client.retrieve_schema(schema_id)
        return dataclasses.asdict(schema)

    @mcp.tool(
        description="Update schema, typically for field-level thresholds. Returns: id, name, queues, url, content (sections with datapoints), metadata, modified_by, modified_at."
    )
    async def update_schema(schema_id: int, schema_data: dict) -> dict:
        """Update an existing schema."""
        if not is_read_write_mode():
            return {"error": "update_schema is not available in read-only mode"}

        logger.debug(f"Updating schema: schema_id={schema_id}")
        await client._http_client.update(Resource.Schema, schema_id, schema_data)
        updated_schema: Schema = await client.retrieve_schema(schema_id)
        return dataclasses.asdict(updated_schema)

    @mcp.tool(
        description="Create a schema. Returns: id, name, queues, url, content (sections with datapoints), metadata, modified_by, modified_at. Must have ≥1 section with children (datapoints)."
    )
    async def create_schema(name: str, content: list[dict]) -> dict:
        """Create a new schema."""
        if not is_read_write_mode():
            return {"error": "create_schema is not available in read-only mode"}

        logger.debug(f"Creating schema: name={name}")
        schema_data = {"name": name, "content": content}
        schema: Schema = await client.create_new_schema(schema_data)
        return dataclasses.asdict(schema)
