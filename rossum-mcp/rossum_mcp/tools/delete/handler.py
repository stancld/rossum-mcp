from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

from rossum_mcp.tools.delete.models import DeleteEntityType
from rossum_mcp.tools.delete.registry import build_delete_registry

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient


def register_delete_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    registry = build_delete_registry(client)

    # Fail fast at startup if DeleteEntityType drifts from the registry
    for _entity in DeleteEntityType:
        if _entity not in registry:
            raise RuntimeError(
                f"DeleteEntityType member '{_entity}' is missing from registry — "
                "update DeleteEntityType or build_delete_registry to keep them in sync"
            )

    @mcp.tool(
        description=(
            "Delete an entity by ID. "
            "Entity-specific behavior: "
            "queue → deletion begins after ~24h, cascades to annotations/documents; "
            "annotation → soft-delete (status 'deleted'); "
            "workspace → fails if it still contains queues; "
            "schema → fails with 409 if linked to any queue/annotation; "
            "inbox → removes email ingestion for the linked queue; "
            "connector → removes external validation/export endpoint."
        ),
        tags={"write"},
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def delete(entity: DeleteEntityType, entity_id: int) -> dict:
        delete_fn = registry.get(entity)
        if delete_fn is None:
            raise ToolError(f"Unknown entity type: {entity}")

        return await delete_fn(entity_id)
