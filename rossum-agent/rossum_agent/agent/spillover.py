"""Auto-spillover for large tool results.

When a tool result exceeds SPILLOVER_THRESHOLD, the full content is saved
to a workspace file and a compact summary + file path is returned instead.
The agent can then use run_jq or run_grep to query the full content.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from pathlib import Path

logger = structlog.get_logger(__name__)

SPILLOVER_THRESHOLD = 30_000
_PREVIEW_ITEMS = 3
_PREVIEW_CHARS = 500


def _sanitize_filename_part(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return sanitized or "output"


def maybe_spill(
    content: str,
    tool_name: str,
    step_number: int,
    output_dir: Path,
    tool_call_id: str | None = None,
) -> str:
    """Save large content to a workspace file and return a summary with the file path.

    Returns the original content unchanged if it's below the threshold.
    """
    if len(content) <= SPILLOVER_THRESHOLD:
        return content

    workspace_dir = output_dir / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    filename_parts = [f"step{step_number}", _sanitize_filename_part(tool_name)]
    if tool_call_id:
        filename_parts.append(_sanitize_filename_part(tool_call_id))
    filename = "_".join(filename_parts) + ".json"
    file_path = workspace_dir / filename
    file_path.write_text(content, encoding="utf-8")

    logger.info(f"Spilled {len(content)} chars from {tool_name} to {file_path}")

    return _summarize(content, str(file_path))


def _summarize(content: str, file_path: str) -> str:
    """Generate a compact summary of spilled content."""
    # Try JSON array
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return _summarize_array(parsed, file_path)
        if isinstance(parsed, dict):
            return _summarize_object(parsed, file_path)
    except (json.JSONDecodeError, ValueError):
        pass

    # Plain text fallback
    return _summarize_text(content, file_path)


def _summarize_array(items: list, file_path: str) -> str:
    preview_items = items[:_PREVIEW_ITEMS]
    preview_json = json.dumps(preview_items, indent=2, default=str)

    remaining = len(items) - _PREVIEW_ITEMS
    remaining_note = f"\n... ({remaining} more items)" if remaining > 0 else ""

    return (
        f"Result saved to {file_path} ({len(items)} items)\n\n"
        f"Preview:\n{preview_json}{remaining_note}\n\n"
        f"Use run_jq or run_grep on the file path to query full content."
    )


def _summarize_object(obj: dict, file_path: str) -> str:
    keys = list(obj.keys())

    # Extract all scalar values (strings, numbers, bools, None) so the agent
    # keeps critical identifiers (IDs, names, URLs) without reading the file.
    scalars: dict = {}
    for k, v in obj.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            scalars[k] = v

    if scalars:
        scalar_json = json.dumps(scalars, indent=2, default=str)
        preview = f"Key fields:\n{scalar_json}"
    else:
        preview = f"Preview:\n{json.dumps(obj, indent=2, default=str)[:_PREVIEW_CHARS]}\n..."

    non_scalar_keys = [k for k in keys if k not in scalars]
    nested_note = f"\nNested/large keys (use run_jq to query): {', '.join(non_scalar_keys)}" if non_scalar_keys else ""

    return (
        f"Result saved to {file_path} (object with {len(keys)} keys: {', '.join(keys[:10])})\n\n"
        f"{preview}{nested_note}\n\n"
        f"Use run_jq or run_grep on the file path to query full content."
    )


def _summarize_text(content: str, file_path: str) -> str:
    line_count = content.count("\n") + 1
    preview = content[:_PREVIEW_CHARS]

    return (
        f"Result saved to {file_path} ({line_count} lines, {len(content)} chars)\n\n"
        f"Preview:\n{preview}\n...\n\n"
        f"Use run_jq or run_grep on the file path to query full content."
    )
