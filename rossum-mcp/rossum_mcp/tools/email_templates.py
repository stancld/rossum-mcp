"""Email template tools for Rossum MCP Server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from rossum_api.models.email_template import EmailTemplate

from rossum_mcp.tools.base import is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)

EmailTemplateType = Literal["rejection", "rejection_default", "email_with_no_processable_attachments", "custom"]


async def _get_email_template(client: AsyncRossumAPIClient, email_template_id: int) -> EmailTemplate:
    email_template: EmailTemplate = await client.retrieve_email_template(email_template_id)
    return email_template


async def _list_email_templates(
    client: AsyncRossumAPIClient,
    queue_id: int | None = None,
    type: EmailTemplateType | None = None,
    name: str | None = None,
    first_n: int | None = None,
) -> list[EmailTemplate]:
    filters: dict = {}
    if queue_id is not None:
        filters["queue"] = queue_id
    if type is not None:
        filters["type"] = type
    if name is not None:
        filters["name"] = name

    templates_list: list[EmailTemplate] = []
    async for template in client.list_email_templates(**filters):
        templates_list.append(template)
        if first_n is not None and len(templates_list) >= first_n:
            break

    return templates_list


async def _create_email_template(
    client: AsyncRossumAPIClient,
    name: str,
    queue: str,
    subject: str,
    message: str,
    type: EmailTemplateType = "custom",
    automate: bool = False,
    to: list[dict[str, Any]] | None = None,
    cc: list[dict[str, Any]] | None = None,
    bcc: list[dict[str, Any]] | None = None,
    triggers: list[str] | None = None,
) -> EmailTemplate | dict:
    if not is_read_write_mode():
        return {"error": "create_email_template is not available in read-only mode"}

    logger.debug(f"Creating email template: name={name}, queue={queue}, type={type}")

    template_data: dict[str, Any] = {
        "name": name,
        "queue": queue,
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


def register_email_template_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register email template-related tools with the FastMCP server."""

    @mcp.tool(
        description="Retrieve a single email template by ID. Use list_email_templates first to find templates for a queue."
    )
    async def get_email_template(email_template_id: int) -> EmailTemplate:
        return await _get_email_template(client, email_template_id)

    @mcp.tool(
        description="List all email templates with optional filtering. Email templates define automated or manual email responses sent from Rossum queues. Types: 'rejection' (for rejecting documents), 'rejection_default' (default rejection template), 'email_with_no_processable_attachments' (when email has no valid attachments), 'custom' (user-defined templates)."
    )
    async def list_email_templates(
        queue_id: int | None = None,
        type: EmailTemplateType | None = None,
        name: str | None = None,
        first_n: int | None = None,
    ) -> list[EmailTemplate]:
        return await _list_email_templates(client, queue_id, type, name, first_n)

    @mcp.tool(
        description="Create a new email template. Email templates can be automated (automate=True) to send emails automatically on specific triggers, or manual for user-initiated sending. The 'to', 'cc', and 'bcc' fields accept lists of recipient objects with 'type' ('annotator', 'constant', 'datapoint') and 'value' keys."
    )
    async def create_email_template(
        name: str,
        queue: str,
        subject: str,
        message: str,
        type: EmailTemplateType = "custom",
        automate: bool = False,
        to: list[dict[str, Any]] | None = None,
        cc: list[dict[str, Any]] | None = None,
        bcc: list[dict[str, Any]] | None = None,
        triggers: list[str] | None = None,
    ) -> EmailTemplate | dict:
        return await _create_email_template(
            client, name, queue, subject, message, type, automate, to, cc, bcc, triggers
        )
