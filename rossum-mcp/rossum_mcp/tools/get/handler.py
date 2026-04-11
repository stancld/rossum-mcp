"""MCP tool registrations for core get operations.

Builds on the entity registry (registry.py) to expose the get tool to the MCP server.
"""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

from rossum_mcp.tools.base import serialize_dataclass
from rossum_mcp.tools.get.registry import EntityConfig, build_get_registry
from rossum_mcp.tools.get.related import fetch_related

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


class EntityType(StrEnum):
    QUEUE = "queue"
    SCHEMA = "schema"
    HOOK = "hook"
    ENGINE = "engine"
    RULE = "rule"
    USER = "user"
    WORKSPACE = "workspace"
    EMAIL_TEMPLATE = "email_template"
    ORGANIZATION_GROUP = "organization_group"
    ANNOTATION = "annotation"
    RELATION = "relation"
    DOCUMENT_RELATION = "document_relation"
    ORGANIZATION_LIMIT = "organization_limit"
    HOOK_SECRETS_KEYS = "hook_secrets_keys"


async def _get_one(
    client: AsyncRossumAPIClient, config: EntityConfig, entity: str, entity_id: int, include_related: bool
) -> dict[str, object]:
    result = await config.retrieve_fn(entity_id)
    data = serialize_dataclass(result)

    response: dict[str, object] = {"entity": entity, "id": entity_id, "data": data}

    if include_related:
        related = await fetch_related(client, entity, entity_id, result)
        if related:
            response["_related"] = related

    return response


async def _get_many(
    client: AsyncRossumAPIClient, config: EntityConfig, entity: str, entity_ids: list[int], include_related: bool
) -> list[dict[str, object]]:
    tasks = [_get_one(client, config, entity, eid, include_related) for eid in entity_ids]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[dict[str, object]] = []
    skipped = 0
    for entity_id, response in zip(entity_ids, responses, strict=True):
        if isinstance(response, Exception):
            logger.warning(f"Failed to retrieve {entity} (id={entity_id}), skipping")
            skipped += 1
        else:
            results.append(response)

    if skipped:
        logger.warning(f"Skipped {skipped} {entity} item(s) that failed to retrieve")

    return results


def register_core_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    registry = build_get_registry(client)

    # Fail fast at startup if EntityType drifts from the registry
    for _entity in EntityType:
        if _entity not in registry:
            raise RuntimeError(
                f"EntityType member '{_entity}' is missing from registry — "
                "update EntityType or build_get_registry to keep them in sync"
            )

    @mcp.tool(
        description=(
            "Get entities by ID. Accepts a single ID or a list of IDs for batch retrieval. "
            "include_related=True enriches with related data (queue->schema_tree+engine+hooks, schema->queues+rules, hook->queues+events). "
            "hook_secrets_keys returns stored secret key names (values are write-only, never returned)."
        ),
        tags={"read"},
        annotations={"readOnlyHint": True},
    )
    async def get(
        entity: EntityType, entity_id: int | list[int], include_related: bool = False
    ) -> dict[str, object] | list[dict[str, object]]:
        config = registry.get(entity)
        if config is None:
            raise ToolError(f"Unknown entity type: {entity}")

        if isinstance(entity_id, list):
            return await _get_many(client, config, entity, entity_id, include_related)

        return await _get_one(client, config, entity, entity_id, include_related)
