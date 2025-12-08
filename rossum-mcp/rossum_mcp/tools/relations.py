"""Relation tools for Rossum MCP Server."""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient
    from rossum_api.models.relation import Relation

logger = logging.getLogger(__name__)


def register_relation_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register relation-related tools with the FastMCP server."""

    @mcp.tool(description="Retrieve relation details. Returns: id, type, key, parent, annotations, url.")
    async def get_relation(relation_id: int) -> dict:
        """Retrieve relation details."""
        logger.debug(f"Retrieving relation: relation_id={relation_id}")
        relation_data = await client._http_client.fetch_one(Resource.Relation, relation_id)
        relation_obj: Relation = client._deserializer(Resource.Relation, relation_data)
        return dataclasses.asdict(relation_obj)

    @mcp.tool(
        description="List all relations with optional filters. Relations introduce common relations between annotations (edit, attachment, duplicate). Returns: count, results array with relation details (id, type, key, parent, annotations, url)."
    )
    async def list_relations(
        id: int | None = None,
        type: str | None = None,
        parent: int | None = None,
        key: str | None = None,
        annotation: int | None = None,
    ) -> dict:
        """List all relations with optional filters."""
        logger.debug(f"Listing relations: id={id}, type={type}, parent={parent}, key={key}, annotation={annotation}")
        filters: dict[str, int | str] = {}
        if id is not None:
            filters["id"] = id
        if type is not None:
            filters["type"] = type
        if parent is not None:
            filters["parent"] = parent
        if key is not None:
            filters["key"] = key
        if annotation is not None:
            filters["annotation"] = annotation

        relations_list = [relation async for relation in client.list_relations(**filters)]  # type: ignore[arg-type]
        return {
            "count": len(relations_list),
            "results": [dataclasses.asdict(relation) for relation in relations_list],
        }
