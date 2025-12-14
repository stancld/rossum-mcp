"""Schema tools for Rossum MCP Server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.schema import Schema  # noqa: TC002 - needed at runtime for FastMCP

from rossum_mcp.tools.base import is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def register_schema_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register schema-related tools with the FastMCP server."""

    @mcp.tool(description="Retrieve schema details.")
    async def get_schema(schema_id: int) -> Schema:
        """Retrieve schema details."""
        logger.debug(f"Retrieving schema: schema_id={schema_id}")
        schema: Schema = await client.retrieve_schema(schema_id)
        return schema

    @mcp.tool(description="Update schema, typically for field-level thresholds.")
    async def update_schema(schema_id: int, schema_data: dict) -> Schema | dict:
        """Update an existing schema."""
        if not is_read_write_mode():
            return {"error": "update_schema is not available in read-only mode"}

        logger.debug(f"Updating schema: schema_id={schema_id}")
        await client._http_client.update(Resource.Schema, schema_id, schema_data)
        updated_schema: Schema = await client.retrieve_schema(schema_id)
        return updated_schema

    @mcp.tool(description="Create a schema. Must have ≥1 section with children (datapoints).")
    async def create_schema(name: str, content: list[dict]) -> Schema | dict:
        """Create a new schema."""
        if not is_read_write_mode():
            return {"error": "create_schema is not available in read-only mode"}

        logger.debug(f"Creating schema: name={name}")
        schema_data = {"name": name, "content": content}
        schema: Schema = await client.create_new_schema(schema_data)
        return schema
