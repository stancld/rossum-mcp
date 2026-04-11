from __future__ import annotations

from rossum_mcp.models.queue import QUEUE_TEMPLATE_NAMES


async def _list_queue_template_names(max_items: int | None = None) -> list[str]:
    items: list[str] = list(QUEUE_TEMPLATE_NAMES)
    return items[:max_items] if max_items is not None else items
