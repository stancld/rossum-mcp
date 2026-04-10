"""Hook models and enums."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rossum_api.models.hook import Hook as RossumHook

from rossum_mcp.models.base import RossumResourceWithResolvedWorkspaces


class HookSideload(StrEnum):
    QUEUES = "queues"
    MODIFIERS = "modifiers"
    SCHEMAS = "schemas"
    EMAILS = "emails"
    RELATED_EMAILS = "related_emails"
    RELATIONS = "relations"
    CHILD_RELATION = "child_relation"
    NOTES = "notes"
    SUGGESTED_EDITS = "suggested_edits"
    ASSIGNEES = "assignees"
    PAGES = "pages"
    LABELS = "labels"
    AUTOMATION_BLOCKERS = "automation_blockers"


@dataclass
class Hook(RossumResourceWithResolvedWorkspaces[RossumHook], RossumHook):
    """Enriched Hook with resolved workspace URLs."""
