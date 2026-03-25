from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal, cast

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.inbox import Inbox

from rossum_mcp.tools.base import build_filters

if TYPE_CHECKING:
    from typing import Any

    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _update_inbox(
    client: AsyncRossumAPIClient,
    inbox_id: int,
    name: str | None = None,
    email_prefix: str | None = None,
    bounce_email_to: str | None = None,
    filters: dict[str, Any] | None = None,
    dmarc_check_action: Literal["accept", "drop"] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Inbox:
    logger.debug(f"Updating inbox: inbox_id={inbox_id}")

    patch_data = build_filters(
        name=name,
        email_prefix=email_prefix,
        bounce_email_to=bounce_email_to,
        filters=filters,
        dmarc_check_action=dmarc_check_action,
        metadata=metadata,
    )

    updated = await client._http_client.update(Resource.Inbox, inbox_id, patch_data)
    return cast("Inbox", client._deserializer(Resource.Inbox, updated))
