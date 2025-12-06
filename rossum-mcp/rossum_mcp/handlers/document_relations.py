"""Document relation operations handler for Rossum MCP Server"""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from mcp.types import Tool
from rossum_api.domain_logic.resources import Resource

from rossum_mcp.handlers.base import BaseHandler

if TYPE_CHECKING:
    from rossum_api.models.document_relation import DocumentRelation

logger = logging.getLogger(__name__)


class DocumentRelationsHandler(BaseHandler):
    """Handler for document relation-related operations"""

    @classmethod
    def get_tool_definitions(cls) -> list[Tool]:
        """Get list of tool definitions for document relation operations."""
        return [
            Tool(
                name="get_document_relation",
                description="Retrieve document relation details. Returns: id, type, annotation, key, documents, url.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document_relation_id": {
                            "type": "integer",
                            "description": "Document relation ID",
                        }
                    },
                    "required": ["document_relation_id"],
                },
            ),
            Tool(
                name="list_document_relations",
                description="List all document relations with optional filters. Document relations introduce additional relations between annotations and documents (export, einvoice). Returns: count, results array with document relation details (id, type, annotation, key, documents, url).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": ["integer", "null"],
                            "description": "Optional document relation ID filter",
                        },
                        "type": {
                            "type": ["string", "null"],
                            "description": "Optional relation type filter ('export', 'einvoice')",
                        },
                        "annotation": {
                            "type": ["integer", "null"],
                            "description": "Optional annotation ID filter",
                        },
                        "key": {
                            "type": ["string", "null"],
                            "description": "Optional relation key filter",
                        },
                        "documents": {
                            "type": ["integer", "null"],
                            "description": "Optional document ID filter",
                        },
                    },
                },
            ),
        ]

    async def get_document_relation(self, document_relation_id: int) -> dict:
        """Retrieve document relation details.

        Args:
            document_relation_id: Rossum document relation ID to retrieve

        Returns:
            Dictionary containing document relation details
        """
        logger.debug(f"Retrieving document relation: document_relation_id={document_relation_id}")

        document_relation_data = await self.client._http_client.fetch_one(
            Resource.DocumentRelation, document_relation_id
        )
        document_relation_obj: DocumentRelation = self.client._deserializer(
            Resource.DocumentRelation, document_relation_data
        )
        return dataclasses.asdict(document_relation_obj)

    async def list_document_relations(
        self,
        id: int | None = None,
        type: str | None = None,
        annotation: int | None = None,
        key: str | None = None,
        documents: int | None = None,
    ) -> dict:
        """List all document relations with optional filters.

        Args:
            id: Optional document relation ID filter
            type: Optional relation type filter ('export', 'einvoice')
            annotation: Optional annotation ID filter
            key: Optional relation key filter
            documents: Optional document ID filter

        Returns:
            Dictionary containing list of document relations with count and results
        """
        logger.debug(
            f"Listing document relations: id={id}, type={type}, annotation={annotation}, key={key}, documents={documents}"
        )

        filters: dict[str, int | str] = {}
        if id is not None:
            filters["id"] = id
        if type is not None:
            filters["type"] = type
        if annotation is not None:
            filters["annotation"] = annotation
        if key is not None:
            filters["key"] = key
        if documents is not None:
            filters["documents"] = documents

        document_relations_list = [
            document_relation
            async for document_relation in self.client.list_document_relations(**filters)  # type: ignore[arg-type]
        ]

        return {
            "count": len(document_relations_list),
            "results": [dataclasses.asdict(dr) for dr in document_relations_list],
        }
