from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.models.engine import EngineField

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_engine_fields(client: AsyncRossumAPIClient, engine_id: int | None = None) -> list[EngineField]:
    logger.debug(f"Retrieving engine fields: engine_id={engine_id}")
    return [engine_field async for engine_field in client.retrieve_engine_fields(engine_id=engine_id)]


def register_engine_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Retrieve engine fields for a specific engine or all engine fields.",
        tags={"engines"},
        annotations={"readOnlyHint": True},
    )
    async def get_engine_fields(engine_id: int | None = None) -> list[EngineField]:
        return await _get_engine_fields(client, engine_id)
