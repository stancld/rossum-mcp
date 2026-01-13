"""Engine tools for Rossum MCP Server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal, cast

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.engine import Engine, EngineField, EngineFieldType

from rossum_mcp.tools.base import build_resource_url, is_read_write_mode

type EngineType = Literal["extractor", "splitter"]

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_engine(client: AsyncRossumAPIClient, engine_id: int) -> Engine:
    logger.debug(f"Retrieving engine: engine_id={engine_id}")
    engine: Engine = await client.retrieve_engine(engine_id)
    return engine


async def _list_engines(
    client: AsyncRossumAPIClient,
    id: int | None = None,
    engine_type: EngineType | None = None,
    agenda_id: str | None = None,
) -> list[Engine]:
    logger.debug(f"Listing engines: id={id}, type={engine_type}, agenda_id={agenda_id}")
    filters: dict[str, int | str] = {}
    if id is not None:
        filters["id"] = id
    if engine_type is not None:
        filters["type"] = engine_type
    if agenda_id is not None:
        filters["agenda_id"] = agenda_id
    return [engine async for engine in client.list_engines(**filters)]  # type: ignore[arg-type]


async def _update_engine(client: AsyncRossumAPIClient, engine_id: int, engine_data: dict) -> Engine | dict:
    if not is_read_write_mode():
        return {"error": "update_engine is not available in read-only mode"}

    logger.debug(f"Updating engine: engine_id={engine_id}, data={engine_data}")
    updated_engine_data = await client._http_client.update(Resource.Engine, engine_id, engine_data)
    return cast("Engine", client._deserializer(Resource.Engine, updated_engine_data))


async def _create_engine(
    client: AsyncRossumAPIClient, name: str, organization_id: int, engine_type: EngineType
) -> Engine | dict:
    if not is_read_write_mode():
        return {"error": "create_engine is not available in read-only mode"}

    if engine_type not in ("extractor", "splitter"):
        raise ValueError(f"Invalid engine_type '{engine_type}'. Must be 'extractor' or 'splitter'")

    logger.debug(f"Creating engine: name={name}, organization_id={organization_id}, type={engine_type}")
    engine_data = {
        "name": name,
        "organization": build_resource_url("organizations", organization_id),
        "type": engine_type,
    }
    engine_response = await client._http_client.create(Resource.Engine, engine_data)
    return cast("Engine", client._deserializer(Resource.Engine, engine_response))


async def _create_engine_field(
    client: AsyncRossumAPIClient,
    engine_id: int,
    name: str,
    label: str,
    field_type: EngineFieldType,
    schema_ids: list[int],
    tabular: bool = False,
    multiline: str = "false",
    subtype: str | None = None,
    pre_trained_field_id: str | None = None,
) -> EngineField | dict:
    if not is_read_write_mode():
        return {"error": "create_engine_field is not available in read-only mode"}

    valid_types = ("string", "number", "date", "enum")
    if field_type not in valid_types:
        raise ValueError(f"Invalid field_type '{field_type}'. Must be one of: {', '.join(valid_types)}")
    if not schema_ids:
        raise ValueError("schema_ids cannot be empty - engine field must be linked to at least one schema")

    logger.debug(f"Creating engine field: engine_id={engine_id}, name={name}, type={field_type}, schemas={schema_ids}")
    engine_field_data = {
        "engine": build_resource_url("engines", engine_id),
        "name": name,
        "label": label,
        "type": field_type,
        "tabular": tabular,
        "multiline": multiline,
        "schemas": [build_resource_url("schemas", schema_id) for schema_id in schema_ids],
    }
    if subtype is not None:
        engine_field_data["subtype"] = subtype
    if pre_trained_field_id is not None:
        engine_field_data["pre_trained_field_id"] = pre_trained_field_id

    engine_field_response = await client._http_client.create(Resource.EngineField, engine_field_data)
    return cast("EngineField", client._deserializer(Resource.EngineField, engine_field_response))


async def _get_engine_fields(client: AsyncRossumAPIClient, engine_id: int | None = None) -> list[EngineField]:
    logger.debug(f"Retrieving engine fields: engine_id={engine_id}")
    return [engine_field async for engine_field in client.retrieve_engine_fields(engine_id=engine_id)]


def register_engine_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register engine-related tools with the FastMCP server."""

    @mcp.tool(description="Retrieve a single engine by ID.")
    async def get_engine(engine_id: int) -> Engine:
        return await _get_engine(client, engine_id)

    @mcp.tool(description="List all engines with optional filters.")
    async def list_engines(
        id: int | None = None, engine_type: EngineType | None = None, agenda_id: str | None = None
    ) -> list[Engine]:
        return await _list_engines(client, id, engine_type, agenda_id)

    @mcp.tool(description="Update engine settings.")
    async def update_engine(engine_id: int, engine_data: dict) -> Engine | dict:
        return await _update_engine(client, engine_id, engine_data)

    @mcp.tool(
        description="Create a new engine. IMPORTANT: When creating a new engine, check the schema to be used and create contained Engine fields immediately!"
    )
    async def create_engine(name: str, organization_id: int, engine_type: EngineType) -> Engine | dict:
        return await _create_engine(client, name, organization_id, engine_type)

    @mcp.tool(description="Create engine field for each schema field. Must be called when creating engine + schema.")
    async def create_engine_field(
        engine_id: int,
        name: str,
        label: str,
        field_type: EngineFieldType,
        schema_ids: list[int],
        tabular: bool = False,
        multiline: str = "false",
        subtype: str | None = None,
        pre_trained_field_id: str | None = None,
    ) -> EngineField | dict:
        return await _create_engine_field(
            client, engine_id, name, label, field_type, schema_ids, tabular, multiline, subtype, pre_trained_field_id
        )

    @mcp.tool(description="Retrieve engine fields for a specific engine or all engine fields.")
    async def get_engine_fields(engine_id: int | None = None) -> list[EngineField]:
        return await _get_engine_fields(client, engine_id)
