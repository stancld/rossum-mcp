"""include_related fetchers for enriched get responses.

Only meaningful for a few entities. Uses asyncio.gather for parallel fetches.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError
from rossum_api import APIClientError
from rossum_api.domain_logic.resources import Resource
from rossum_api.models import deserialize_default
from rossum_api.models.engine import Engine
from rossum_api.models.hook import Hook
from rossum_api.models.queue import Queue

from rossum_mcp.tools.base import build_filters, extract_id_from_url, graceful_list
from rossum_mcp.tools.get.schemas import extract_schema_tree
from rossum_mcp.tools.search.registry import _list_hooks

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def fetch_related(
    client: AsyncRossumAPIClient, entity: str, entity_id: int, obj: object | None = None
) -> dict[str, object] | None:
    """Fetch related data for an entity. Returns None if no fetcher exists."""
    fetcher: Callable[..., Awaitable[dict[str, object]]] | None = RELATED_FETCHERS.get(entity)
    if fetcher is None:
        return None
    return await fetcher(client, entity_id, obj)


async def _get_queue_engine(client: AsyncRossumAPIClient, queue_id: int) -> Engine | dict:
    """Retrieve the engine assigned to a queue."""
    logger.debug(f"Retrieving queue engine: queue_id={queue_id}")
    queue: Queue = await client.retrieve_queue(queue_id)

    engine_url = None
    if queue.dedicated_engine:
        engine_url = queue.dedicated_engine
    elif queue.generic_engine:
        engine_url = queue.generic_engine
    elif queue.engine:
        engine_url = queue.engine

    if not engine_url:
        return {"message": "No engine assigned to this queue"}

    try:
        if isinstance(engine_url, str):
            engine_id = extract_id_from_url(engine_url)
            engine: Engine = await client.retrieve_engine(engine_id)
        else:
            engine = deserialize_default(Resource.Engine, engine_url)
    except APIClientError as e:
        if e.status_code == 404:
            return {"message": f"Engine not found (engine URL: {engine_url})"}
        raise

    return engine


async def _get_schema_tree_structure(
    client: AsyncRossumAPIClient, schema_id: int | None = None, queue_id: int | None = None
) -> list[dict]:
    """Get lightweight schema tree structure. Used by related fetchers."""
    # Import here to avoid circular import: get.related → get.registry → search.registry → ... → get.related
    from rossum_mcp.tools.get.registry import _get_schema  # noqa: PLC0415 - circular import avoidance

    if schema_id is None and queue_id is None:
        raise ToolError("Provide schema_id or queue_id")
    if schema_id is not None and queue_id is not None:
        raise ToolError("Provide schema_id or queue_id, not both")
    if queue_id:
        queue = await client.retrieve_queue(queue_id)
        schema_id = extract_id_from_url(queue.schema)
    schema = await _get_schema(client, schema_id)  # ty:ignore[invalid-argument-type]
    return extract_schema_tree(schema)


async def _fetch_queue_related(
    client: AsyncRossumAPIClient, queue_id: int, _obj: object | None = None
) -> dict[str, object]:
    schema_tree, engine, hooks = await asyncio.gather(
        _get_schema_tree_structure(client, queue_id=queue_id),
        _get_queue_engine(client, queue_id),
        _list_hooks(client, queue_id=queue_id),
        return_exceptions=True,
    )

    related: dict[str, object] = {}

    if isinstance(schema_tree, BaseException):
        logger.warning(f"Failed to fetch schema tree for queue {queue_id}: {schema_tree}")
    else:
        related["schema_tree"] = schema_tree

    if isinstance(engine, BaseException):
        logger.warning(f"Failed to fetch engine for queue {queue_id}: {engine}")
    else:
        related["engine"] = engine

    if isinstance(hooks, BaseException):
        logger.warning(f"Failed to fetch hooks for queue {queue_id}: {hooks}")
    else:
        related["hooks"] = [{"id": h.id, "name": h.name, "active": h.active} for h in hooks]
        related["hooks_count"] = len(hooks)

    return related


async def _fetch_schema_related(
    client: AsyncRossumAPIClient, schema_id: int, _obj: object | None = None
) -> dict[str, object]:
    queue_result, rules_result = await asyncio.gather(
        graceful_list(client, Resource.Queue, "queue", **build_filters(schema=schema_id)),
        graceful_list(client, Resource.Rule, "rule", **build_filters(schema=schema_id)),
    )

    return {
        "queues": [q.url for q in queue_result.items],
        "rules": [{"id": r.id, "name": r.name, "enabled": r.enabled} for r in rules_result.items],
    }


async def _fetch_hook_related(
    client: AsyncRossumAPIClient, hook_id: int, obj: object | None = None
) -> dict[str, object]:
    # Use the already-fetched hook if available; avoids a redundant network call.
    hook = obj if isinstance(obj, Hook) else await client.retrieve_hook(hook_id)
    return {
        "queues": list(hook.queues) if hook.queues else [],
        "events": list(hook.events) if hook.events else [],
    }


RELATED_FETCHERS: dict[str, Callable[..., Awaitable[dict[str, object]]]] = {
    "queue": _fetch_queue_related,
    "schema": _fetch_schema_related,
    "hook": _fetch_hook_related,
}
