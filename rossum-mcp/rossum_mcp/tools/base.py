from __future__ import annotations

import asyncio
import dataclasses
import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Generic, TypeVar

from rossum_api.domain_logic.resources import Resource

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Any

    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class GracefulListResult(Generic[T]):  # noqa: UP046 - PEP 695 breaks sphinx-autodoc-typehints with PEP 563
    items: list[T]
    skipped_ids: list[int | str] = field(default_factory=list)


class MCPMode(StrEnum):
    READ_ONLY = "read-only"
    READ_WRITE = "read-write"


def serialize_dataclass(obj: object) -> object:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return obj


def extract_id_from_url(url: str) -> int:
    """Extract the integer resource ID from a Rossum API URL."""
    try:
        return int(url.rstrip("/").split("/")[-1])
    except (ValueError, IndexError) as e:
        raise ValueError(f"Cannot extract resource ID from URL: {url}") from e


def build_resource_url(base_url: str, resource_type: str, resource_id: int) -> str:
    """Build a full URL for a Rossum API resource."""
    return f"{base_url}/{resource_type}/{resource_id}"


def build_filters(**kwargs: Any) -> dict[str, Any]:
    """Build a filter dict from kwargs, excluding None values."""
    return {k: v for k, v in kwargs.items() if v is not None}


def filter_by_name_regex[T](items: list[T], name: str | None, use_regex: bool) -> list[T]:
    """Apply client-side regex name filtering when use_regex is True."""
    if not use_regex or name is None:
        return items
    return [
        item
        for item in items
        if (item_name := item.name) and re.search(name, item_name, re.IGNORECASE)  # ty:ignore[unresolved-attribute] - all callers pass items with .name
    ]


async def graceful_list(
    client: AsyncRossumAPIClient, resource: Resource, resource_label: str, max_items: int | None = None, **filters: Any
) -> GracefulListResult:
    """List resources gracefully, skipping items that fail deserialization.

    Uses _http_client.cursor_fetch_all directly so that a single broken item
    does not terminate the entire iteration (the high-level client generators
    die on the first deserialization error).
    """
    items: list[Any] = []
    skipped_ids: list[int | str] = []
    async for raw in client._http_client.cursor_fetch_all(resource, **filters):
        try:
            item = client._deserializer(resource, raw)
            items.append(item)
        except asyncio.CancelledError:
            raise
        except Exception:
            item_id = raw.get("id", "unknown")
            skipped_ids.append(item_id)
            logger.warning(f"Failed to deserialize {resource_label} (id={item_id}), skipping")
        if max_items is not None and len(items) >= max_items:
            break
    if skipped_ids:
        logger.warning(f"Skipped {len(skipped_ids)} {resource_label} item(s) that failed to deserialize")
    return GracefulListResult(items=items, skipped_ids=skipped_ids)


def get_queue_engine_url(queue: object) -> str | None:
    """Get the engine URL from a queue, checking dedicated, generic, then default engine."""
    for attr in ("dedicated_engine", "generic_engine", "engine"):
        value = getattr(queue, attr, None)
        if value and isinstance(value, str):
            return value
    return None


async def resolve_queue_workspaces(client: AsyncRossumAPIClient, queue_urls: set[str]) -> dict[str, str]:
    """Map queue URLs to their workspace URLs by fetching queue data."""
    if not queue_urls:
        return {}
    queue_result = await graceful_list(client, Resource.Queue, "queue")
    return {q.url: q.workspace for q in queue_result.items if q.workspace}


def resolve_workspaces_from_queues(queue_urls: list[str], queue_workspace_map: dict[str, str]) -> list[str]:
    return list({queue_workspace_map[q] for q in queue_urls if q in queue_workspace_map})


def resolve_workspace_from_queue(queue_url: str | None, queue_workspace_map: dict[str, str]) -> str | None:
    return queue_workspace_map[queue_url] if queue_url and queue_url in queue_workspace_map else None


def filter_by_workspace_id[T](items: list[T], workspace_id: int | None) -> list[T]:
    if workspace_id is None:
        return items
    workspace_url_suffix = f"/workspaces/{workspace_id}"
    return [
        item
        for item in items
        if (ws := getattr(item, "workspaces", None)) and any(w.endswith(workspace_url_suffix) for w in ws)
    ]


async def delete_resource(
    resource_type: str,
    resource_id: int,
    delete_fn: Callable[[int], Awaitable[None]],
    success_message: str | None = None,
) -> dict:
    """Generic delete operation.

    Write-access is enforced at the MCP layer via tags={"write"} + mcp.disable().
    """
    logger.debug(f"Deleting {resource_type}: {resource_type}_id={resource_id}")
    await delete_fn(resource_id)

    if success_message is None:
        success_message = f"{resource_type.title()} {resource_id} deleted successfully"
    return {"message": success_message}
