"""URL context extraction for Rossum application URLs.

This module provides utilities to extract context (queue_id, document_id, hook_id, engine_id)
from Rossum application URLs, enabling the agent to understand the user's current
context when they paste a URL.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse


@dataclass
class RossumUrlContext:
    """Extracted context from a Rossum application URL."""

    queue_id: int | None = None
    document_id: int | None = None
    hook_id: int | None = None
    engine_id: int | None = None
    raw_url: str | None = None
    page_type: str | None = None
    additional_context: dict[str, str] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Check if no context was extracted."""
        return all(getattr(self, f) is None for f in ["queue_id", "document_id", "hook_id", "engine_id"])

    def to_context_string(self) -> str:
        """Convert the context to a human-readable string for the agent."""
        parts = []
        if self.queue_id:
            parts.append(f"Queue ID: {self.queue_id}")
        if self.document_id:
            parts.append(f"Document ID: {self.document_id}")
        if self.hook_id:
            parts.append(f"Hook ID: {self.hook_id}")
        if self.engine_id:
            parts.append(f"Engine ID: {self.engine_id}")
        if self.page_type:
            parts.append(f"Page type: {self.page_type}")
        for key, value in self.additional_context.items():
            parts.append(f"{key}: {value}")
        return ", ".join(parts) if parts else ""


# URL patterns for different Rossum pages
# Format: /queues/{queue_id}/...
QUEUE_PATTERN = re.compile(r"/queues/(\d+)")
# Format: /document/{document_id}
DOCUMENT_PATTERN = re.compile(r"/document/(\d+)")
# Format: /hooks/{hook_id} or /extensions/{hook_id} or /extensions/my-extensions/{hook_id}
HOOK_PATTERN = re.compile(r"/(hooks|extensions|extensions/my-extensions)/(\d+)")
# Format: /engines/{engine_id} or /automation/engines/{engine_id}
ENGINE_PATTERN = re.compile(r"/(automation/)?engines/(\d+)")

# Documents list view pattern
DOCUMENTS_VIEW_PATTERN = re.compile(r"/documents(\?|$)")

# Page type patterns (order matters - more specific patterns first)
PAGE_TYPE_PATTERNS = [
    (re.compile(r"/automation/engines/\d+/settings/basic"), "engine_settings"),
    (re.compile(r"/automation/engines/\d+/settings"), "engine_settings"),
    (re.compile(r"/settings/basic"), "queue_settings"),
    (re.compile(r"/settings/schema"), "schema_settings"),
    (re.compile(r"/settings/hooks"), "hooks_settings"),
    (re.compile(r"/settings/automation"), "automation_settings"),
    (re.compile(r"/settings/emails"), "email_settings"),
    (re.compile(r"/settings"), "settings"),
    (re.compile(r"/documents(\?|$)"), "documents_list"),
    (re.compile(r"/all$"), "all_documents"),
    (re.compile(r"/queues/\d+/review"), "review"),
    (re.compile(r"/upload"), "upload"),
]


def _extract_documents_view_context(url: str, context: RossumUrlContext) -> None:
    """Extract context from the documents list view URL.

    Parses the filtering query parameter to extract queue_id and other context.
    Example URL: /documents?filtering={"items":[{"field":"queue","value":["3866808"],...}]}
    """
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        if "filtering" in query_params:
            filtering_json = query_params["filtering"][0]
            filtering = json.loads(filtering_json)

            for item in filtering.get("items", []):
                if item.get("field") == "queue" and item.get("value"):
                    queue_values = item["value"]
                    if queue_values and len(queue_values) == 1:
                        context.queue_id = int(queue_values[0])
                    elif queue_values:
                        context.additional_context["queue_ids"] = ",".join(queue_values)

        if "level" in query_params:
            context.additional_context["view_level"] = query_params["level"][0]

    except (json.JSONDecodeError, KeyError, ValueError, IndexError):
        pass


def extract_url_context(url: str | None) -> RossumUrlContext:
    """Extract context from a Rossum application URL.

    Args:
        url: The Rossum application URL (e.g.,
             "https://elis.rossum.ai/queues/3866808/settings/basic")

    Returns:
        RossumUrlContext with extracted IDs and page type.
    """
    if not url:
        return RossumUrlContext()

    context = RossumUrlContext(raw_url=url)

    if match := QUEUE_PATTERN.search(url):
        context.queue_id = int(match.group(1))

    if match := DOCUMENT_PATTERN.search(url):
        context.document_id = int(match.group(1))

    if match := HOOK_PATTERN.search(url):
        context.hook_id = int(match.group(2))

    if match := ENGINE_PATTERN.search(url):
        context.engine_id = int(match.group(2))

    if DOCUMENTS_VIEW_PATTERN.search(url):
        _extract_documents_view_context(url, context)

    for pattern, page_type in PAGE_TYPE_PATTERNS:
        if pattern.search(url):
            context.page_type = page_type
            break

    return context


def format_context_for_prompt(context: RossumUrlContext) -> str:
    """Format the URL context for inclusion in the agent prompt.

    Args:
        context: The extracted URL context.

    Returns:
        A formatted string to prepend to user messages.
    """
    if context.is_empty():
        return ""

    context_str = context.to_context_string()
    return f"""
**Current Context from URL:**
{context_str}

When the user refers to "this queue", "this schema", "this annotation", etc., use the IDs from the context above.
---

"""
