"""Document relation tools for Rossum MCP Server."""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient
    from rossum_api.models.document_relation import DocumentRelation

logger = logging.getLogger(__name__)


def register_document_relation_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register document relation-related tools with the FastMCP server."""

    @mcp.tool(description="Retrieve document relation details. Returns: id, type, annotation, key, documents, url.")
    async def get_document_relation(document_relation_id: int) -> dict:
        """Retrieve document relation details."""
        logger.debug(f"Retrieving document relation: document_relation_id={document_relation_id}")
        document_relation_data = await client._http_client.fetch_one(Resource.DocumentRelation, document_relation_id)
        document_relation_obj: DocumentRelation = client._deserializer(
            Resource.DocumentRelation, document_relation_data
        )
        return dataclasses.asdict(document_relation_obj)

    @mcp.tool(
        description="List all document relations with optional filters. Document relations introduce additional relations between annotations and documents (export, einvoice). Returns: count, results array with document relation details (id, type, annotation, key, documents, url)."
    )
    async def list_document_relations(
        id: int | None = None,
        type: str | None = None,
        annotation: int | None = None,
        key: str | None = None,
        documents: int | None = None,
    ) -> dict:
        """List all document relations with optional filters."""
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
            async for document_relation in client.list_document_relations(**filters)  # type: ignore[arg-type]
        ]
        return {
            "count": len(document_relations_list),
            "results": [dataclasses.asdict(dr) for dr in document_relations_list],
        }
