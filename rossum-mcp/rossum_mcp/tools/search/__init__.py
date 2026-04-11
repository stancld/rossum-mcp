from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

from rossum_mcp.tools.base import serialize_dataclass
from rossum_mcp.tools.search.models import (
    SearchQuery,  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
)
from rossum_mcp.tools.search.registry import build_search_registry, extract_search_kwargs

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient


def register_search_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    search_registry = build_search_registry(client)

    @mcp.tool(
        description="Search/list entities with typed, entity-specific filters. Pass a query object with `entity` discriminator.",
        tags={"read"},
        annotations={"readOnlyHint": True},
    )
    async def search(query: SearchQuery, first_n: int | None = None) -> list[object]:
        entity = query.entity
        search_fn = search_registry.get(entity)
        if search_fn is None:
            raise ToolError(f"Entity '{entity}' does not support search/list.")

        kwargs = extract_search_kwargs(query)
        if first_n is not None:
            kwargs["max_items"] = first_n
        result = await search_fn(**kwargs)
        return [serialize_dataclass(item) for item in result]
