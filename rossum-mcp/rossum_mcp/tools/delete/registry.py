from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from rossum_mcp.tools.delete.annotations import _delete_annotation
from rossum_mcp.tools.delete.hooks import _delete_hook
from rossum_mcp.tools.delete.queues import _delete_queue
from rossum_mcp.tools.delete.rules import _delete_rule
from rossum_mcp.tools.delete.schemas import _delete_schema
from rossum_mcp.tools.delete.workspaces import _delete_workspace

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

DeleteRegistry = dict[str, Callable[[int], Awaitable[dict]]]


def build_delete_registry(client: AsyncRossumAPIClient) -> DeleteRegistry:
    return {
        "queue": lambda eid: _delete_queue(client, eid),
        "schema": lambda eid: _delete_schema(client, eid),
        "hook": lambda eid: _delete_hook(client, eid),
        "rule": lambda eid: _delete_rule(client, eid),
        "workspace": lambda eid: _delete_workspace(client, eid),
        "annotation": lambda eid: _delete_annotation(client, eid),
    }
