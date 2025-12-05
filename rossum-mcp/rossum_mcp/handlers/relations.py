"""Relation operations handler for Rossum MCP Server"""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from mcp.types import Tool
from rossum_api.domain_logic.resources import Resource

from rossum_mcp.handlers.base import BaseHandler

if TYPE_CHECKING:
    from rossum_api.models.relation import Relation

logger = logging.getLogger(__name__)


class RelationsHandler(BaseHandler):
    """Handler for relation-related operations"""

    @classmethod
    def get_tool_definitions(cls) -> list[Tool]:
        """Get list of tool definitions for relation operations."""
        return [
            Tool(
                name="get_relation",
                description="Retrieve relation details. Returns: id, type, key, parent, annotations, url.",
                inputSchema={
                    "type": "object",
                    "properties": {"relation_id": {"type": "integer", "description": "Relation ID"}},
                    "required": ["relation_id"],
                },
            ),
            Tool(
                name="list_relations",
                description="List all relations with optional filters. Relations introduce common relations between annotations (edit, attachment, duplicate). Returns: count, results array with relation details (id, type, key, parent, annotations, url).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": ["integer", "null"],
                            "description": "Optional relation ID filter",
                        },
                        "type": {
                            "type": ["string", "null"],
                            "description": "Optional relation type filter ('edit', 'attachment', 'duplicate')",
                        },
                        "parent": {
                            "type": ["integer", "null"],
                            "description": "Optional parent annotation ID filter",
                        },
                        "key": {
                            "type": ["string", "null"],
                            "description": "Optional relation key filter",
                        },
                        "annotation": {
                            "type": ["integer", "null"],
                            "description": "Optional annotation ID filter",
                        },
                    },
                },
            ),
        ]

    async def get_relation(self, relation_id: int) -> dict:
        """Retrieve relation details.

        Args:
            relation_id: Rossum relation ID to retrieve

        Returns:
            Dictionary containing relation details
        """
        logger.debug(f"Retrieving relation: relation_id={relation_id}")

        relation_data = await self.client._http_client.fetch_one(Resource.Relation, relation_id)
        relation_obj: Relation = self.client._deserializer(Resource.Relation, relation_data)
        return dataclasses.asdict(relation_obj)

    async def list_relations(
        self,
        id: int | None = None,
        type: str | None = None,
        parent: int | None = None,
        key: str | None = None,
        annotation: int | None = None,
    ) -> dict:
        """List all relations with optional filters.

        Args:
            id: Optional relation ID filter
            type: Optional relation type filter ('edit', 'attachment', 'duplicate')
            parent: Optional parent annotation ID filter
            key: Optional relation key filter
            annotation: Optional annotation ID filter

        Returns:
            Dictionary containing list of relations with count and results
        """
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

        relations_list = [relation async for relation in self.client.list_relations(**filters)]  # type: ignore[arg-type]

        return {"count": len(relations_list), "results": [dataclasses.asdict(relation) for relation in relations_list]}
