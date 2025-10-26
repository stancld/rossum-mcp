#!/usr/bin/env python3
"""Rossum MCP Server

Provides tools for uploading documents and retrieving annotations using Rossum API
"""

import asyncio
import json
import logging
import os
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from rossum_api import AsyncRossumAPIClient
from rossum_api.domain_logic.resources import Resource
from rossum_api.dtos import Token
from rossum_api.models import deserialize_default

# Set up logging to a file (since stdout is used for MCP)
logging.basicConfig(
    filename="/tmp/rossum_mcp_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class RossumMCPServer:
    """MCP Server for Rossum API integration"""

    def __init__(self) -> None:
        self.server = Server("rossum-mcp-server")
        self.base_url = os.environ["ROSSUM_API_BASE_URL"]
        self.api_token = os.environ["ROSSUM_API_TOKEN"]

        self.client = AsyncRossumAPIClient(base_url=self.base_url, credentials=Token(token=self.api_token))

        self.setup_handlers()

    async def upload_document(self, file_path: str, queue_id: int) -> dict:
        """Upload a document to Rossum.

        Args:
            file_path: Absolute path to the document file
            queue_id: Rossum queue ID where the document should be uploaded

        Returns:
            Dictionary containing task_id, task_status, queue_id, and message

        Raises:
            FileNotFoundError: If the specified file does not exist
            ValueError: If the upload fails or returns unexpected response
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            task = (await self.client.upload_document(queue_id, [(str(path), path.name)]))[0]
        except KeyError as e:
            logger.error(f"Upload failed - unexpected API response format: {e!s}")
            error_msg = (
                f"Document upload failed - API response missing expected key {e!s}. "
                f"This usually means either:\n"
                f"1. The queue_id ({queue_id}) is invalid or you don't have access to it\n"
                f"2. The Rossum API returned an error response\n"
                f"Please verify:\n"
                f"- The queue_id is correct and exists in your workspace\n"
                f"- You have permission to upload documents to this queue\n"
                f"- Your API token has the necessary permissions"
            )
            raise ValueError(error_msg) from e
        except IndexError as e:
            logger.error(f"Upload failed - no tasks returned: {e}")
            raise ValueError(
                f"Document upload failed - no tasks were created. "
                f"This may indicate the queue_id ({queue_id}) is invalid."
            ) from e
        except Exception as e:
            logger.error(f"Upload failed: {type(e).__name__}: {e}")
            raise ValueError(f"Document upload failed: {type(e).__name__}: {e!s}") from e

        return {
            "task_id": task.id,
            "task_status": task.status,
            "queue_id": queue_id,
            "message": "Document upload initiated. Use `list_annotations` to find the annotation ID for this queue.",
        }

    async def get_annotation(self, annotation_id: int, sideloads: Sequence[str] = ()) -> dict:
        """Retrieve annotation data from Rossum.

        Args:
            annotation_id: The annotation ID to retrieve
            sideloads: List of sideloads to include (e.g., ['content'])

        Returns:
            Dictionary containing annotation details including id, status, url, content, etc.
        """
        logger.debug(f"Retrieving annotation: annotation_id={annotation_id}")

        annotation = await self.client.retrieve_annotation(annotation_id, sideloads)

        return {
            "id": annotation.id,
            "status": annotation.status,
            "url": annotation.url,
            "schema": annotation.schema,
            "modifier": annotation.modifier,
            "document": annotation.document,
            "content": annotation.content,
            "created_at": annotation.created_at,
            "modified_at": annotation.modified_at,
        }

    async def list_annotations(
        self,
        queue_id: int,
        status: str | None = "importing,to_review,confirmed,exported",
    ) -> dict:
        """List annotations for a queue with optional filtering.

        Args:
            queue_id: Rossum queue ID to list annotations from
            status: Optional status filter (comma-separated). Defaults to common statuses.

        Returns:
            Dictionary containing count and results list of annotations
        """
        logger.debug(f"Listing annotations: queue_id={queue_id}, status={status}")

        # Build filter parameters
        params: dict = {"queue": queue_id, "page_size": 100}
        if status:
            params["status"] = status

        annotations_list = [item async for item in self.client.list_annotations(**params)]

        return {
            "count": len(annotations_list),
            "results": [
                {
                    "id": ann.id,
                    "status": ann.status,
                    "url": ann.url,
                    "document": ann.document,
                    "created_at": ann.created_at,
                    "modified_at": ann.modified_at,
                }
                for ann in annotations_list
            ],
        }

    async def get_queue(self, queue_id: int) -> dict:
        """Retrieve queue details.

        Args:
            queue_id: Rossum queue ID to retrieve

        Returns:
            Dictionary containing queue details including schema_id
        """
        logger.debug(f"Retrieving queue: queue_id={queue_id}")

        queue = await self.client.retrieve_queue(queue_id)

        return {
            "id": queue.id,
            "name": queue.name,
            "url": queue.url,
            "schema": queue.schema,
            "workspace": queue.workspace,
            "inbox": queue.inbox,
            "engine": queue.engine,
        }

    async def get_schema(self, schema_id: int) -> dict:
        """Retrieve schema details.

        Args:
            schema_id: Rossum schema ID to retrieve

        Returns:
            Dictionary containing schema details and content
        """
        logger.debug(f"Retrieving schema: schema_id={schema_id}")

        schema = await self.client.retrieve_schema(schema_id)

        return {
            "id": schema.id,
            "name": schema.name,
            "url": schema.url,
            "content": schema.content,
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
        queue = await self.client.retrieve_queue(queue_id)

        # Extract schema ID from the schema URL
        # The schema field is a URL like "https://api.elis.rossum.ai/v1/schemas/12345"
        schema_url = queue.schema
        schema_id = int(schema_url.rstrip("/").split("/")[-1])

        # Now retrieve the schema
        schema = await self.client.retrieve_schema(schema_id)

        return {
            "queue_id": queue.id,
            "queue_name": queue.name,
            "schema_id": schema.id,
            "schema_name": schema.name,
            "schema_url": schema.url,
            "schema_content": schema.content,
        }

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
        queue = await self.client.retrieve_queue(queue_id)

        # Check if an engine is assigned and determine its type
        engine_url = None
        engine_type = None

        if queue.dedicated_engine:
            engine_url = queue.dedicated_engine
            engine_type = "dedicated"
        elif queue.generic_engine:
            engine_url = queue.generic_engine
            engine_type = "generic"
        elif queue.engine:
            engine_url = queue.engine
            engine_type = "standard"

        if not engine_url:
            return {
                "queue_id": queue.id,
                "queue_name": queue.name,
                "engine_id": None,
                "engine_name": None,
                "engine_url": None,
                "engine_type": None,
                "message": "No engine assigned to this queue",
            }

        # Extract engine ID from the engine URL or use the embedded object
        # The engine field can be a URL like "https://api.elis.rossum.ai/v1/engines/12345"
        # or an embedded dict/object with engine data
        if isinstance(engine_url, str):
            engine_id = int(engine_url.rstrip("/").split("/")[-1])
            # Retrieve the engine from API
            engine = await self.client.retrieve_engine(engine_id)
        else:
            # If it's a dict, it's an embedded engine object - deserialize it using the SDK
            # No need to make an additional API call
            engine = deserialize_default(Resource.Engine, engine_url)

        # Now engine is always an Engine model object
        engine_id = engine.id
        engine_name = engine.name
        engine_url_final = engine.url

        return {
            "queue_id": queue.id,
            "queue_name": queue.name,
            "engine_id": engine_id,
            "engine_name": engine_name,
            "engine_url": engine_url_final,
            "engine_type": engine_type,
        }

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
    ) -> dict:
        """Create a new queue with schema and optional engine assignment.

        Args:
            name: Queue name
            workspace_id: Workspace ID where the queue should be created
            schema_id: Schema ID to assign to the queue
            engine_id: Optional engine ID to assign to the queue
            inbox_id: Optional inbox ID to assign to the queue
            connector_id: Optional connector ID to assign to the queue
            locale: Queue locale (default: en_GB)
            automation_enabled: Enable automation for the queue (default: False)
            automation_level: Automation level ('never', 'always', etc.) (default: never)
            training_enabled: Enable training for the queue (default: True)

        Returns:
            Dictionary containing created queue details including id, name, schema, and engine
        """
        logger.debug(
            f"Creating queue: name={name}, workspace_id={workspace_id}, schema_id={schema_id}, engine_id={engine_id}"
        )

        # Build queue data with required fields
        queue_data: dict = {
            "name": name,
            "workspace": f"{self.base_url}/workspaces/{workspace_id}",
            "schema": f"{self.base_url}/schemas/{schema_id}",
            "locale": locale,
            "automation_enabled": automation_enabled,
            "automation_level": automation_level,
            "training_enabled": training_enabled,
        }

        # Add optional fields if provided
        if engine_id is not None:
            queue_data["engine"] = f"{self.base_url}/engines/{engine_id}"

        if inbox_id is not None:
            queue_data["inbox"] = f"{self.base_url}/inboxes/{inbox_id}"

        if connector_id is not None:
            queue_data["connector"] = f"{self.base_url}/connectors/{connector_id}"

        # Create the queue
        queue = await self.client.create_new_queue(queue_data)

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

        # Use the internal client's PATCH method to update specific fields
        updated_queue_data = await self.client.internal_client.update(Resource.Queue, queue_id, queue_data)
        updated_queue = await self.client._deserializer(Resource.Queue, updated_queue_data)

        return {
            "id": updated_queue.id,
            "name": updated_queue.name,
            "url": updated_queue.url,
            "automation_enabled": updated_queue.automation_enabled,
            "automation_level": updated_queue.automation_level,
            "default_score_threshold": updated_queue.default_score_threshold,
            "locale": updated_queue.locale,
            "training_enabled": updated_queue.training_enabled,
            "message": f"Queue '{updated_queue.name}' (ID {updated_queue.id}) updated successfully",
        }

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

        # Use the internal client's PATCH method to update specific fields
        updated_schema_data = await self.client.internal_client.update(Resource.Schema, schema_id, schema_data)
        updated_schema = await self.client._deserializer(Resource.Schema, updated_schema_data)

        return {
            "id": updated_schema.id,
            "name": updated_schema.name,
            "url": updated_schema.url,
            "content": updated_schema.content,
            "message": f"Schema '{updated_schema.name}' (ID {updated_schema.id}) updated successfully",
        }

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

        # Use the internal client's PATCH method to update specific fields
        updated_engine_data = await self.client.internal_client.update(Resource.Engine, engine_id, engine_data)
        updated_engine = await self.client._deserializer(Resource.Engine, updated_engine_data)

        return {
            "id": updated_engine.id,
            "name": updated_engine.name,
            "url": updated_engine.url,
            "type": updated_engine.type,
            "learning_enabled": updated_engine.learning_enabled,
            "training_queues": updated_engine.training_queues,
            "description": updated_engine.description,
            "message": f"Engine '{updated_engine.name}' (ID {updated_engine.id}) updated successfully",
        }

    async def start_annotation(self, annotation_id: int) -> dict:
        """Start annotation to move it to 'to_review' status.

        Args:
            annotation_id: Rossum annotation ID to start

        Returns:
            Dictionary containing success message
        """
        logger.debug(f"Starting annotation: annotation_id={annotation_id}")

        await self.client.start_annotation(annotation_id)

        return {
            "annotation_id": annotation_id,
            "message": f"Annotation {annotation_id} started successfully. Status changed to 'to_review'.",
        }

    async def bulk_update_annotation_fields(self, annotation_id: int, operations: list[dict]) -> dict:
        """Bulk update annotation field values using operations.

        This is the CORRECT way to update annotation field values. Use this method instead of
        update_annotation_fields when you need to reliably change field values.

        Args:
            annotation_id: Rossum annotation ID to update
            operations: List of operations in JSON Patch format:
                [
                    {
                        "op": "replace",
                        "id": "datapoint_id",  # Actual datapoint ID from annotation.content
                        "value": {
                            "content": {
                                "value": "new_value",
                                "page": 1,  # Optional
                                "position": [x, y, w, h]  # Optional bounding box
                            }
                        }
                    },
                    {
                        "op": "remove",
                        "id": "datapoint_id_to_remove"
                    }
                ]

        Returns:
            Dictionary containing success message and operation count

        Example:
            # First get annotation to find datapoint IDs
            annotation = get_annotation(annotation_id=123, sideloads=['content'])
            # Find datapoint by schema_id in content and get its 'id'
            datapoint_id = "uuid-here"
            # Create operation
            operations = [{
                "op": "replace",
                "id": datapoint_id,
                "value": {"content": {"value": "air_waybill"}}
            }]
            result = bulk_update_annotation_fields(annotation_id=123, operations=operations)
        """
        logger.debug(f"Bulk updating annotation: annotation_id={annotation_id}, ops={operations}")

        await self.client.bulk_update_annotation_data(annotation_id, operations)

        return {
            "annotation_id": annotation_id,
            "operations_count": len(operations),
            "message": f"Annotation {annotation_id} updated with {len(operations)} operations successfully.",
        }

    async def confirm_annotation(self, annotation_id: int) -> dict:
        """Confirm annotation to move it to 'confirmed' status.

        Args:
            annotation_id: Rossum annotation ID to confirm

        Returns:
            Dictionary containing success message
        """
        logger.debug(f"Confirming annotation: annotation_id={annotation_id}")

        await self.client.confirm_annotation(annotation_id)

        return {
            "annotation_id": annotation_id,
            "message": f"Annotation {annotation_id} confirmed successfully. Status changed to 'confirmed'.",
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
                            "rir_field_names": ["document_type"],
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

        schema = await self.client.create_new_schema(schema_data)

        return {
            "id": schema.id,
            "name": schema.name,
            "url": schema.url,
            "content": schema.content,
            "message": f"Schema '{schema.name}' created successfully with ID {schema.id}",
        }

    def setup_handlers(self) -> None:  # noqa: C901
        """Setup MCP protocol handlers.

        Registers the list_tools and call_tool handlers for the MCP server.
        These handlers define the available tools and their execution logic.

        All MCP tools return JSON strings that clients must parse with json.loads().
        This is the standard MCP protocol behavior - tools return TextContent with JSON.
        """

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="upload_document",
                    description="Upload a document to Rossum for processing. Returns JSON string with task_id, task_status, queue_id, and message. MUST parse with json.loads(). To get the annotation ID for the uploaded document, call list_annotations with the queue_id.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to the document file to upload",
                            },
                            "queue_id": {
                                "type": "integer",
                                "description": "Rossum queue ID where the document should be uploaded",
                            },
                        },
                        "required": ["file_path", "queue_id"],
                    },
                ),
                Tool(
                    name="get_annotation",
                    description="Retrieve full annotation data including extracted content. Returns JSON string with id, status, url, schema, modifier, document, content, created_at, modified_at. MUST parse with json.loads(). After calling list_annotations to get annotation IDs, use this tool to retrieve complete data.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "annotation_id": {
                                "type": "integer",
                                "description": "The annotation ID obtained from list_annotations",
                            },
                            "sideloads": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of sideloads to include. Use ['content'] to fetch annotation content with datapoints. Without this, only metadata is returned.",
                            },
                        },
                        "required": ["annotation_id"],
                    },
                ),
                Tool(
                    name="list_annotations",
                    description="List all annotations for a queue with optional filtering. Returns JSON string with count and results array. MUST parse with json.loads(). After uploading documents, use this to get annotation IDs. Use get_annotation to retrieve full details for each annotation.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_id": {
                                "type": "integer",
                                "description": "Rossum queue ID to list annotations from (same queue_id used in upload_document)",
                            },
                            "status": {
                                "type": "string",
                                "description": "Filter by annotation status (e.g., 'importing', 'to_review', 'confirmed', 'exported'). These four are used as default.",
                            },
                        },
                        "required": ["queue_id"],
                    },
                ),
                Tool(
                    name="get_queue",
                    description="Retrieve queue details including the schema_id. Returns JSON string with id, name, url, schema, workspace, inbox, engine. MUST parse with json.loads(). Use get_schema to retrieve the schema.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_id": {
                                "type": "integer",
                                "description": "Rossum queue ID to retrieve",
                            },
                        },
                        "required": ["queue_id"],
                    },
                ),
                Tool(
                    name="get_schema",
                    description="Retrieve schema details including the schema content/structure. Returns JSON string with id, name, url, content. MUST parse with json.loads(). Use get_queue first to obtain the schema_id.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "schema_id": {
                                "type": "integer",
                                "description": "Rossum schema ID to retrieve (obtained from get_queue)",
                            },
                        },
                        "required": ["schema_id"],
                    },
                ),
                Tool(
                    name="get_queue_schema",
                    description="Retrieve the complete schema for a given queue in a single call. Returns JSON string with queue_id, queue_name, schema_id, schema_name, schema_url, schema_content. MUST parse with json.loads(). Recommended way to get a queue's schema.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_id": {
                                "type": "integer",
                                "description": "Rossum queue ID for which to retrieve the schema",
                            },
                        },
                        "required": ["queue_id"],
                    },
                ),
                Tool(
                    name="get_queue_engine",
                    description="Retrieve the complete engine information for a given queue. Returns JSON string with queue_id, queue_name, engine_id, engine_name, engine_url, engine_type. MUST parse with json.loads(). If no engine is assigned, returns None for engine fields.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_id": {
                                "type": "integer",
                                "description": "Rossum queue ID for which to retrieve the engine",
                            },
                        },
                        "required": ["queue_id"],
                    },
                ),
                Tool(
                    name="create_queue",
                    description="Create a new queue with schema and optional engine assignment. Returns JSON string with id, name, url, workspace, schema, engine, inbox, connector, locale, automation settings, and message. MUST parse with json.loads().",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the queue to create",
                            },
                            "workspace_id": {
                                "type": "integer",
                                "description": "Workspace ID where the queue should be created",
                            },
                            "schema_id": {
                                "type": "integer",
                                "description": "Schema ID to assign to the queue",
                            },
                            "engine_id": {
                                "type": ["integer", "null"],
                                "description": "Optional engine ID to assign to the queue for document processing",
                            },
                            "inbox_id": {
                                "type": ["integer", "null"],
                                "description": "Optional inbox ID to assign to the queue",
                            },
                            "connector_id": {
                                "type": ["integer", "null"],
                                "description": "Optional connector ID to assign to the queue",
                            },
                            "locale": {
                                "type": "string",
                                "description": "Queue locale (e.g., 'en_US', 'en_GB'). Default: 'en_GB'",
                            },
                            "automation_enabled": {
                                "type": "boolean",
                                "description": "Enable automation for the queue. Default: false",
                            },
                            "automation_level": {
                                "type": "string",
                                "description": "Automation level ('never', 'always', etc.). Default: 'never'",
                            },
                            "training_enabled": {
                                "type": "boolean",
                                "description": "Enable training for the queue. Default: true",
                            },
                        },
                        "required": ["name", "workspace_id", "schema_id"],
                    },
                ),
                Tool(
                    name="update_queue",
                    description="Update an existing queue's settings including automation thresholds. Returns JSON string with updated queue details and message. MUST parse with json.loads(). The default_score_threshold ranges from 0.0 to 1.0 (e.g., 0.90 = 90%). Common automation_level values: 'never', 'confident'.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_id": {
                                "type": "integer",
                                "description": "Queue ID to update",
                            },
                            "queue_data": {
                                "type": "object",
                                "description": "Dictionary containing queue fields to update. Common fields: 'name' (str), 'automation_enabled' (bool), 'automation_level' (str: 'never'/'always'/'confident'), 'default_score_threshold' (float: 0.0-1.0, e.g., 0.90 for 90%), 'locale' (str), 'training_enabled' (bool)",
                                "additionalProperties": True,
                            },
                        },
                        "required": ["queue_id", "queue_data"],
                    },
                ),
                Tool(
                    name="update_schema",
                    description="Update an existing schema, typically used to set field-level automation thresholds. Returns JSON string with updated schema details and message. MUST parse with json.loads(). Field-level thresholds override the queue's default_score_threshold. Use higher thresholds (0.95-0.98) for critical fields.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "schema_id": {
                                "type": "integer",
                                "description": "Schema ID to update",
                            },
                            "schema_data": {
                                "type": "object",
                                "description": "Dictionary containing schema fields to update. Typically contains 'content' key with the full schema content array where each field can have a 'score_threshold' property (float 0.0-1.0)",
                                "additionalProperties": True,
                            },
                        },
                        "required": ["schema_id", "schema_data"],
                    },
                ),
                Tool(
                    name="update_engine",
                    description="Update an existing engine's settings, including training queues. Returns JSON string with updated engine details and message. MUST parse with json.loads(). Use this to configure which queues an engine should learn from by updating training_queues with a list of queue URLs.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "engine_id": {
                                "type": "integer",
                                "description": "Engine ID to update",
                            },
                            "engine_data": {
                                "type": "object",
                                "description": "Dictionary containing engine fields to update. Supported fields: 'name' (str), 'description' (str), 'learning_enabled' (bool), 'training_queues' (array of queue URL strings like ['https://api.elis.rossum.ai/v1/queues/12345'])",
                                "additionalProperties": True,
                            },
                        },
                        "required": ["engine_id", "engine_data"],
                    },
                ),
                Tool(
                    name="start_annotation",
                    description="Start annotation to move it from 'importing' to 'to_review' status, making it ready for user review. Returns JSON string with annotation_id and message. MUST parse with json.loads(). Use after uploading a document and waiting for import to complete.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "annotation_id": {
                                "type": "integer",
                                "description": "Annotation ID to start (obtained from list_annotations or upload_document)",
                            },
                        },
                        "required": ["annotation_id"],
                    },
                ),
                Tool(
                    name="bulk_update_annotation_fields",
                    description="RECOMMENDED: Bulk update annotation field values using operations. This is the CORRECT and RELIABLE way to update field values. Returns JSON string with annotation_id, operations_count, and message. MUST parse with json.loads(). First get annotation with get_annotation(sideloads=['content']), find the datapoint by schema_id in content to get its 'id', then use that ID in operations.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "annotation_id": {
                                "type": "integer",
                                "description": "Annotation ID to update",
                            },
                            "operations": {
                                "type": "array",
                                "description": "List of operations in JSON Patch format. Each operation: {'op': 'replace'|'remove', 'id': 'datapoint_id', 'value': {'content': {'value': 'new_value', 'page': 1, 'position': [x,y,w,h]}}}. The 'id' field MUST be the actual datapoint ID from annotation.content (find by schema_id), NOT the schema_id itself. Page and position are optional.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "op": {
                                            "type": "string",
                                            "enum": ["replace", "remove"],
                                            "description": "Operation type: 'replace' to update value, 'remove' to delete datapoint",
                                        },
                                        "id": {
                                            "type": "string",
                                            "description": "Datapoint ID from annotation.content (NOT schema_id)",
                                        },
                                        "value": {
                                            "type": "object",
                                            "description": "Value object with content. Format: {'content': {'value': 'new_value', 'page': 1, 'position': [x,y,w,h]}}",
                                        },
                                    },
                                    "required": ["op", "id"],
                                },
                            },
                        },
                        "required": ["annotation_id", "operations"],
                    },
                ),
                Tool(
                    name="confirm_annotation",
                    description="Confirm annotation to move it from 'to_review' to 'confirmed' status. Returns JSON string with annotation_id and message. MUST parse with json.loads(). Use after reviewing and validating the extracted data. The annotation may then proceed to export if configured.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "annotation_id": {
                                "type": "integer",
                                "description": "Annotation ID to confirm",
                            },
                        },
                        "required": ["annotation_id"],
                    },
                ),
                Tool(
                    name="create_schema",
                    description="Create a new schema with field definitions. Returns JSON string with id, name, url, content, and message. MUST parse with json.loads(). Schema must have at least one section containing children (datapoints). Use this to define document structure before creating queues.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Schema name (e.g., 'Invoice Schema', 'Air Waybill Schema')",
                            },
                            "content": {
                                "type": "array",
                                "description": "Schema content array with sections containing datapoints. Structure: [{'category': 'section', 'id': 'section_id', 'label': 'Section Label', 'children': [{'category': 'datapoint', 'id': 'field_id', 'label': 'Field Label', 'type': 'string'|'enum'|'date'|'number', 'rir_field_names': ['field_name'], 'constraints': {'required': false}, 'options': [{'value': 'val', 'label': 'Label'}] (for enum only)}]}]. For enum fields, include 'options' array with value/label pairs.",
                                "items": {"type": "object"},
                            },
                        },
                        "required": ["name", "content"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:  # noqa: C901
            try:
                logger.info(f"Tool called: {name} with arguments: {arguments}")

                match name:
                    case "upload_document":
                        result = await self.upload_document(arguments["file_path"], arguments["queue_id"])
                    case "get_annotation":
                        result = await self.get_annotation(
                            arguments["annotation_id"],
                            sideloads=arguments.get("sideloads", ()),
                        )
                    case "list_annotations":
                        result = await self.list_annotations(
                            queue_id=arguments["queue_id"],
                            status=arguments.get("status"),
                        )
                    case "get_queue":
                        result = await self.get_queue(arguments["queue_id"])
                    case "get_schema":
                        result = await self.get_schema(arguments["schema_id"])
                    case "get_queue_schema":
                        result = await self.get_queue_schema(arguments["queue_id"])
                    case "get_queue_engine":
                        result = await self.get_queue_engine(arguments["queue_id"])
                    case "create_queue":
                        result = await self.create_queue(
                            name=arguments["name"],
                            workspace_id=arguments["workspace_id"],
                            schema_id=arguments["schema_id"],
                            engine_id=arguments.get("engine_id"),
                            inbox_id=arguments.get("inbox_id"),
                            connector_id=arguments.get("connector_id"),
                            locale=arguments.get("locale", "en_GB"),
                            automation_enabled=arguments.get("automation_enabled", False),
                            automation_level=arguments.get("automation_level", "never"),
                            training_enabled=arguments.get("training_enabled", True),
                        )
                    case "update_queue":
                        result = await self.update_queue(
                            queue_id=arguments["queue_id"],
                            queue_data=arguments["queue_data"],
                        )
                    case "update_schema":
                        result = await self.update_schema(
                            schema_id=arguments["schema_id"],
                            schema_data=arguments["schema_data"],
                        )
                    case "update_engine":
                        result = await self.update_engine(
                            engine_id=arguments["engine_id"],
                            engine_data=arguments["engine_data"],
                        )
                    case "start_annotation":
                        result = await self.start_annotation(annotation_id=arguments["annotation_id"])
                    case "bulk_update_annotation_fields":
                        result = await self.bulk_update_annotation_fields(
                            annotation_id=arguments["annotation_id"],
                            operations=arguments["operations"],
                        )
                    case "confirm_annotation":
                        result = await self.confirm_annotation(annotation_id=arguments["annotation_id"])
                    case "create_schema":
                        result = await self.create_schema(name=arguments["name"], content=arguments["content"])
                    case _:
                        raise ValueError(f"Unknown tool: {name}")

                logger.info(f"Tool {name} completed successfully")
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Tool {name} failed: {e!s}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                error_result = {"error": str(e), "traceback": traceback.format_exc()}
                return [TextContent(type="text", text=json.dumps(error_result, indent=2))]

    async def run(self) -> None:
        """Start the MCP server.

        Runs the server using stdio transport for communication with MCP clients.
        """
        async with stdio_server() as (read_stream, write_stream):
            print("Rossum MCP Server running on stdio", file=sys.stderr)
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())


async def async_main() -> None:
    """Async main entry point.

    Creates and runs the RossumMCPServer instance.
    """
    server = RossumMCPServer()
    await server.run()


def main() -> None:
    """Main entry point for console script.

    This is the entry point used when running the server as a command-line tool.
    It initializes the async event loop and starts the server.
    """
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
