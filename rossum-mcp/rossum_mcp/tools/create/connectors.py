from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.models.connector import Connector

from rossum_mcp.tools.base import build_resource_url

if TYPE_CHECKING:
    from typing import Any

    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _create_connector(
    client: AsyncRossumAPIClient,
    base_url: str,
    name: str,
    queue_id: int,
    service_url: str,
    authorization_token: str | None = None,
    params: str | None = None,
    asynchronous: bool = True,
    authorization_type: str = "secret_key",
    client_ssl_certificate: str | None = None,
    client_ssl_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Connector:
    queue_url = build_resource_url(base_url, "queues", queue_id)
    payload: dict[str, Any] = {
        "name": name,
        "queues": [queue_url],
        "service_url": service_url,
        "asynchronous": asynchronous,
        "authorization_type": authorization_type,
    }
    if authorization_token is not None:
        payload["authorization_token"] = authorization_token
    if params is not None:
        payload["params"] = params
    if client_ssl_certificate is not None:
        payload["client_ssl_certificate"] = client_ssl_certificate
    if client_ssl_key is not None:
        payload["client_ssl_key"] = client_ssl_key
    if metadata is not None:
        payload["metadata"] = metadata

    logger.debug(f"Creating connector: name={name}, service_url={service_url}")
    connector: Connector = await client.create_new_connector(payload)
    logger.info(f"Successfully created connector: id={connector.id}, name={connector.name}")
    return connector
