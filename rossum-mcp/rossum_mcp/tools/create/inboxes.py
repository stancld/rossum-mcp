from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from rossum_api.models.inbox import Inbox

from rossum_mcp.tools.base import build_resource_url

if TYPE_CHECKING:
    from typing import Any

    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _create_inbox(
    client: AsyncRossumAPIClient,
    base_url: str,
    name: str,
    queue_id: int,
    email_prefix: str | None = None,
    bounce_email_to: str | None = None,
    filters: dict[str, Any] | None = None,
    dmarc_check_action: Literal["accept", "drop"] = "accept",
    metadata: dict[str, Any] | None = None,
) -> Inbox:
    queue_url = build_resource_url(base_url, "queues", queue_id)
    payload: dict[str, Any] = {
        "name": name,
        "queues": [queue_url],
        "dmarc_check_action": dmarc_check_action,
    }
    if email_prefix is not None:
        payload["email_prefix"] = email_prefix
    if bounce_email_to is not None:
        payload["bounce_email_to"] = bounce_email_to
    if filters is not None:
        payload["filters"] = filters
    if metadata is not None:
        payload["metadata"] = metadata

    logger.debug(f"Creating inbox: name={name}, queue_id={queue_id}")
    inbox: Inbox = await client.create_new_inbox(payload)
    logger.info(f"Successfully created inbox: id={inbox.id}, email={inbox.email}")
    return inbox
