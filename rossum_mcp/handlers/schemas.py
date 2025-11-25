"""Schema operations handler for Rossum MCP Server"""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from mcp.types import Tool
from rossum_api.domain_logic.resources import Resource

from rossum_mcp.handlers.base import BaseHandler

if TYPE_CHECKING:
    from rossum_api.models.schema import Schema

logger = logging.getLogger(__name__)


class SchemasHandler(BaseHandler):
    """Handler for schema-related operations"""

    @classmethod
    def get_tool_definitions(cls) -> list[Tool]:
        """Get list of tool definitions for schema operations."""
        return [
            Tool(
                name="get_schema",
                description="Retrieve schema details. Returns: id, name, queues, url, content (sections with datapoints), metadata, modified_by, modified_at.",
                inputSchema={
                    "type": "object",
                    "properties": {"schema_id": {"type": "integer", "description": "Schema ID"}},
                    "required": ["schema_id"],
                },
            ),
            Tool(
                name="update_schema",
                description="Update schema, typically for field-level thresholds. Returns: id, name, queues, url, content (sections with datapoints), metadata, modified_by, modified_at.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema_id": {"type": "integer", "description": "Schema ID"},
                        "schema_data": {
                            "type": "object",
                            "description": "Fields to update. Typically 'content' with schema array where fields have 'score_threshold' (0.0-1.0)",
                            "additionalProperties": True,
                        },
                    },
                    "required": ["schema_id", "schema_data"],
                },
            ),
            Tool(
                name="create_schema",
                description="Create a schema. Returns: id, name, queues, url, content (sections with datapoints), metadata, modified_by, modified_at. Must have ≥1 section with children (datapoints).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Schema name"},
                        "content": {
                            "type": "array",
                            "description": "Schema sections with datapoints. Structure: [{'category': 'section', 'id': 'section_id', 'label': 'Label', 'children': [{'category': 'datapoint', 'id': 'field_id', 'label': 'Label', 'type': 'string'|'enum'|'date'|'number', 'rir_field_names': ['name'], 'constraints': {'required': false}, 'options': [{'value': 'v', 'label': 'L'}]}]}]",
                            "items": {"type": "object"},
                        },
                    },
                    "required": ["name", "content"],
                },
            ),
        ]

    async def get_schema(self, schema_id: int) -> dict:
        """Retrieve schema details."""
        logger.debug(f"Retrieving schema: schema_id={schema_id}")
        schema: Schema = await self.client.retrieve_schema(schema_id)
        return dataclasses.asdict(schema)

    async def update_schema(self, schema_id: int, schema_data: dict) -> dict:
        """Update an existing schema."""
        logger.debug(f"Updating schema: schema_id={schema_id}")
        await self.client._http_client.update(Resource.Schema, schema_id, schema_data)
        updated_schema: Schema = await self.client.retrieve_schema(schema_id)
        return dataclasses.asdict(updated_schema)

    async def create_schema(self, name: str, content: list[dict]) -> dict:
        """Create a new schema."""
        logger.debug(f"Creating schema: name={name}")
        schema_data = {"name": name, "content": content}
        schema: Schema = await self.client.create_new_schema(schema_data)
        return dataclasses.asdict(schema)
