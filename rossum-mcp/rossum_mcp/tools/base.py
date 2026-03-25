from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generic, Literal, TypeVar

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


type McpMode = Literal["read-only", "read-write"]

VALID_MODES: tuple[McpMode, ...] = ("read-only", "read-write")


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
    client: AsyncRossumAPIClient,
    resource: Resource,
    resource_label: str,
    max_items: int | None = None,
    **filters: Any,
) -> GracefulListResult:
    """List resources gracefully, skipping items that fail deserialization.

    Uses _http_client.fetch_all directly so that a single broken item
    does not terminate the entire iteration (the high-level client generators
    die on the first deserialization error).
    """
    items: list[Any] = []
    skipped_ids: list[int | str] = []
    async for raw in client._http_client.fetch_all(resource, **filters):
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


async def delete_resource(
    resource_type: str,
    resource_id: int,
    delete_fn: Callable[[int], Awaitable[None]],
    success_message: str | None = None,
) -> dict:
    """Generic delete operation.

    Write-access is enforced at the MCP layer via tags={"write"} + mcp.disable().

    Args:
        resource_type: Name of the resource (e.g., "queue", "workspace")
        resource_id: ID of the resource to delete
        delete_fn: Async function that performs the deletion
        success_message: Custom success message. If None, uses default format.
    """
    logger.debug(f"Deleting {resource_type}: {resource_type}_id={resource_id}")
    await delete_fn(resource_id)

    if success_message is None:
        success_message = f"{resource_type.title()} {resource_id} deleted successfully"
    return {"message": success_message}
