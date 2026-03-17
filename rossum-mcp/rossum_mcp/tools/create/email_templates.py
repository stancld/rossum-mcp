from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from rossum_api.models.email_template import EmailTemplate

from rossum_mcp.tools.base import build_resource_url
from rossum_mcp.tools.models import EmailTemplateType

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

    from rossum_mcp.tools.models import EmailRecipient

logger = logging.getLogger(__name__)


async def _create_email_template(
    client: AsyncRossumAPIClient,
    base_url: str,
    name: str,
    queue: int,
    subject: str,
    message: str,
    type: EmailTemplateType = EmailTemplateType.CUSTOM,
    automate: bool = False,
    to: list[EmailRecipient] | None = None,
    cc: list[EmailRecipient] | None = None,
    bcc: list[EmailRecipient] | None = None,
    triggers: list[str] | None = None,
) -> EmailTemplate | dict:
    logger.debug(f"Creating email template: name={name}, queue={queue}, type={type}")

    template_data: dict[str, Any] = {
        "name": name,
        "queue": build_resource_url(base_url, "queues", queue),
        "subject": subject,
        "message": message,
        "type": type,
        "automate": automate,
    }

    if to is not None:
        template_data["to"] = to
    if cc is not None:
        template_data["cc"] = cc
    if bcc is not None:
        template_data["bcc"] = bcc
    if triggers is not None:
        template_data["triggers"] = triggers

    email_template: EmailTemplate = await client.create_new_email_template(template_data)
    return email_template
