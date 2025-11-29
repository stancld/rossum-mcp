"""Engine operations handler for Rossum MCP Server"""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from mcp.types import Tool
from rossum_api.domain_logic.resources import Resource

from rossum_mcp.handlers.base import BaseHandler

if TYPE_CHECKING:
    from rossum_api.models.engine import Engine, EngineField

logger = logging.getLogger(__name__)


class EnginesHandler(BaseHandler):
    """Handler for engine-related operations"""

    @classmethod
    def get_tool_definitions(cls) -> list[Tool]:
        """Get list of tool definitions for engine operations."""
        return [
            Tool(
                name="update_engine",
                description="Update engine settings. Returns: id, url, name, type, learning_enabled, training_queues, description, agenda_id, message.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "engine_id": {"type": "integer", "description": "Engine ID"},
                        "engine_data": {
                            "type": "object",
                            "description": "Fields to update: name, description, learning_enabled, training_queues (array of queue URLs)",
                            "additionalProperties": True,
                        },
                    },
                    "required": ["engine_id", "engine_data"],
                },
            ),
            Tool(
                name="create_engine",
                description="Create a new engine. Returns: id, url, name, type, learning_enabled, training_queues, description, agenda_id, message. IMPORTANT: When creating a new engine, check the schema to be used and create contained Engine fields immediately!",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Engine name"},
                        "organization_id": {"type": "integer", "description": "Organization ID"},
                        "engine_type": {
                            "type": "string",
                            "description": "Engine type: 'extractor' or 'splitter'",
                            "enum": ["extractor", "splitter"],
                        },
                    },
                    "required": ["name", "organization_id", "engine_type"],
                },
            ),
            Tool(
                name="create_engine_field",
                description="Create engine field for each schema field. Must be called when creating engine + schema. Returns: id, url, engine, name, tabular, label, type, subtype, pre_trained_field_id, multiline, schema_ids (added), message.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "engine_id": {"type": "integer", "description": "Engine ID"},
                        "name": {"type": "string", "description": "Field name (slug, max 50 chars)"},
                        "label": {"type": "string", "description": "Human-readable label (max 100 chars)"},
                        "field_type": {
                            "type": "string",
                            "description": "Field type, IMPORTANT: Follow exactly referenced schema if asked.",
                            "enum": ["string", "number", "date", "enum"],
                        },
                        "schema_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Schema IDs to link (≥1 required)",
                        },
                        "tabular": {
                            "type": "boolean",
                            "description": "Is in table? Default: false. IMPORTANT: Follow exactly referenced schema if asked.",
                        },
                        "multiline": {
                            "type": "string",
                            "description": "Multiline: 'true', 'false', ''. Default: 'false'",
                            "enum": ["true", "false", ""],
                        },
                        "subtype": {"type": ["string", "null"], "description": "Optional subtype (max 50 chars)"},
                        "pre_trained_field_id": {
                            "type": ["string", "null"],
                            "description": "Optional pre-trained field ID (max 50 chars)",
                        },
                    },
                    "required": ["engine_id", "name", "label", "field_type", "schema_ids"],
                },
            ),
        ]

    async def update_engine(self, engine_id: int, engine_data: dict) -> dict:
        """Update an existing engine's settings.

        Args:
            engine_id: Rossum engine ID to update
            engine_data: Dictionary containing engine fields to update
                Supported fields: name, description, learning_enabled, training_queues
                - name (str): Engine name
                - description (str): Engine description
                - learning_enabled (bool): Enable/disable learning for the engine
                - training_queues (list[str]): List of queue URLs for training
                  Format: ["https://api.elis.rossum.ai/v1/queues/12345", ...]

        Returns:
            Dictionary containing updated engine details

        Example:
            Update training queues:
            {
                "training_queues": [
                    "https://api.elis.rossum.ai/v1/queues/12345",
                    "https://api.elis.rossum.ai/v1/queues/67890"
                ]
            }

            Enable learning:
            {
                "learning_enabled": True
            }
        """
        logger.debug(f"Updating engine: engine_id={engine_id}, data={engine_data}")

        updated_engine_data = await self.client._http_client.update(Resource.Engine, engine_id, engine_data)
        updated_engine: Engine = self.client._deserializer(Resource.Engine, updated_engine_data)

        result = dataclasses.asdict(updated_engine)
        result["message"] = f"Engine '{updated_engine.name}' (ID {updated_engine.id}) updated successfully"
        return result

    async def create_engine(self, name: str, organization_id: int, engine_type: str) -> dict:
        """Create a new engine.

        Args:
            name: Engine name
            organization_id: Organization ID where the engine should be created
            engine_type: Engine type - either 'extractor' or 'splitter'

        Returns:
            Dictionary containing created engine details including id, name, url, type, and message

        Raises:
            ValueError: If engine_type is not 'extractor' or 'splitter'
        """
        if engine_type not in ("extractor", "splitter"):
            raise ValueError(f"Invalid engine_type '{engine_type}'. Must be 'extractor' or 'splitter'")

        logger.debug(f"Creating engine: name={name}, organization_id={organization_id}, type={engine_type}")

        engine_data = {
            "name": name,
            "organization": self._build_resource_url("organizations", organization_id),
            "type": engine_type,
        }

        engine_response = await self.client._http_client.create(Resource.Engine, engine_data)
        engine: Engine = self.client._deserializer(Resource.Engine, engine_response)

        result = dataclasses.asdict(engine)
        result["message"] = f"Engine '{engine.name}' created successfully with ID {engine.id}"
        return result

    async def create_engine_field(
        self,
        engine_id: int,
        name: str,
        label: str,
        field_type: str,
        schema_ids: list[int],
        tabular: bool = False,
        multiline: str = "false",
        subtype: str | None = None,
        pre_trained_field_id: str | None = None,
    ) -> dict:
        """Create a new engine field and link it to schemas.

        Engine fields define what data the engine extracts. They must be created for each
        field in the schema when setting up an engine.

        Args:
            engine_id: Engine ID to which this field belongs
            name: Field name (slug format, max 50 chars)
            label: Human-readable label (max 100 chars)
            field_type: Field type - 'string', 'number', 'date', or 'enum'
            schema_ids: List of schema IDs to link this engine field to
            tabular: Whether this field is in a table (default: False)
            multiline: Multiline setting - 'true', 'false', or '' (default: 'false')
            subtype: Optional field subtype (max 50 chars)
            pre_trained_field_id: Optional pre-trained field ID (max 50 chars)

        Returns:
            Dictionary containing created engine field details including id, name, url, and message

        Raises:
            ValueError: If field_type is not valid or schema_ids is empty
        """
        valid_types = ("string", "number", "date", "enum")
        if field_type not in valid_types:
            raise ValueError(f"Invalid field_type '{field_type}'. Must be one of: {', '.join(valid_types)}")

        if not schema_ids:
            raise ValueError("schema_ids cannot be empty - engine field must be linked to at least one schema")

        logger.debug(
            f"Creating engine field: engine_id={engine_id}, name={name}, type={field_type}, schemas={schema_ids}"
        )

        # Prepare engine field data
        engine_field_data = {
            "engine": self._build_resource_url("engines", engine_id),
            "name": name,
            "label": label,
            "type": field_type,
            "tabular": tabular,
            "multiline": multiline,
            "schemas": [self._build_resource_url("schemas", schema_id) for schema_id in schema_ids],
        }

        # Add optional fields if provided
        if subtype is not None:
            engine_field_data["subtype"] = subtype

        if pre_trained_field_id is not None:
            engine_field_data["pre_trained_field_id"] = pre_trained_field_id

        # Create the engine field
        engine_field_response = await self.client._http_client.create(Resource.EngineField, engine_field_data)
        engine_field: EngineField = self.client._deserializer(Resource.EngineField, engine_field_response)

        result = dataclasses.asdict(engine_field)
        result["schema_ids"] = schema_ids
        result["message"] = (
            f"Engine field '{engine_field.label}' created successfully with ID {engine_field.id} and linked to {len(schema_ids)} schema(s)"
        )
        return result
