"""Annotation tools for Rossum MCP Server."""

from __future__ import annotations

import logging
from collections.abc import Sequence  # noqa: TC003 - needed at runtime for FastMCP
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from rossum_api.models.annotation import Annotation

from rossum_mcp.tools.base import is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)

type Sideload = Literal["content", "document", "automation_blocker"]


async def _upload_document(client: AsyncRossumAPIClient, file_path: str, queue_id: int) -> dict:
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


async def _get_annotation(
    client: AsyncRossumAPIClient, annotation_id: int, sideloads: Sequence[Sideload] = ()
) -> Annotation:
    logger.debug(f"Retrieving annotation: annotation_id={annotation_id}")
    annotation: Annotation = await client.retrieve_annotation(annotation_id, sideloads)  # type: ignore[arg-type]
    return annotation


async def _list_annotations(
    client: AsyncRossumAPIClient,
    queue_id: int,
    status: str | None = "importing,to_review,confirmed,exported",
    ordering: Sequence[str] = (),
    first_n: int | None = None,
) -> list[Annotation]:
    logger.debug(f"Listing annotations: queue_id={queue_id}, status={status}, ordering={ordering}, first_n={first_n}")
    params: dict = {"queue": queue_id, "page_size": 100}
    if status:
        params["status"] = status
    if ordering:
        params["ordering"] = ordering

    annotations_list: list[Annotation] = []
    async for item in client.list_annotations(**params):
        annotations_list.append(item)
        if first_n is not None and len(annotations_list) >= first_n:
            break
    return annotations_list


async def _start_annotation(client: AsyncRossumAPIClient, annotation_id: int) -> dict:
    if not is_read_write_mode():
        return {"error": "start_annotation is not available in read-only mode"}

    logger.debug(f"Starting annotation: annotation_id={annotation_id}")
    await client.start_annotation(annotation_id)
    return {
        "annotation_id": annotation_id,
        "message": f"Annotation {annotation_id} started successfully. Status changed to 'reviewing'.",
    }


async def _bulk_update_annotation_fields(
    client: AsyncRossumAPIClient, annotation_id: int, operations: list[dict]
) -> dict:
    if not is_read_write_mode():
        return {"error": "bulk_update_annotation_fields is not available in read-only mode"}

    logger.debug(f"Bulk updating annotation: annotation_id={annotation_id}, ops={operations}")
    await client.bulk_update_annotation_data(annotation_id, operations)
    return {
        "annotation_id": annotation_id,
        "operations_count": len(operations),
        "message": f"Annotation {annotation_id} updated with {len(operations)} operations successfully.",
    }


async def _confirm_annotation(client: AsyncRossumAPIClient, annotation_id: int) -> dict:
    if not is_read_write_mode():
        return {"error": "confirm_annotation is not available in read-only mode"}

    logger.debug(f"Confirming annotation: annotation_id={annotation_id}")
    await client.confirm_annotation(annotation_id)
    return {
        "annotation_id": annotation_id,
        "message": f"Annotation {annotation_id} confirmed successfully. Status changed to 'confirmed'.",
    }


def register_annotation_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register annotation-related tools with the FastMCP server."""

    @mcp.tool(description="Upload a document to Rossum. Use list_annotations to get annotation ID.")
    async def upload_document(file_path: str, queue_id: int) -> dict:
        return await _upload_document(client, file_path, queue_id)

    @mcp.tool(description="Retrieve annotation data. Use 'content' sideload to get extracted data.")
    async def get_annotation(annotation_id: int, sideloads: Sequence[Sideload] = ()) -> Annotation:
        return await _get_annotation(client, annotation_id, sideloads)

    @mcp.tool(description="List annotations for a queue. Use ordering=['-created_at'] to sort by newest first.")
    async def list_annotations(
        queue_id: int,
        status: str | None = "importing,to_review,confirmed,exported",
        ordering: Sequence[str] = (),
        first_n: int | None = None,
    ) -> list[Annotation]:
        return await _list_annotations(client, queue_id, status, ordering, first_n)

    @mcp.tool(description="Start annotation (move from 'to_review' to 'reviewing').")
    async def start_annotation(annotation_id: int) -> dict:
        return await _start_annotation(client, annotation_id)

    @mcp.tool(
        description="Bulk update annotation fields. It can be used after `start_annotation` only. Use datapoint ID from content, NOT schema_id."
    )
    async def bulk_update_annotation_fields(annotation_id: int, operations: list[dict]) -> dict:
        return await _bulk_update_annotation_fields(client, annotation_id, operations)

    @mcp.tool(
        description="Confirm annotation (move to 'confirmed'). It can be used after `bulk_update_annotation_fields`."
    )
    async def confirm_annotation(annotation_id: int) -> dict:
        return await _confirm_annotation(client, annotation_id)
