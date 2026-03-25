from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource

from rossum_mcp.tools.base import delete_resource

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)
DeleteRegistry = dict[str, Callable[[int], Awaitable[dict]]]


async def _delete_queue(client: AsyncRossumAPIClient, queue_id: int) -> dict:
    return await delete_resource(
        "queue", queue_id, client.delete_queue, f"Queue {queue_id} scheduled for deletion (starts after 24 hours)"
    )


async def _delete_schema(client: AsyncRossumAPIClient, schema_id: int) -> dict:
    return await delete_resource("schema", schema_id, client.delete_schema)


async def _delete_hook(client: AsyncRossumAPIClient, hook_id: int) -> dict:
    return await delete_resource("hook", hook_id, client.delete_hook)


async def _delete_rule(client: AsyncRossumAPIClient, rule_id: int) -> dict:
    return await delete_resource("rule", rule_id, client.delete_rule)


async def _delete_workspace(client: AsyncRossumAPIClient, workspace_id: int) -> dict:
    return await delete_resource("workspace", workspace_id, client.delete_workspace)


async def _delete_annotation(client: AsyncRossumAPIClient, annotation_id: int) -> dict:
    return await delete_resource(
        "annotation", annotation_id, client.delete_annotation, f"Annotation {annotation_id} moved to 'deleted' status"
    )


async def _delete_inbox(client: AsyncRossumAPIClient, inbox_id: int) -> dict:
    logger.debug(f"Deleting inbox: inbox_id={inbox_id}")
    await client._http_client.delete(Resource.Inbox, inbox_id)
    return {"message": f"Inbox {inbox_id} deleted successfully"}


async def _delete_connector(client: AsyncRossumAPIClient, connector_id: int) -> dict:
    logger.debug(f"Deleting connector: connector_id={connector_id}")
    await client._http_client.delete(Resource.Connector, connector_id)
    return {"message": f"Connector {connector_id} deleted successfully"}


def build_delete_registry(client: AsyncRossumAPIClient) -> DeleteRegistry:
    return {
        "queue": lambda eid: _delete_queue(client, eid),
        "schema": lambda eid: _delete_schema(client, eid),
        "hook": lambda eid: _delete_hook(client, eid),
        "rule": lambda eid: _delete_rule(client, eid),
        "workspace": lambda eid: _delete_workspace(client, eid),
        "annotation": lambda eid: _delete_annotation(client, eid),
        "inbox": lambda eid: _delete_inbox(client, eid),
        "connector": lambda eid: _delete_connector(client, eid),
    }
