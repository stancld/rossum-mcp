from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast, get_args

from fastmcp.exceptions import ToolError
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.engine import Engine, EngineField, EngineFieldType

from rossum_mcp.models.engine import EngineType
from rossum_mcp.tools.base import build_resource_url

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _create_engine(
    client: AsyncRossumAPIClient, base_url: str, name: str, organization_id: int, engine_type: EngineType
) -> Engine:
    if engine_type not in tuple(EngineType):
        raise ToolError(f"Invalid engine_type '{engine_type}'. Must be one of: {', '.join(EngineType)}")

    logger.debug(f"Creating engine: name={name}, organization_id={organization_id}, type={engine_type}")
    engine_data = {
        "name": name,
        "organization": build_resource_url(base_url, "organizations", organization_id),
        "type": engine_type,
    }
    engine_response = await client._http_client.create(Resource.Engine, engine_data)
    return cast("Engine", client._deserializer(Resource.Engine, engine_response))


async def _create_engine_field(
    client: AsyncRossumAPIClient,
    base_url: str,
    engine_id: int,
    name: str,
    label: str,
    field_type: EngineFieldType,
    schema_ids: list[int],
    tabular: bool = False,
    multiline: bool = False,
    subtype: str | None = None,
    pre_trained_field_id: str | None = None,
) -> EngineField:
    valid_types = get_args(EngineFieldType)
    if field_type not in valid_types:
        raise ToolError(f"Invalid field_type '{field_type}'. Must be one of: {', '.join(valid_types)}")
    if not schema_ids:
        raise ToolError("schema_ids cannot be empty - engine field must be linked to at least one schema")

    logger.debug(f"Creating engine field: engine_id={engine_id}, name={name}, type={field_type}, schemas={schema_ids}")
    engine_field_data = {
        "engine": build_resource_url(base_url, "engines", engine_id),
        "name": name,
        "label": label,
        "type": field_type,
        "tabular": tabular,
        "multiline": str(multiline).lower(),
        "schemas": [build_resource_url(base_url, "schemas", schema_id) for schema_id in schema_ids],
    }
    if subtype is not None:
        engine_field_data["subtype"] = subtype
    if pre_trained_field_id is not None:
        engine_field_data["pre_trained_field_id"] = pre_trained_field_id

    engine_field_response = await client._http_client.create(Resource.EngineField, engine_field_data)
    return cast("EngineField", client._deserializer(Resource.EngineField, engine_field_response))
