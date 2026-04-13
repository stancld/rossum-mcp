from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_mcp.tools.base import delete_resource

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient


async def _delete_schema(client: AsyncRossumAPIClient, schema_id: int) -> dict:
    return await delete_resource("schema", schema_id, client.delete_schema)
