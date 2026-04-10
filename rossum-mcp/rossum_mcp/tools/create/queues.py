from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from fastmcp.exceptions import ToolError
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.queue import Queue

from rossum_mcp.models.queue import QUEUE_TEMPLATE_NAMES, QueueTemplateName
from rossum_mcp.tools.base import build_resource_url, extract_id_from_url, get_queue_engine_url
from rossum_mcp.tools.resource_tracking import embed_tracked_resources, track_resource

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient


logger = logging.getLogger(__name__)


async def _create_queue_from_template(
    client: AsyncRossumAPIClient,
    base_url: str,
    name: str,
    template_name: QueueTemplateName,
    workspace_id: int,
    include_documents: bool = False,
    engine_id: int | None = None,
) -> Queue:
    if template_name not in QUEUE_TEMPLATE_NAMES:
        raise ToolError(f"Invalid template_name: '{template_name}'. Available templates: {QUEUE_TEMPLATE_NAMES}")

    logger.debug(
        f"Creating queue from template: name={name}, template_name={template_name}, workspace_id={workspace_id}"
    )

    payload: dict = {
        "name": name,
        "template_name": template_name,
        "workspace": build_resource_url(base_url, "workspaces", workspace_id),
        "include_documents": include_documents,
    }

    if engine_id is not None:
        payload["engine"] = build_resource_url(base_url, "engines", engine_id)

    response = await client._http_client.request_json(
        method="POST",
        url="queues/from_template",
        json=payload,
    )
    queue = cast("Queue", client._deserializer(Resource.Queue, response))

    tracked: list[dict] = []

    # Track the schema created as a side effect
    try:
        schema_id = extract_id_from_url(queue.schema)
        schema = await client.retrieve_schema(schema_id)
        track_resource(tracked, "schema", schema_id, schema)
    except Exception:
        logger.warning(f"Failed to fetch schema for tracked resource (queue={queue.id})", exc_info=True)

    # Track the engine created as a side effect
    engine_url = get_queue_engine_url(queue)
    if engine_url:
        try:
            eid = extract_id_from_url(engine_url)
            engine = await client.retrieve_engine(eid)
            track_resource(tracked, "engine", eid, engine)
        except Exception:
            logger.warning(f"Failed to fetch engine for tracked resource (queue={queue.id})", exc_info=True)

    return embed_tracked_resources(queue, tracked)
