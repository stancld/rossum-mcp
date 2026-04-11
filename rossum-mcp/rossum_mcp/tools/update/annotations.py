from __future__ import annotations

import logging

from fastmcp import FastMCP
from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _start_annotation(client: AsyncRossumAPIClient, annotation_id: int) -> dict:
    logger.debug(f"Starting annotation: annotation_id={annotation_id}")
    await client.start_annotation(annotation_id)
    return {
        "annotation_id": annotation_id,
        "message": f"Annotation {annotation_id} started successfully. Status changed to 'reviewing'.",
    }


async def _bulk_update_annotation_fields(
    client: AsyncRossumAPIClient, annotation_id: int, operations: list[dict]
) -> dict:
    logger.debug(f"Bulk updating annotation: annotation_id={annotation_id}, ops={operations}")
    await client.bulk_update_annotation_data(annotation_id, operations)
    return {
        "annotation_id": annotation_id,
        "operations_count": len(operations),
        "message": f"Annotation {annotation_id} updated with {len(operations)} operations successfully.",
    }


async def _confirm_annotation(client: AsyncRossumAPIClient, annotation_id: int) -> dict:
    logger.debug(f"Confirming annotation: annotation_id={annotation_id}")
    await client.confirm_annotation(annotation_id)
    return {
        "annotation_id": annotation_id,
        "message": f"Annotation {annotation_id} confirmed successfully. Status changed to 'confirmed'.",
    }


def register_annotation_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Set annotation status to 'reviewing' (from 'to_review').",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def start_annotation(annotation_id: int) -> dict:
        return await _start_annotation(client, annotation_id)

    @mcp.tool(
        description="Bulk update extracted fields. Requires annotation in 'reviewing' status. Use datapoint IDs from content, not schema_id.",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def bulk_update_annotation_fields(annotation_id: int, operations: list[dict]) -> dict:
        return await _bulk_update_annotation_fields(client, annotation_id, operations)

    @mcp.tool(
        description="Set annotation status to 'confirmed' (typically after field updates).",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def confirm_annotation(annotation_id: int) -> dict:
        return await _confirm_annotation(client, annotation_id)
