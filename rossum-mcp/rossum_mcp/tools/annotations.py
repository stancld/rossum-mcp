"""Annotation tools for Rossum MCP Server."""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Sequence  # noqa: TC003 - needed at runtime for FastMCP
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from rossum_mcp.tools.base import is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient
    from rossum_api.models.annotation import Annotation

logger = logging.getLogger(__name__)

# Fixed sideloads (critical for well-behaving agent)
type Sideload = Literal["content", "document", "automation_blocker"]


def register_annotation_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:  # noqa: C901
    """Register annotation-related tools with the FastMCP server."""

    @mcp.tool(
        description="Upload a document to Rossum. Returns: task_id, task_status, queue_id, message. Use list_annotations to get annotation ID."
    )
    async def upload_document(file_path: str, queue_id: int) -> dict:
        """Upload a document to Rossum."""
        if not is_read_write_mode():
            return {"error": "upload_document is not available in read-only mode"}

        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            task = (await client.upload_document(queue_id, [(str(path), path.name)]))[0]
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
                f"Document upload failed - no tasks were created. This may indicate the queue_id ({queue_id}) is invalid."
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

    @mcp.tool(
        description="Retrieve annotation data. Returns: id, status, url, schema, modifier, content, created_at, modified_at. "
        "Use 'content' to get extracted data."
    )
    async def get_annotation(annotation_id: int, sideloads: Sequence[Sideload] = ()) -> dict:
        """Retrieve annotation data from Rossum."""
        logger.debug(f"Retrieving annotation: annotation_id={annotation_id}")
        try:
            annotation: Annotation = await client.retrieve_annotation(annotation_id, sideloads)  # type: ignore[arg-type]
            return dataclasses.asdict(annotation)
        except KeyError as e:
            logger.error(f"Failed to retrieve annotation {annotation_id}: KeyError {e}")
            return {
                "error": f"Failed to retrieve annotation {annotation_id}. "
                f"Invalid sideload requested: {e}. "
                f"Valid sideloads for annotations are: 'content', 'document', 'automation_blocker'."
            }

    @mcp.tool(description="List annotations for a queue. Returns: count, results array.")
    async def list_annotations(queue_id: int, status: str | None = "importing,to_review,confirmed,exported") -> dict:
        """List annotations for a queue with optional filtering."""
        logger.debug(f"Listing annotations: queue_id={queue_id}, status={status}")
        params: dict = {"queue": queue_id, "page_size": 100}
        if status:
            params["status"] = status
        annotations_list: list[Annotation] = [item async for item in client.list_annotations(**params)]
        return {"count": len(annotations_list), "results": [dataclasses.asdict(ann) for ann in annotations_list]}

    @mcp.tool(description="Start annotation (move from 'importing' to 'to_review'). Returns: annotation_id, message.")
    async def start_annotation(annotation_id: int) -> dict:
        """Start annotation to move it to 'reviewing' status."""
        if not is_read_write_mode():
            return {"error": "start_annotation is not available in read-only mode"}

        logger.debug(f"Starting annotation: annotation_id={annotation_id}")
        await client.start_annotation(annotation_id)
        return {
            "annotation_id": annotation_id,
            "message": f"Annotation {annotation_id} started successfully. Status changed to 'reviewing'.",
        }

    @mcp.tool(
        description="Bulk update annotation fields. It can be used after `start_annotation` only. Returns: annotation_id, operations_count, message. Use datapoint ID from content, NOT schema_id."
    )
    async def bulk_update_annotation_fields(annotation_id: int, operations: list[dict]) -> dict:
        """Bulk update annotation field values using operations."""
        if not is_read_write_mode():
            return {"error": "bulk_update_annotation_fields is not available in read-only mode"}

        logger.debug(f"Bulk updating annotation: annotation_id={annotation_id}, ops={operations}")
        await client.bulk_update_annotation_data(annotation_id, operations)
        return {
            "annotation_id": annotation_id,
            "operations_count": len(operations),
            "message": f"Annotation {annotation_id} updated with {len(operations)} operations successfully.",
        }

    @mcp.tool(
        description="Confirm annotation (move to 'confirmed'). It can be used after `bulk_update_annotation_fields`. Returns: annotation_id, message."
    )
    async def confirm_annotation(annotation_id: int) -> dict:
        """Confirm annotation to move it to 'confirmed' status."""
        if not is_read_write_mode():
            return {"error": "confirm_annotation is not available in read-only mode"}

        logger.debug(f"Confirming annotation: annotation_id={annotation_id}")
        await client.confirm_annotation(annotation_id)
        return {
            "annotation_id": annotation_id,
            "message": f"Annotation {annotation_id} confirmed successfully. Status changed to 'confirmed'.",
        }
