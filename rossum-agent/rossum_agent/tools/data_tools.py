"""General-purpose jq and grep tools for arbitrary JSON/text content."""

from __future__ import annotations

import json
import re
from pathlib import Path

import jq  # ty: ignore[unresolved-import] - no type stubs for jq
from anthropic import beta_tool

from rossum_agent.tools.utils import _truncate_output

_JQ_OUTPUT_LIMIT = 50_000
_GREP_MATCH_LIMIT = 200


def _resolve_content(value: str | dict) -> str:
    """Return file contents if value is an existing path, otherwise return value as-is.

    Accepts dict (already-parsed JSON) and serializes it back to a string.
    """
    if isinstance(value, dict):
        return json.dumps(value)
    path = Path(value)
    if path.is_absolute():
        try:
            return path.read_text(encoding="utf-8")
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            pass
    return value


@beta_tool
def run_jq(jq_query: str, data: str | dict) -> str:
    """Run a jq expression against JSON content or a file path containing JSON.

    Use to filter, transform, or extract values from API responses, schema
    definitions, annotation content, or any JSON data.

    Common patterns:
    - `.[] | select(.status == "active")` — filter array elements
    - `.[0].name` — extract nested value
    - `keys` — list object keys
    - `map(.id)` — extract field from array

    Null safety — fields like .workspace can be null; always guard before string ops:
    - `.workspace // "" | split("/") | last` — safe split with fallback
    - `select(.workspace != null) | .workspace | split("/") | last` — skip nulls
    - `.field | tonumber? // null` — safe numeric conversion

    Annotation content structure (get_annotation_content):
    - Top-level array of sections, each with `.children[]` (datapoints or multivalues)
    - Datapoint value is at `.content.value`, not `.value`
    - To find a datapoint: `[.. | objects | select(.schema_id == "amount_total")] | .[0].content.value`

    Args:
        jq_query: A jq expression to run.
        data: JSON string, absolute path to a JSON file, or parsed JSON dict.

    Returns:
        JSON result from the jq expression, or error message.
    """
    content = _resolve_content(data)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid JSON: {e}"})

    try:
        results = jq.compile(jq_query).input_value(parsed).all()
    except (ValueError, SystemError) as e:
        msg = f"jq error: {e}"
        err_str = str(e).lower()
        if "null" in err_str or "must be" in err_str or "cannot be" in err_str:
            msg += ' (hint: a field is likely null — use `// ""` fallback or `select(.field != null)` to guard)'
        return json.dumps({"status": "error", "message": msg})

    result = results[0] if len(results) == 1 else results
    serialized = json.dumps(result)
    if len(serialized) > _JQ_OUTPUT_LIMIT:
        serialized = _truncate_output(serialized, _JQ_OUTPUT_LIMIT)
        return json.dumps({"status": "success", "result": serialized, "truncated": True})
    return json.dumps({"status": "success", "result": result})


@beta_tool
def run_grep(pattern: str, text: str, case_insensitive: bool = True) -> str:
    """Search text for lines matching a regex pattern. Accepts raw text or a file path.

    Use to find relevant lines in large text payloads — log output, configuration
    files, schema dumps, or any multi-line string.

    Args:
        pattern: Regex or literal string to search for.
        text: Multi-line text or absolute path to a text file.
        case_insensitive: Whether to ignore case (default: True).

    Returns:
        Matching lines with line numbers, or error.
    """
    content = _resolve_content(text)

    try:
        compiled = re.compile(pattern, re.IGNORECASE if case_insensitive else 0)
    except re.error as e:
        return json.dumps({"status": "error", "message": f"Invalid regex: {e}"})

    matches = [{"line": i + 1, "text": line} for i, line in enumerate(content.splitlines()) if compiled.search(line)]

    if not matches:
        return json.dumps({"status": "success", "result": "No matches found"})

    truncated = False
    if len(matches) > _GREP_MATCH_LIMIT:
        total = len(matches)
        matches = matches[:_GREP_MATCH_LIMIT]
        matches.append({"line": -1, "text": f"... ({total - _GREP_MATCH_LIMIT} more matches)"})
        truncated = True

    return json.dumps({"status": "success", "matches": len(matches) - (1 if truncated else 0), "result": matches})
