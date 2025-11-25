"""Annotation operations handler for Rossum MCP Server"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from mcp.types import Tool

from rossum_mcp.handlers.base import BaseHandler

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rossum_api.models.annotation import Annotation
    from rossum_api.types import Sideload

logger = logging.getLogger(__name__)


class AnnotationsHandler(BaseHandler):
    """Handler for annotation-related operations"""

    @classmethod
    def get_tool_definitions(cls) -> list[Tool]:
        """Get list of tool definitions for annotation operations."""
        return [
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
        ]

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

    async def get_annotation(self, annotation_id: int, sideloads: Sequence[Sideload] = ()) -> dict:
        """Retrieve annotation data from Rossum.

        Args:
            annotation_id: The annotation ID to retrieve
            sideloads: List of sideloads to include (e.g., ['content'])

        Returns:
            Dictionary containing annotation details including id, status, url, content, etc.
        """
        logger.debug(f"Retrieving annotation: annotation_id={annotation_id}")

        annotation: Annotation = await self.client.retrieve_annotation(annotation_id, sideloads)

        return dataclasses.asdict(annotation)

    async def list_annotations(
        self, queue_id: int, status: str | None = "importing,to_review,confirmed,exported"
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

        annotations_list: list[Annotation] = [item async for item in self.client.list_annotations(**params)]

        return {
            "count": len(annotations_list),
            "results": [dataclasses.asdict(ann) for ann in annotations_list],
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
