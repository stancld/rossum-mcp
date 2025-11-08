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

        # Read-only mode configuration: "read-only" or "read-write" (default)
        self.mode = os.environ.get("ROSSUM_MCP_MODE", "read-write").lower()
        if self.mode not in ("read-only", "read-write"):
            raise ValueError(f"Invalid ROSSUM_MCP_MODE: {self.mode}. Must be 'read-only' or 'read-write'")

        logger.info(f"Rossum MCP Server starting in {self.mode} mode")

        self.client = AsyncRossumAPIClient(base_url=self.base_url, credentials=Token(token=self.api_token))

        # Define read-only tool names (GET/LIST operations)
        self._read_only_tools = {
            "get_annotation",
            "list_annotations",
            "get_queue",
            "get_schema",
            "get_queue_schema",
            "get_queue_engine",
            "list_hooks",
            "list_rules",
        }

        # Setup tool registry mapping tool names to handler methods
        self._tool_registry = self._build_tool_registry()

        self.setup_handlers()

    def _build_resource_url(self, resource_type: str, resource_id: int) -> str:
        """Build a full URL for a Rossum API resource.

        Args:
            resource_type: The resource type (e.g., 'workspaces', 'schemas', 'queues')
            resource_id: The resource ID

        Returns:
            Full URL string for the resource
        """
        return f"{self.base_url}/{resource_type}/{resource_id}"

    def _is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed based on current mode.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if the tool is allowed in current mode, False otherwise
        """
        if self.mode == "read-write":
            return True
        # In read-only mode, only allow read-only tools
        return tool_name in self._read_only_tools

    def _build_tool_registry(self) -> dict:
        """Build registry mapping tool names to their handler methods.

        Filters tools based on the current mode (read-only or read-write).

        Returns:
            Dictionary mapping tool names to async handler callables
        """
        all_tools = {
            "upload_document": self._handle_upload_document,
            "get_annotation": self._handle_get_annotation,
            "list_annotations": self._handle_list_annotations,
            "get_queue": self._handle_get_queue,
            "get_schema": self._handle_get_schema,
            "get_queue_schema": self._handle_get_queue_schema,
            "get_queue_engine": self._handle_get_queue_engine,
            "create_queue": self._handle_create_queue,
            "update_queue": self._handle_update_queue,
            "update_schema": self._handle_update_schema,
            "update_engine": self._handle_update_engine,
            "start_annotation": self._handle_start_annotation,
            "bulk_update_annotation_fields": self._handle_bulk_update_annotation_fields,
            "confirm_annotation": self._handle_confirm_annotation,
            "create_schema": self._handle_create_schema,
            "create_engine": self._handle_create_engine,
            "create_engine_field": self._handle_create_engine_field,
            "list_hooks": self._handle_list_hooks,
            "list_rules": self._handle_list_rules,
        }

        # Filter tools based on mode
        return {name: handler for name, handler in all_tools.items() if self._is_tool_allowed(name)}

    # Tool handler methods - direct argument passing for better type safety
    async def _handle_upload_document(self, file_path: str, queue_id: int) -> dict:
        return await self.upload_document(file_path, queue_id)

    async def _handle_get_annotation(self, annotation_id: int, sideloads: Sequence[str] = ()) -> dict:
        return await self.get_annotation(annotation_id, sideloads=sideloads)

    async def _handle_list_annotations(self, queue_id: int, status: str | None = None) -> dict:
        return await self.list_annotations(queue_id=queue_id, status=status)

    async def _handle_get_queue(self, queue_id: int) -> dict:
        return await self.get_queue(queue_id)

    async def _handle_get_schema(self, schema_id: int) -> dict:
        return await self.get_schema(schema_id)

    async def _handle_get_queue_schema(self, queue_id: int) -> dict:
        return await self.get_queue_schema(queue_id)

    async def _handle_get_queue_engine(self, queue_id: int) -> dict:
        return await self.get_queue_engine(queue_id)

    async def _handle_create_queue(
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
        return await self.create_queue(
            name=name,
            workspace_id=workspace_id,
            schema_id=schema_id,
            engine_id=engine_id,
            inbox_id=inbox_id,
            connector_id=connector_id,
            locale=locale,
            automation_enabled=automation_enabled,
            automation_level=automation_level,
            training_enabled=training_enabled,
        )

    async def _handle_update_queue(self, queue_id: int, queue_data: dict) -> dict:
        return await self.update_queue(queue_id=queue_id, queue_data=queue_data)

    async def _handle_update_schema(self, schema_id: int, schema_data: dict) -> dict:
        return await self.update_schema(schema_id=schema_id, schema_data=schema_data)

    async def _handle_update_engine(self, engine_id: int, engine_data: dict) -> dict:
        return await self.update_engine(engine_id=engine_id, engine_data=engine_data)

    async def _handle_start_annotation(self, annotation_id: int) -> dict:
        return await self.start_annotation(annotation_id=annotation_id)

    async def _handle_bulk_update_annotation_fields(self, annotation_id: int, operations: list[dict]) -> dict:
        return await self.bulk_update_annotation_fields(annotation_id=annotation_id, operations=operations)

    async def _handle_confirm_annotation(self, annotation_id: int) -> dict:
        return await self.confirm_annotation(annotation_id=annotation_id)

    async def _handle_create_schema(self, name: str, content: list[dict]) -> dict:
        return await self.create_schema(name=name, content=content)

    async def _handle_create_engine(self, name: str, organization_id: int, engine_type: str) -> dict:
        return await self.create_engine(name=name, organization_id=organization_id, engine_type=engine_type)

    async def _handle_create_engine_field(
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
        return await self.create_engine_field(
            engine_id=engine_id,
            name=name,
            label=label,
            field_type=field_type,
            schema_ids=schema_ids,
            tabular=tabular,
            multiline=multiline,
            subtype=subtype,
            pre_trained_field_id=pre_trained_field_id,
        )

    async def _handle_list_hooks(self, queue_id: int | None = None, active: bool | None = None) -> dict:
        return await self.list_hooks(queue_id=queue_id, active=active)

    async def _handle_list_rules(
        self, schema_id: int | None = None, organization_id: int | None = None, enabled: bool | None = None
    ) -> dict:
        return await self.list_rules(schema_id=schema_id, organization_id=organization_id, enabled=enabled)

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

        updated_queue_data = await self.client._http_client.update.update(Resource.Queue, queue_id, queue_data)
        updated_queue = self.client._deserializer(Resource.Queue, updated_queue_data)

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

        updated_schema_data = await self.client._http_client.update(Resource.Schema, schema_id, schema_data)
        updated_schema = self.client._deserializer(Resource.Schema, updated_schema_data)

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

        updated_engine_data = await self.client._http_client.update(Resource.Engine, engine_id, engine_data)
        updated_engine = self.client._deserializer(Resource.Engine, updated_engine_data)

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
        """Start annotation to move it to 'reviewing' status.

        Args:
            annotation_id: Rossum annotation ID to start

        Returns:
            Dictionary containing success message
        """
        logger.debug(f"Starting annotation: annotation_id={annotation_id}")

        await self.client.start_annotation(annotation_id)

        return {
            "annotation_id": annotation_id,
            "message": f"Annotation {annotation_id} started successfully. Status changed to 'reviewing'.",
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
                        "id": 1234,  # Integer datapoint ID from annotation.content
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
                        "id": 5678  # Integer datapoint ID to remove
                    }
                ]

        Returns:
            Dictionary containing success message and operation count

        Example:
            # First get annotation to find datapoint IDs
            annotation = get_annotation(annotation_id=123, sideloads=['content'])
            # Find datapoint by schema_id in content and get its 'id'
            datapoint_id = 1234
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

        schema = await self.client.create_new_schema(schema_data)

        return {
            "id": schema.id,
            "name": schema.name,
            "url": schema.url,
            "content": schema.content,
            "message": f"Schema '{schema.name}' created successfully with ID {schema.id}",
        }

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
        engine = self.client._deserializer(Resource.Engine, engine_response)

        return {
            "id": engine.id,
            "name": engine.name,
            "url": engine.url,
            "type": engine.type,
            "organization": engine_data["organization"],
            "message": f"Engine '{engine.name}' created successfully with ID {engine.id}",
        }

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
        engine_field = self.client._deserializer(Resource.EngineField, engine_field_response)

        return {
            "id": engine_field.id,
            "name": engine_field.name,
            "label": engine_field.label,
            "url": engine_field.url,
            "type": engine_field.type,
            "engine": engine_field.engine,
            "tabular": engine_field.tabular,
            "multiline": engine_field.multiline,
            "subtype": engine_field.subtype,
            "pre_trained_field_id": engine_field.pre_trained_field_id,
            "schema_ids": schema_ids,
            "message": f"Engine field '{engine_field.label}' created successfully with ID {engine_field.id} and linked to {len(schema_ids)} schema(s)",
        }

    async def list_hooks(self, queue_id: int | None = None, active: bool | None = None) -> dict:
        """List all hooks/extensions, optionally filtered by queue and active status.

        Args:
            queue_id: Optional queue ID to filter hooks by queue
            active: Optional boolean to filter by active status

        Returns:
            Dictionary containing count and results list of hooks
        """
        logger.debug(f"Listing hooks: queue_id={queue_id}, active={active}")

        # Build filter parameters
        filters: dict = {}
        if queue_id is not None:
            filters["queue"] = queue_id
        if active is not None:
            filters["active"] = active

        hooks_list = [hook async for hook in self.client.list_hooks(**filters)]

        return {
            "count": len(hooks_list),
            "results": [
                {
                    "id": hook.id,
                    "name": hook.name,
                    "url": hook.url,
                    "type": hook.type,
                    "active": hook.active,
                    "queues": hook.queues,
                    "events": hook.events,
                    "config": hook.config,
                    "extension_source": hook.extension_source,
                }
                for hook in hooks_list
            ],
        }

    async def list_rules(
        self, schema_id: int | None = None, organization_id: int | None = None, enabled: bool | None = None
    ) -> dict:
        """List all rules, optionally filtered by schema, organization, and enabled status.

        Args:
            schema_id: Optional schema ID to filter rules by schema
            organization_id: Optional organization ID to filter rules by organization
            enabled: Optional boolean to filter by enabled status

        Returns:
            Dictionary containing count and results list of rules
        """
        logger.debug(f"Listing rules: schema_id={schema_id}, organization_id={organization_id}, enabled={enabled}")

        # Build filter parameters
        filters: dict = {}
        if schema_id is not None:
            filters["schema"] = schema_id
        if organization_id is not None:
            filters["organization"] = organization_id
        if enabled is not None:
            filters["enabled"] = enabled

        rules_list = [rule async for rule in self.client.list_rules(**filters)]

        return {
            "count": len(rules_list),
            "results": [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "url": rule.url,
                    "enabled": rule.enabled,
                    "organization": rule.organization,
                    "schema": rule.schema,
                    "trigger_condition": rule.trigger_condition,
                    "created_by": rule.created_by,
                    "created_at": rule.created_at,
                    "modified_by": rule.modified_by,
                    "modified_at": rule.modified_at,
                    "rule_template": rule.rule_template,
                    "synchronized_from_template": rule.synchronized_from_template,
                    "actions": [
                        {
                            "id": action.id,
                            "type": action.type,
                            "payload": action.payload,
                            "event": action.event,
                            "enabled": action.enabled,
                        }
                        for action in rule.actions
                    ],
                }
                for rule in rules_list
            ],
        }

    def _get_tool_definitions(self) -> list[Tool]:
        """Get list of tool definitions for MCP protocol.

        Filters tools based on the current mode (read-only or read-write).

        Returns:
            List of Tool objects with their schemas and descriptions
        """
        all_tool_definitions = [
            Tool(
                name="upload_document",
                description="Upload a document to Rossum. Returns: task_id, task_status, queue_id, message. Use list_annotations to get annotation ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Absolute path to document file"},
                        "queue_id": {"type": "integer", "description": "Queue ID"},
                    },
                    "required": ["file_path", "queue_id"],
                },
            ),
            Tool(
                name="get_annotation",
                description="Retrieve annotation data. Returns: id, status, url, schema, modifier, document, content, created_at, modified_at.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "annotation_id": {"type": "integer", "description": "Annotation ID"},
                        "sideloads": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional sideloads. Use ['content'] for datapoints, otherwise only metadata.",
                        },
                    },
                    "required": ["annotation_id"],
                },
            ),
            Tool(
                name="list_annotations",
                description="List annotations for a queue. Returns: count, results array.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "queue_id": {"type": "integer", "description": "Queue ID"},
                        "status": {
                            "type": "string",
                            "description": "Filter by status: 'importing', 'to_review', 'confirmed', 'exported'. Default: all four.",
                        },
                    },
                    "required": ["queue_id"],
                },
            ),
            Tool(
                name="get_queue",
                description="Retrieve queue details. Returns: id, name, url, schema, workspace, inbox, engine.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "queue_id": {"type": "integer", "description": "Queue ID"},
                    },
                    "required": ["queue_id"],
                },
            ),
            Tool(
                name="get_schema",
                description="Retrieve schema details. Returns: id, name, url, content.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema_id": {"type": "integer", "description": "Schema ID"},
                    },
                    "required": ["schema_id"],
                },
            ),
            Tool(
                name="get_queue_schema",
                description="Retrieve queue schema in one call. Returns: queue_id, queue_name, schema_id, schema_name, schema_url, schema_content.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "queue_id": {"type": "integer", "description": "Queue ID"},
                    },
                    "required": ["queue_id"],
                },
            ),
            Tool(
                name="get_queue_engine",
                description="Retrieve queue engine info. Returns: queue_id, queue_name, engine_id, engine_name, engine_url, engine_type. None if no engine assigned.",
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
                name="update_engine",
                description="Update engine settings. Returns: updated engine details, message.",
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
                name="start_annotation",
                description="Start annotation (move from 'importing' to 'to_review'). Returns: annotation_id, message.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "annotation_id": {"type": "integer", "description": "Annotation ID"},
                    },
                    "required": ["annotation_id"],
                },
            ),
            Tool(
                name="bulk_update_annotation_fields",
                description="Bulk update annotation fields. It can be used after `start_annotation` only. Returns: annotation_id, operations_count, message. Use datapoint ID from content, NOT schema_id.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "annotation_id": {"type": "integer", "description": "Annotation ID"},
                        "operations": {
                            "type": "array",
                            "description": "JSON Patch operations. Format: {'op': 'replace'|'remove', 'id': datapoint_id (int), 'value': {'content': {'value': 'new_value'}}}. Use numeric datapoint ID from annotation.content, NOT schema_id.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "op": {"type": "string", "enum": ["replace", "remove"]},
                                    "id": {
                                        "type": "integer",
                                        "description": "Datapoint ID (numeric) from annotation content",
                                    },
                                    "value": {"type": "object"},
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
                description="Confirm annotation (move to 'confirmed'). It cane be used after `bulk_update_annotation_fields`. Returns: annotation_id, message.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "annotation_id": {"type": "integer", "description": "Annotation ID"},
                    },
                    "required": ["annotation_id"],
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
            Tool(
                name="create_engine",
                description="Create a new engine. Returns: id, name, url, type, organization, message.",
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
                description="Create engine field for each schema field. Must be called when creating engine + schema. Returns: id, name, label, url, type, engine, tabular, multiline, message.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "engine_id": {"type": "integer", "description": "Engine ID"},
                        "name": {"type": "string", "description": "Field name (slug, max 50 chars)"},
                        "label": {"type": "string", "description": "Human-readable label (max 100 chars)"},
                        "field_type": {
                            "type": "string",
                            "description": "Field type",
                            "enum": ["string", "number", "date", "enum"],
                        },
                        "schema_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Schema IDs to link (≥1 required)",
                        },
                        "tabular": {"type": "boolean", "description": "Is in table? Default: false"},
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
            Tool(
                name="list_hooks",
                description="List all hooks/extensions. Returns: count, results array with hook details (id, name, url, type, active, queues, events, config, extension_source).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "queue_id": {
                            "type": ["integer", "null"],
                            "description": "Optional queue ID to filter hooks by queue",
                        },
                        "active": {
                            "type": ["boolean", "null"],
                            "description": "Optional filter by active status (true/false)",
                        },
                    },
                },
            ),
            Tool(
                name="list_rules",
                description="List all rules. Returns: count, results array with rule details (id, name, url, enabled, organization, schema, trigger_condition, created_by, created_at, modified_by, modified_at, rule_template, synchronized_from_template, actions).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema_id": {
                            "type": ["integer", "null"],
                            "description": "Optional schema ID to filter rules by schema",
                        },
                        "organization_id": {
                            "type": ["integer", "null"],
                            "description": "Optional organization ID to filter rules by organization",
                        },
                        "enabled": {
                            "type": ["boolean", "null"],
                            "description": "Optional filter by enabled status (true/false)",
                        },
                    },
                },
            ),
        ]

        # Filter tool definitions based on mode
        return [tool for tool in all_tool_definitions if self._is_tool_allowed(tool.name)]

    def setup_handlers(self) -> None:
        """Setup MCP protocol handlers.

        Registers the list_tools and call_tool handlers for the MCP server.
        These handlers define the available tools and their execution logic.

        All MCP tools return JSON strings that clients must parse with json.loads().
        This is the standard MCP protocol behavior - tools return TextContent with JSON.
        """

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return self._get_tool_definitions()

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            try:
                logger.info(f"Tool called: {name} with arguments: {arguments}")

                # Use registry to dispatch to appropriate handler
                if name not in self._tool_registry:
                    raise ValueError(f"Unknown tool: {name}")

                handler = self._tool_registry[name]
                # Unpack arguments dict into keyword arguments for type safety
                result = await handler(**arguments)

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
