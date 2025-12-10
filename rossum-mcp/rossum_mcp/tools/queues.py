"""Queue tools for Rossum MCP Server."""

from __future__ import annotations

import dataclasses
import logging
import os
from typing import TYPE_CHECKING

from rossum_api import APIClientError
from rossum_api.domain_logic.resources import Resource
from rossum_api.models import deserialize_default

from rossum_mcp.tools.base import build_resource_url, is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient
    from rossum_api.models.engine import Engine
    from rossum_api.models.queue import Queue
    from rossum_api.models.schema import Schema

logger = logging.getLogger(__name__)


def register_queue_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:  # noqa: C901
    """Register queue-related tools with the FastMCP server."""

    @mcp.tool(description="Retrieve queue details. Returns: id, name, url, schema, workspace, inbox, engine.")
    async def get_queue(queue_id: int) -> dict:
        """Retrieve queue details."""
        logger.debug(f"Retrieving queue: queue_id={queue_id}")
        queue: Queue = await client.retrieve_queue(queue_id)
        return {
            "id": queue.id,
            "name": queue.name,
            "url": queue.url,
            "schema": queue.schema,
            "workspace": queue.workspace,
            "inbox": queue.inbox,
            "engine": queue.engine,
        }

    @mcp.tool(
        description="Retrieve queue schema. Returns Schema model fields: id, name, queues, url, content, metadata, modified_by, modified_at."
    )
    async def get_queue_schema(queue_id: int) -> dict:
        """Retrieve complete schema for a queue."""
        logger.debug(f"Retrieving queue schema: queue_id={queue_id}")
        queue: Queue = await client.retrieve_queue(queue_id)
        schema_url = queue.schema
        schema_id = int(schema_url.rstrip("/").split("/")[-1])
        schema: Schema = await client.retrieve_schema(schema_id)
        return dataclasses.asdict(schema)

    @mcp.tool(
        description="Retrieve queue engine. Returns Engine model fields: id, url, name, type, learning_enabled, training_queues, description, agenda_id. None if no engine assigned."
    )
    async def get_queue_engine(queue_id: int) -> dict:
        """Retrieve complete engine information for a queue."""
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
                engine_id = int(engine_url.rstrip("/").split("/")[-1])
                engine: Engine = await client.retrieve_engine(engine_id)
            else:
                engine = deserialize_default(Resource.Engine, engine_url)
        except APIClientError as e:
            if e.status_code == 404:
                return {"message": f"Engine not found (engine URL: {engine_url})"}
            raise

        return dataclasses.asdict(engine)

    @mcp.tool(
        description="Create a queue. Returns: id, name, url, workspace, schema, engine, inbox, connector, locale, automation settings, message."
    )
    async def create_queue(
        name: str,
        workspace_id: int,
        schema_id: int,
        engine_id: int | None = None,
        inbox_id: int | None = None,
        connector_id: int | None = None,
        locale: str = "en_GB",
        automation_enabled: bool = False,
        automation_level: str = "never",
        training_enabled: bool = True,
        splitting_screen_feature_flag: bool = False,
    ) -> dict:
        """Create a new queue with schema and optional engine assignment."""
        if not is_read_write_mode():
            return {"error": "create_queue is not available in read-only mode"}

        logger.debug(
            f"Creating queue: name={name}, workspace_id={workspace_id}, schema_id={schema_id}, engine_id={engine_id}"
        )

        queue_data: dict = {
            "name": name,
            "workspace": build_resource_url("workspaces", workspace_id),
            "schema": build_resource_url("schemas", schema_id),
            "locale": locale,
            "automation_enabled": automation_enabled,
            "automation_level": automation_level,
            "training_enabled": training_enabled,
        }

        if engine_id is not None:
            queue_data["engine"] = build_resource_url("engines", engine_id)
        if inbox_id is not None:
            queue_data["inbox"] = build_resource_url("inboxes", inbox_id)
        if connector_id is not None:
            queue_data["connector"] = build_resource_url("connectors", connector_id)
        if splitting_screen_feature_flag:
            if os.environ.get("SPLITTING_SCREEN_FLAG_NAME") and os.environ.get("SPLITTING_SCREEN_FLAG_VALUE"):
                queue_data["settings"] = {
                    os.environ["SPLITTING_SCREEN_FLAG_NAME"]: os.environ["SPLITTING_SCREEN_FLAG_VALUE"]
                }
            else:
                logger.error("Splitting screen failed to update")

        queue: Queue = await client.create_new_queue(queue_data)
        return {
            "id": queue.id,
            "name": queue.name,
            "url": queue.url,
            "workspace": queue.workspace,
            "schema": queue.schema,
            "engine": queue.engine,
            "inbox": queue.inbox,
            "connector": queue.connector,
            "locale": queue.locale,
            "automation_enabled": queue.automation_enabled,
            "automation_level": queue.automation_level,
            "training_enabled": queue.training_enabled,
            "message": f"Queue '{queue.name}' created successfully with ID {queue.id}",
        }

    @mcp.tool(description="Update queue settings. Returns: updated queue details, message.")
    async def update_queue(queue_id: int, queue_data: dict) -> dict:
        """Update an existing queue with new settings."""
        if not is_read_write_mode():
            return {"error": "update_queue is not available in read-only mode"}

        logger.debug(f"Updating queue: queue_id={queue_id}, data={queue_data}")
        updated_queue_data = await client._http_client.update(Resource.Queue, queue_id, queue_data)
        updated_queue: Queue = client._deserializer(Resource.Queue, updated_queue_data)
        result = dataclasses.asdict(updated_queue)
        result["message"] = f"Queue '{updated_queue.name}' (ID {updated_queue.id}) updated successfully"
        return result
