"""MCP tool registrations for core get/search operations.

Builds on the entity registry (registry.py) to expose get and search
tools to the MCP server.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from enum import StrEnum
from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

from rossum_mcp.tools.get.registry import EntityConfig, build_get_registry
from rossum_mcp.tools.get.related import fetch_related
from rossum_mcp.tools.search.models import (
    SearchQuery,  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
)
from rossum_mcp.tools.search.registry import extract_search_kwargs

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


def _serialize(obj: object) -> object:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return obj


async def _get_one(
    client: AsyncRossumAPIClient, config: EntityConfig, entity: str, entity_id: int, include_related: bool
) -> dict[str, object]:
    if config.retrieve_fn is None:
        raise RuntimeError(f"Entity '{entity}' has no retrieve_fn — use search instead")
    result = await config.retrieve_fn(entity_id)
    data = _serialize(result)

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
        if _entity not in registry or registry[_entity].retrieve_fn is None:
            raise RuntimeError(
                f"EntityType member '{_entity}' is missing from registry or has no retrieve_fn — "
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
        if config.retrieve_fn is None:
            raise ToolError(f"Entity '{entity}' does not support get by ID. Use search instead.")

        if isinstance(entity_id, list):
            return await _get_many(client, config, entity, entity_id, include_related)

        return await _get_one(client, config, entity, entity_id, include_related)

    @mcp.tool(
        description="Search/list entities with typed, entity-specific filters. Pass a query object with `entity` discriminator.",
        tags={"read"},
        annotations={"readOnlyHint": True},
    )
    async def search(query: SearchQuery, first_n: int | None = None) -> list[object]:
        entity = query.entity
        config = registry.get(entity)
        if config is None:
            raise ToolError(f"Unknown entity type: {entity}")
        if config.search_fn is None:
            raise ToolError(f"Entity '{entity}' does not support search/list.")

        kwargs = extract_search_kwargs(query)
        if first_n is not None:
            kwargs["max_items"] = first_n
        result = await config.search_fn(**kwargs)
        return [_serialize(item) for item in result]
