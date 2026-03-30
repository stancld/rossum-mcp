"""Auto-spillover for large tool results.

When a tool result exceeds SPILLOVER_THRESHOLD, the full content is saved
to a workspace file and a compact summary + file path is returned instead.
The agent can then use run_jq or run_grep to query the full content.

The search() summarizer extracts compact rows and aggregations. All other
tools use a generic summarizer that recurses one level into nested dicts.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# json.loads return narrowed to the container types we dispatch on
_JsonParsed = dict[str, object] | list[object] | str | int | float | bool | None

logger = logging.getLogger(__name__)

SPILLOVER_THRESHOLD = 30_000
_PREVIEW_ITEMS = 3
_PREVIEW_CHARS = 500
_TOOL_SUMMARY_MAX_ITEMS = 10
_MAX_SCALAR_FIELDS = 20
_MAX_VALUE_LEN = 120


def _sanitize_filename_part(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return sanitized or "output"


def _id_from_url(value: object) -> object:
    """Extract the trailing numeric ID from a Rossum API URL."""
    if not isinstance(value, str) or "://" not in value:
        return value
    last = value.rstrip("/").rsplit("/", 1)[-1]
    try:
        return int(last)
    except ValueError:
        return value


def _format_value(v: object) -> str:
    """Format a scalar value, extracting IDs from URLs and truncating long strings."""
    if isinstance(v, str):
        v = _id_from_url(v)
        if isinstance(v, str) and len(v) > _MAX_VALUE_LEN:
            return v[:_MAX_VALUE_LEN] + "..."
    return str(v)


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

    return _summarize(content, str(file_path), tool_name)


def _summarize(content: str, file_path: str, tool_name: str = "") -> str:
    """Generate a compact summary of spilled content."""
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return _summarize_text(content, file_path)

    # Tool-specific summary when available
    if tool_name:
        tool_result = _try_tool_summary(parsed, file_path, tool_name)
        if tool_result is not None:
            return tool_result

    # Generic fallback
    if isinstance(parsed, list):
        return _summarize_array(parsed, file_path)
    if isinstance(parsed, dict):
        return _summarize_object(parsed, file_path)
    return _summarize_text(content, file_path)


# ---------------------------------------------------------------------------
# Tool-specific summarizers
# ---------------------------------------------------------------------------


def _try_tool_summary(parsed: _JsonParsed, file_path: str, tool_name: str) -> str | None:
    """Dispatch to a tool-aware summarizer. Returns None to fall back to generic."""
    if tool_name == "search" and isinstance(parsed, list):
        return _summarize_search_result(parsed, file_path)
    return None


# -- search() ---------------------------------------------------------------

_SEARCH_DISPLAY_FIELDS: dict[str, tuple[str, ...]] = {
    "queue": ("id", "name", "status"),
    "hook": ("id", "name", "active"),
    "hook_log": ("timestamp", "level", "hook_id", "status_code", "message"),
    "annotation": ("id", "status", "queue"),
    "user": ("id", "username", "email"),
    "rule": ("id", "name", "enabled"),
}


def _summarize_search_result(parsed: list[object], file_path: str) -> str | None:
    """Summarize search() results with count, compact rows, and aggregations."""
    count = len(parsed)
    if count == 0:
        return f"Result saved to {file_path}\n\nSearch returned 0 results."

    entity_type = _detect_search_entity(parsed[0])
    lines = [f"Result saved to {file_path}\n"]
    lines.append(f"Search results: {count} {entity_type}{'s' if count != 1 else ''}")

    preview_n = min(count, _TOOL_SUMMARY_MAX_ITEMS)
    lines.append("")
    for item in parsed[:preview_n]:
        if isinstance(item, dict):
            lines.append(f"- {_compact_item(item, entity_type)}")
    if count > preview_n:
        lines.append(f"... ({count - preview_n} more)")

    aggs = _search_aggregations(parsed, entity_type)
    if aggs:
        lines.append("\nAggregations:")
        for a in aggs:
            lines.append(f"- {a}")

    lines.append("\nUse run_jq only if you need filtering or full raw content.")
    return "\n".join(lines)


def _detect_search_entity(first_item: object) -> str:
    if not isinstance(first_item, dict):
        return "item"
    keys = set(first_item.keys())
    if "automation_enabled" in keys or "automation_level" in keys:
        return "queue"
    if "hook" in keys and "status_code" in keys:
        return "hook_log"
    if "trigger_condition" in keys or "actions" in keys:
        return "rule"
    if "events" in keys or "hook_type" in keys:
        return "hook"
    if "status" in keys and "queue" in keys and "document" in keys:
        return "annotation"
    if "username" in keys:
        return "user"
    return "item"


def _compact_item(item: dict, entity_type: str) -> str:
    display_fields = _SEARCH_DISPLAY_FIELDS.get(entity_type)
    parts: list[str] = []

    if display_fields:
        for k in display_fields:
            if k not in item:
                continue
            v = item[k]
            if isinstance(v, str) and "://" in v:
                v = _id_from_url(v)
            if isinstance(v, str) and len(v) > 60:
                v = v[:57] + "..."
            parts.append(f"{k}={v}")
    else:
        for k, v in item.items():
            if not (isinstance(v, (str, int, float, bool)) or v is None):
                continue
            if isinstance(v, str) and "://" in v:
                v = _id_from_url(v)
            if isinstance(v, str) and len(v) > 60:
                v = v[:57] + "..."
            parts.append(f"{k}={v}")
            if len(parts) >= 5:
                break

    return ", ".join(parts)


def _search_aggregations(items: list[object], entity_type: str) -> list[str]:
    aggs: list[str] = []
    dicts: list[dict] = [i for i in items if isinstance(i, dict)]

    if entity_type == "hook_log":
        levels: Counter[str] = Counter()
        status_codes: Counter[object] = Counter()
        hook_ids: set[object] = set()
        for d in dicts:
            levels[str(d.get("level", "?"))] += 1
            sc = d.get("status_code")
            if sc is not None:
                status_codes[sc] += 1
            hid = d.get("hook_id")
            if hid is not None:
                hook_ids.add(hid)
        error_count = levels.get("ERROR", 0) + levels.get("error", 0)
        if error_count:
            aggs.append(f"errors: {error_count}")
        aggs.append(f"unique hook IDs: {len(hook_ids)}")
        if status_codes:
            top = status_codes.most_common(5)
            aggs.append(f"status codes: {', '.join(f'{code} ({n}x)' for code, n in top)}")

    elif entity_type in ("annotation", "queue"):
        statuses: Counter[str] = Counter()
        for d in dicts:
            statuses[str(d.get("status", "?"))] += 1
        if len(statuses) > 1:
            aggs.append(f"by status: {', '.join(f'{s} ({n})' for s, n in statuses.items())}")

    return aggs


# ---------------------------------------------------------------------------
# Generic fallback summarizers
# ---------------------------------------------------------------------------


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


def _extract_dict_fields(d: dict, prefix: str, scalar_lines: list[str], nested_lines: list[str]) -> None:
    """Extract scalars and nested keys from a dict, appending to the output lists."""
    sub_nested: list[str] = []
    for k, v in d.items():
        qualified = f"{prefix}.{k}" if prefix else k
        if isinstance(v, (str, int, float, bool)) or v is None:
            scalar_lines.append(f"  {qualified}: {_format_value(v)}")
        elif isinstance(v, list):
            sub_nested.append(f"{k} ({len(v)} items)")
        elif isinstance(v, dict):
            sub_nested.append(k)
    if prefix and sub_nested:
        nested_lines.append(f"  {prefix}: {', '.join(sub_nested)}")
    elif not prefix:
        for item in sub_nested:
            nested_lines.append(f"  {item}")


def _summarize_object(obj: dict, file_path: str) -> str:
    """Summarize a JSON object, extracting scalars one level deep and listing nested areas."""
    keys = list(obj.keys())
    scalar_lines: list[str] = []
    nested_lines: list[str] = []

    for k, v in obj.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            scalar_lines.append(f"  {k}: {_format_value(v)}")
        elif isinstance(v, dict):
            _extract_dict_fields(v, k, scalar_lines, nested_lines)
        elif isinstance(v, list):
            nested_lines.append(f"  {k} ({len(v)} items)")

    parts = [f"Result saved to {file_path} (object with {len(keys)} keys: {', '.join(keys[:10])})"]

    if scalar_lines:
        if len(scalar_lines) > _MAX_SCALAR_FIELDS:
            overflow = len(scalar_lines) - _MAX_SCALAR_FIELDS
            scalar_lines = scalar_lines[:_MAX_SCALAR_FIELDS]
            scalar_lines.append(f"  ... ({overflow} more)")
        parts.append("\nKey fields:\n" + "\n".join(scalar_lines))

    if nested_lines:
        parts.append("\nNested (use run_jq to query):\n" + "\n".join(nested_lines))

    if not scalar_lines and not nested_lines:
        preview = json.dumps(obj, indent=2, default=str)[:_PREVIEW_CHARS]
        parts.append(f"\nPreview:\n{preview}\n...")

    parts.append("\nUse run_jq or run_grep on the file path to query full content.")
    return "\n".join(parts)


def _summarize_text(content: str, file_path: str) -> str:
    line_count = content.count("\n") + 1
    preview = content[:_PREVIEW_CHARS]

    return (
        f"Result saved to {file_path} ({line_count} lines, {len(content)} chars)\n\n"
        f"Preview:\n{preview}\n...\n\n"
        f"Use run_jq or run_grep on the file path to query full content."
    )
