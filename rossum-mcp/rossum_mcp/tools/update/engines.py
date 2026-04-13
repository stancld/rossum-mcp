from __future__ import annotations

import logging
from typing import cast

from fastmcp import FastMCP
from rossum_api import AsyncRossumAPIClient
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.engine import Engine

from rossum_mcp.tools.update.models import (
    EngineUpdateData,  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
)

logger = logging.getLogger(__name__)


async def _update_engine(client: AsyncRossumAPIClient, engine_id: int, engine_data: EngineUpdateData) -> Engine | dict:
    logger.debug(f"Updating engine: engine_id={engine_id}, data={engine_data}")
    updated_engine_data = await client._http_client.update(Resource.Engine, engine_id, dict(engine_data))
    return cast("Engine", client._deserializer(Resource.Engine, updated_engine_data))


def register_engine_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Update engine settings.",
        tags={"engines", "write"},
        annotations={"readOnlyHint": False},
    )
    async def update_engine(engine_id: int, engine_data: EngineUpdateData) -> Engine | dict:
        return await _update_engine(client, engine_id, engine_data)
