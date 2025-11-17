"""Schema operations handler for Rossum MCP Server"""

from __future__ import annotations

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
                description="Retrieve schema details. Returns: id, name, url, content.",
                inputSchema={
                    "type": "object",
                    "properties": {"schema_id": {"type": "integer", "description": "Schema ID"}},
                    "required": ["schema_id"],
                },
            ),
            Tool(
                name="update_schema",
                description="Update schema, typically for field-level thresholds. Returns: updated schema details, message.",
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
                description="Create a schema. Returns: id, name, url, content, message. Must have ≥1 section with children (datapoints).",
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
        """Retrieve schema details.

        Args:
            schema_id: Rossum schema ID to retrieve

        Returns:
            Dictionary containing schema details and content
        """
        logger.debug(f"Retrieving schema: schema_id={schema_id}")

        schema: Schema = await self.client.retrieve_schema(schema_id)
        return {"id": schema.id, "name": schema.name, "url": schema.url, "content": schema.content}

    async def update_schema(self, schema_id: int, schema_data: dict) -> dict:
        """Update an existing schema.

        Args:
            schema_id: Rossum schema ID to update
            schema_data: Dictionary containing schema fields to update
                Typically contains 'content' - the schema content array

        Returns:
            Dictionary containing updated schema details

        Example:
            Update field-level thresholds:
            {
                "content": [
                    {"id": "invoice_id", "score_threshold": 0.98, ...},
                    {"id": "amount_total", "score_threshold": 0.95, ...},
                ]
            }
        """
        logger.debug(f"Updating schema: schema_id={schema_id}")

        updated_schema_data = await self.client._http_client.update(Resource.Schema, schema_id, schema_data)
        updated_schema: Schema = self.client._deserializer(Resource.Schema, updated_schema_data)

        return {
            "id": updated_schema.id,
            "name": updated_schema.name,
            "url": updated_schema.url,
            "content": updated_schema.content,
            "message": f"Schema '{updated_schema.name}' (ID {updated_schema.id}) updated successfully",
        }

    async def create_schema(self, name: str, content: list[dict]) -> dict:
        """Create a new schema.

        Args:
            name: Schema name
            content: Schema content array containing sections with datapoints.
                Must follow Rossum schema structure with sections containing children.

        Returns:
            Dictionary containing created schema details including id, name, url, and content

        Example content structure:
            [
                {
                    "category": "section",
                    "id": "document_info",
                    "label": "Document Information",
                    "children": [
                        {
                            "category": "datapoint",
                            "id": "document_type",
                            "label": "Document Type",
                            "type": "enum",
                            "rir_field_names": [],
                            "constraints": {"required": False},
                            "options": [
                                {"value": "invoice", "label": "Invoice"},
                                {"value": "receipt", "label": "Receipt"}
                            ]
                        }
                    ]
                }
            ]
        """
        logger.debug(f"Creating schema: name={name}")

        schema_data = {"name": name, "content": content}

        schema: Schema = await self.client.create_new_schema(schema_data)

        return {
            "id": schema.id,
            "name": schema.name,
            "url": schema.url,
            "content": schema.content,
            "message": f"Schema '{schema.name}' created successfully with ID {schema.id}",
        }
