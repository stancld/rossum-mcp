"""Email template models and enums."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, TypedDict

from rossum_api.models.email_template import EmailTemplate as RossumEmailTemplate

from rossum_mcp.models.base import RossumResourceWithResolvedWorkspaces


class EmailRecipient(TypedDict):
    type: Literal["annotator", "constant", "datapoint"]
    value: str


class EmailTemplateType(StrEnum):
    REJECTION = "rejection"
    REJECTION_DEFAULT = "rejection_default"
    EMAIL_WITH_NO_PROCESSABLE_ATTACHMENTS = "email_with_no_processable_attachments"
    CUSTOM = "custom"


@dataclass
class EmailTemplate(RossumResourceWithResolvedWorkspaces[RossumEmailTemplate], RossumEmailTemplate):
    """Enriched EmailTemplate with resolved workspace URLs."""
