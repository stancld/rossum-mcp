from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_mcp.tools.base import delete_resource

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient


async def _delete_queue(client: AsyncRossumAPIClient, queue_id: int) -> dict:
    return await delete_resource(
        "queue", queue_id, client.delete_queue, f"Queue {queue_id} scheduled for deletion (starts after 24 hours)"
    )
