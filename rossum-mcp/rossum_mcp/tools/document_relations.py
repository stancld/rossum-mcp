"""Document relation tools for Rossum MCP Server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.models.document_relation import (
    DocumentRelation,  # noqa: TC002 - needed at runtime for FastMCP
)

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def register_document_relation_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register document relation-related tools with the FastMCP server."""

    @mcp.tool(description="Retrieve document relation details.")
    async def get_document_relation(document_relation_id: int) -> DocumentRelation:
        """Retrieve document relation details."""
        logger.debug(f"Retrieving document relation: document_relation_id={document_relation_id}")
        document_relation: DocumentRelation = await client.retrieve_document_relation(document_relation_id)
        return document_relation

    @mcp.tool(
        description="List all document relations with optional filters. Document relations introduce additional relations between annotations and documents (export, einvoice)."
    )
    async def list_document_relations(
        id: int | None = None,
        type: str | None = None,
        annotation: int | None = None,
        key: str | None = None,
        documents: int | None = None,
    ) -> list[DocumentRelation]:
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

        return [
            document_relation
            async for document_relation in client.list_document_relations(**filters)  # type: ignore[arg-type]
        ]
