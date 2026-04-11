from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_mcp.tools.base import delete_resource

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient


async def _delete_annotation(client: AsyncRossumAPIClient, annotation_id: int) -> dict:
    return await delete_resource(
        "annotation", annotation_id, client.delete_annotation, f"Annotation {annotation_id} moved to 'deleted' status"
    )
