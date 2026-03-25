from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.connector import Connector

from rossum_mcp.tools.base import build_filters

if TYPE_CHECKING:
    from typing import Any

    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _update_connector(
    client: AsyncRossumAPIClient,
    connector_id: int,
    name: str | None = None,
    service_url: str | None = None,
    authorization_token: str | None = None,
    params: str | None = None,
    asynchronous: bool | None = None,
    authorization_type: str | None = None,
    client_ssl_certificate: str | None = None,
    client_ssl_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Connector:
    logger.debug(f"Updating connector: connector_id={connector_id}")

    patch_data = build_filters(
        name=name,
        service_url=service_url,
        authorization_token=authorization_token,
        params=params,
        asynchronous=asynchronous,
        authorization_type=authorization_type,
        client_ssl_certificate=client_ssl_certificate,
        client_ssl_key=client_ssl_key,
        metadata=metadata,
    )

    updated = await client._http_client.update(Resource.Connector, connector_id, patch_data)
    return cast("Connector", client._deserializer(Resource.Connector, updated))
