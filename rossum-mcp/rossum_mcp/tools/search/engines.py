from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.engine import Engine

from rossum_mcp.models.engine import EngineType  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
from rossum_mcp.tools.base import build_filters, graceful_list

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _list_engines(
    client: AsyncRossumAPIClient,
    engine_type: EngineType | None = None,
    agenda_id: str | None = None,
    max_items: int | None = None,
) -> list[Engine]:
    logger.debug(f"Listing engines: type={engine_type}, agenda_id={agenda_id}")
    filters = build_filters(type=engine_type, agenda_id=agenda_id)
    result = await graceful_list(client, Resource.Engine, "engine", max_items=max_items, **filters)
    return result.items
