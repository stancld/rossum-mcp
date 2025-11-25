"""Queue operations handler for Rossum MCP Server"""

from __future__ import annotations

import dataclasses
import logging
import os
from typing import TYPE_CHECKING

from mcp.types import Tool
from rossum_api.domain_logic.resources import Resource
from rossum_api.models import deserialize_default

from rossum_mcp.handlers.base import BaseHandler

if TYPE_CHECKING:
    from rossum_api.models.engine import Engine
    from rossum_api.models.queue import Queue
    from rossum_api.models.schema import Schema

logger = logging.getLogger(__name__)


class QueuesHandler(BaseHandler):
    """Handler for queue-related operations"""

    @classmethod
    def get_tool_definitions(cls) -> list[Tool]:
        """Get list of tool definitions for queue operations."""
        return [
            Tool(
                name="get_queue",
                description="Retrieve queue details. Returns: id, name, url, schema, workspace, inbox, engine.",
                inputSchema={
                    "type": "object",
                    "properties": {"queue_id": {"type": "integer", "description": "Queue ID"}},
                    "required": ["queue_id"],
                },
            ),
            Tool(
                name="get_queue_schema",
                description="Retrieve queue schema. Returns Schema model fields: id, name, queues, url, content, metadata, modified_by, modified_at.",
                inputSchema={
                    "type": "object",
                    "properties": {"queue_id": {"type": "integer", "description": "Queue ID"}},
                    "required": ["queue_id"],
                },
            ),
            Tool(
                name="get_queue_engine",
                description="Retrieve queue engine. Returns Engine model fields: id, url, name, type, learning_enabled, training_queues, description, agenda_id. None if no engine assigned.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "queue_id": {"type": "integer", "description": "Queue ID"},
                    },
                    "required": ["queue_id"],
                },
            ),
            Tool(
                name="create_queue",
                description="Create a queue. Returns: id, name, url, workspace, schema, engine, inbox, connector, locale, automation settings, message.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Queue name"},
                        "workspace_id": {"type": "integer", "description": "Workspace ID"},
                        "schema_id": {"type": "integer", "description": "Schema ID"},
                        "engine_id": {"type": ["integer", "null"], "description": "Optional engine ID"},
                        "inbox_id": {"type": ["integer", "null"], "description": "Optional inbox ID"},
                        "connector_id": {"type": ["integer", "null"], "description": "Optional connector ID"},
                        "locale": {"type": "string", "description": "Locale. Default: 'en_GB'"},
                        "automation_enabled": {
                            "type": "boolean",
                            "description": "Enable automation. Default: false",
                        },
                        "automation_level": {
                            "type": "string",
                            "description": "Level: 'never', 'always'. Default: 'never'",
                        },
                        "training_enabled": {"type": "boolean", "description": "Enable training. Default: true"},
                        "splitting_screen_feature_flag": {
                            "type": "boolean",
                            "description": "Enable splitting screen for inbox queue in UI. Default: false",
                        },
                    },
                    "required": ["name", "workspace_id", "schema_id"],
                },
            ),
            Tool(
                name="update_queue",
                description="Update queue settings. Returns: updated queue details, message.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "queue_id": {"type": "integer", "description": "Queue ID"},
                        "queue_data": {
                            "type": "object",
                            "description": "Fields to update: name, automation_enabled, automation_level ('never'/'always'/'confident'), default_score_threshold (0.0-1.0), locale, training_enabled",
                            "additionalProperties": True,
                        },
                    },
                    "required": ["queue_id", "queue_data"],
                },
            ),
        ]

    async def get_queue(self, queue_id: int) -> dict:
        """Retrieve queue details.

        Args:
            queue_id: Rossum queue ID to retrieve

        Returns:
            Dictionary containing queue details including schema_id
        """
        logger.debug(f"Retrieving queue: queue_id={queue_id}")

        queue: Queue = await self.client.retrieve_queue(queue_id)
        return {
            "id": queue.id,
            "name": queue.name,
            "url": queue.url,
            "schema": queue.schema,
            "workspace": queue.workspace,
            "inbox": queue.inbox,
            "engine": queue.engine,
        }

    async def get_queue_schema(self, queue_id: int) -> dict:
        """Retrieve complete schema for a queue.

        This convenience method combines queue and schema retrieval in a single call.

        Args:
            queue_id: Rossum queue ID

        Returns:
            Dictionary containing queue and schema details including schema content
        """
        logger.debug(f"Retrieving queue schema: queue_id={queue_id}")

        # First retrieve the queue to get the schema URL/ID
        queue: Queue = await self.client.retrieve_queue(queue_id)

        # Extract schema ID from the schema URL
        # The schema field is a URL like "https://api.elis.rossum.ai/v1/schemas/12345"
        schema_url = queue.schema
        schema_id = int(schema_url.rstrip("/").split("/")[-1])

        # Now retrieve the schema
        schema: Schema = await self.client.retrieve_schema(schema_id)

        return dataclasses.asdict(schema)

    async def get_queue_engine(self, queue_id: int) -> dict:
        """Retrieve complete engine information for a queue.

        This convenience method combines queue and engine retrieval in a single call.

        Args:
            queue_id: Rossum queue ID

        Returns:
            Dictionary containing queue and engine details. If no engine is assigned,
            returns None for engine fields.
        """
        logger.debug(f"Retrieving queue engine: queue_id={queue_id}")

        # First retrieve the queue to get the engine URL/ID
        queue: Queue = await self.client.retrieve_queue(queue_id)

        # Check if an engine is assigned and determine its type
        engine_url = None

        if queue.dedicated_engine:
            engine_url = queue.dedicated_engine
        elif queue.generic_engine:
            engine_url = queue.generic_engine
        elif queue.engine:
            engine_url = queue.engine

        if not engine_url:
            return {"message": "No engine assigned to this queue"}

        # Extract engine ID from the engine URL or use the embedded object
        # The engine field can be a URL like "https://api.elis.rossum.ai/v1/engines/12345"
        # or an embedded dict/object with engine data
        if isinstance(engine_url, str):
            engine_id = int(engine_url.rstrip("/").split("/")[-1])
            # Retrieve the engine from API
            engine: Engine = await self.client.retrieve_engine(engine_id)
        else:
            # If it's a dict, it's an embedded engine object - deserialize it using the SDK
            # No need to make an additional API call
            engine = deserialize_default(Resource.Engine, engine_url)

        # Now engine is always an Engine model object
        return dataclasses.asdict(engine)

    async def create_queue(
        self,
        name: str,
        workspace_id: int,
        schema_id: int,
        engine_id: int | None = None,
        inbox_id: int | None = None,
        connector_id: int | None = None,
        locale: str = "en_GB",
        automation_enabled: bool = False,
        automation_level: str = "never",
        training_enabled: bool = True,
        splitting_screen_feature_flag: bool = False,
    ) -> dict:
        """Create a new queue with schema and optional engine assignment.

        Args:
            name: Queue name
            workspace_id: Workspace ID where the queue should be created
            schema_id: Schema ID to assign to the queue
            engine_id: Optional engine ID to assign to the queue
            inbox_id: Optional inbox ID to assign to the queue
            connector_id: Optional connector ID to assign to the queue
            locale: Queue locale
            automation_enabled: Enable automation for the queue
            automation_level: Automation level ('never', 'always', etc.)
            training_enabled: Enable training for the queue
            splitting_screen_feature_flag: Enable splitting screen for inbox queue in UI

        Returns:
            Dictionary containing created queue details including id, name, schema, and engine
        """
        logger.debug(
            f"Creating queue: name={name}, workspace_id={workspace_id}, schema_id={schema_id}, engine_id={engine_id}"
        )

        # Build queue data with required fields
        queue_data: dict = {
            "name": name,
            "workspace": self._build_resource_url("workspaces", workspace_id),
            "schema": self._build_resource_url("schemas", schema_id),
            "locale": locale,
            "automation_enabled": automation_enabled,
            "automation_level": automation_level,
            "training_enabled": training_enabled,
        }

        # Add optional fields if provided
        if engine_id is not None:
            queue_data["engine"] = self._build_resource_url("engines", engine_id)

        if inbox_id is not None:
            queue_data["inbox"] = self._build_resource_url("inboxes", inbox_id)

        if connector_id is not None:
            queue_data["connector"] = self._build_resource_url("connectors", connector_id)

        if splitting_screen_feature_flag:
            if not (os.environ.get("SPLITTING_SCREEN_FLAG_NAME") and os.environ.get("SPLITTING_SCREEN_FLAG_VALUE")):
                logger.error("Splitting screen failed to update")
            queue_data["settings"] = {
                os.environ["SPLITTING_SCREEN_FLAG_NAME"]: os.environ["SPLITTING_SCREEN_FLAG_VALUE"]
            }

        # Create the queue
        queue: Queue = await self.client.create_new_queue(queue_data)

        return {
            "id": queue.id,
            "name": queue.name,
            "url": queue.url,
            "workspace": queue.workspace,
            "schema": queue.schema,
            "engine": queue.engine,
            "inbox": queue.inbox,
            "connector": queue.connector,
            "locale": queue.locale,
            "automation_enabled": queue.automation_enabled,
            "automation_level": queue.automation_level,
            "training_enabled": queue.training_enabled,
            "message": f"Queue '{queue.name}' created successfully with ID {queue.id}",
        }

    async def update_queue(self, queue_id: int, queue_data: dict) -> dict:
        """Update an existing queue with new settings.

        Args:
            queue_id: Rossum queue ID to update
            queue_data: Dictionary containing queue fields to update
                Supported fields: name, automation_enabled, automation_level,
                default_score_threshold, locale, training_enabled, etc.

        Returns:
            Dictionary containing updated queue details

        Example:
            Update automation settings:
            {
                "automation_enabled": True,
                "automation_level": "auto_if_confident",
                "default_score_threshold": 0.90
            }
        """
        logger.debug(f"Updating queue: queue_id={queue_id}, data={queue_data}")

        updated_queue_data = await self.client._http_client.update(Resource.Queue, queue_id, queue_data)
        updated_queue: Queue = self.client._deserializer(Resource.Queue, updated_queue_data)

        result = dataclasses.asdict(updated_queue)
        result["message"] = f"Queue '{updated_queue.name}' (ID {updated_queue.id}) updated successfully"
        return result
