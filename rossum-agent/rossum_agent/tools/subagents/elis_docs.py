"""Elis API documentation search sub-agent."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import jq
from anthropic import beta_tool

from rossum_agent.tools.subagents.base import SubAgent, SubAgentConfig
from rossum_agent.tools.utils import _truncate_output

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAPI spec paths & output limits
# ---------------------------------------------------------------------------
OPENAPI_URL = "https://rossum.app/api/docs/openapi/openapi-specs/openapi.json"
_CACHE_PATH = Path(tempfile.gettempdir()) / "rossum_elis_openapi.json"
_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours

_JQ_OUTPUT_LIMIT = 50000
_GREP_MATCH_LIMIT = 200

# JSON keys whose string values are worth searching in grep
_SEARCHABLE_KEYS = frozenset(
    {
        "summary",
        "description",
        "title",
        "operationId",
        "name",
        "enum",
        "x-enumDescriptions",
        "default",
        "example",
        "format",
        "pattern",
    }
)

# Sub-agent context window budget
_TOOL_RESULT_LIMIT = 15000
_TOOL_RESULT_INNER_LIMIT = 12000


# ---------------------------------------------------------------------------
# Spec cache
# ---------------------------------------------------------------------------
class SpecCache:
    """In-memory + disk cache for the OpenAPI spec."""

    def __init__(self, cache_path: Path = _CACHE_PATH) -> None:
        self._cache_path = cache_path
        self._spec: dict[str, Any] | None = None
        self._mtime: float = 0

    def invalidate(self) -> None:
        """Clear in-memory and disk cache."""
        self._spec = None
        self._mtime = 0
        try:
            self._cache_path.unlink(missing_ok=True)
            logger.info(f"Deleted cached OpenAPI spec at {self._cache_path}")
        except OSError:
            pass

    def load(self) -> dict[str, Any]:
        """Load spec with in-memory caching keyed on file mtime."""
        path = self._ensure_downloaded()
        current_mtime = path.stat().st_mtime

        if self._spec is not None and current_mtime == self._mtime:
            return self._spec

        try:
            spec = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Cached spec invalid, re-downloading: {e}")
            path.unlink(missing_ok=True)
            path = self._ensure_downloaded()
            spec = json.loads(path.read_text())

        self._spec = spec
        self._mtime = current_mtime
        return spec

    def _ensure_downloaded(self) -> Path:
        """Download OpenAPI spec if not cached or cache is stale (>24h)."""
        if self._cache_path.exists():
            cache_age = time.time() - self._cache_path.stat().st_mtime
            if cache_age <= _CACHE_TTL_SECONDS:
                return self._cache_path
            logger.info(f"Cache expired ({cache_age / 3600:.1f}h old), re-downloading")

        logger.info(f"Downloading OpenAPI spec from {OPENAPI_URL}")
        resp = httpx.get(OPENAPI_URL, timeout=60)
        resp.raise_for_status()

        try:
            spec = json.loads(resp.text)
        except json.JSONDecodeError:
            logger.info("Response is not JSON, attempting to extract from Redocly HTML")
            try:
                spec = _extract_spec_from_redocly(resp.text)
            except (ValueError, json.JSONDecodeError) as e:
                logger.error(f"Failed to extract OpenAPI spec from HTML: {e}")
                raise ValueError(f"Could not extract OpenAPI spec from {OPENAPI_URL}") from e

        # Atomic write: write to temp file then rename to avoid partial reads
        spec_json = json.dumps(spec, indent=2)
        fd, tmp_path = tempfile.mkstemp(dir=self._cache_path.parent, prefix=".openapi_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(spec_json)
            Path(tmp_path).replace(self._cache_path)
        except BaseException:
            Path(tmp_path).unlink(missing_ok=True)
            raise

        logger.info(f"OpenAPI spec cached at {self._cache_path} ({len(spec_json)} bytes)")
        return self._cache_path


# Module-level singleton
_cache = SpecCache()


def _extract_spec_from_redocly(html: str) -> dict[str, Any]:
    """Extract OpenAPI spec from Redocly HTML page.

    The spec is embedded in __redoc_state JavaScript variable.
    """
    idx = html.find("__redoc_state")
    if idx < 0:
        raise ValueError("Could not find __redoc_state in HTML")

    eq_idx = html.find("=", idx)
    json_start = html.find("{", eq_idx)
    if json_start < 0:
        raise ValueError("Could not find JSON object after __redoc_state")

    decoder = json.JSONDecoder()
    data, _ = decoder.raw_decode(html, json_start)
    spec = data.get("spec", {}).get("data", {})
    if not spec.get("openapi"):
        raise ValueError("Extracted data does not contain OpenAPI spec")
    return spec


_MAX_WALK_DEPTH = 50


def _walk_string_values(
    obj: Any, path: str = "$", keys_filter: frozenset[str] | None = None, _depth: int = 0
) -> list[tuple[str, str]]:
    """Walk JSON returning (json_path, string_value) for fields matching keys_filter."""
    if _depth >= _MAX_WALK_DEPTH:
        return []
    results: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            child_path = f"{path}.{key}"
            if isinstance(value, str):
                if keys_filter is None or key in keys_filter:
                    results.append((child_path, value))
            else:
                results.extend(_walk_string_values(value, child_path, keys_filter, _depth + 1))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            child_path = f"{path}[{i}]"
            if isinstance(item, str):
                results.append((child_path, item))
            else:
                results.extend(_walk_string_values(item, child_path, keys_filter, _depth + 1))
    return results


# ---------------------------------------------------------------------------
# Low-level OpenAPI tools (used by the sub-agent)
# ---------------------------------------------------------------------------
@beta_tool
def elis_openapi_jq(jq_query: str) -> str:
    """Query the Rossum API OpenAPI spec with jq for endpoint details, schemas, and parameters.

    Common queries:
    - `.paths | keys` — list endpoints
    - `.paths | keys | map(select(contains("email")))` — find by keyword
    - `.paths["/v1/queues/{id}"]` — endpoint details
    - `.components.schemas.Queue` — schema definition
    - `.components.schemas | keys` — list schemas

    Args:
        jq_query: A jq query string to run against the OpenAPI spec.

    Returns:
        JSON result from the jq query, or error message.
    """
    logger.debug(f"elis_openapi_jq called with query: {jq_query!r}")
    try:
        spec = _cache.load()
    except (httpx.HTTPStatusError, ValueError, OSError) as e:
        logger.exception("Error loading OpenAPI spec")
        return json.dumps({"status": "error", "message": f"Error: {e}"})

    try:
        output = jq.compile(jq_query).input_value(spec).text()
    except (ValueError, SystemError) as e:
        return json.dumps({"status": "error", "message": f"jq error: {e}"})

    output = _truncate_output(output, _JQ_OUTPUT_LIMIT)
    return json.dumps({"status": "success", "result": output})


@beta_tool
def elis_openapi_grep(pattern: str, case_insensitive: bool = True) -> str:
    """Search API spec descriptions, summaries, operationIds, and field names by keyword.

    Searches only meaningful string values (not JSON structure). Use to discover
    endpoints or schemas by keyword when you don't know exact paths.
    For structured queries, prefer elis_openapi_jq.

    Examples: "pagination", "annotation_status", "email_template", "TxScript"

    Args:
        pattern: Text pattern to search for (supports regex).
        case_insensitive: Whether to ignore case (default: True).

    Returns:
        Matching values with their JSON paths.
    """
    logger.debug(f"elis_openapi_grep called with pattern: {pattern!r}")
    try:
        spec = _cache.load()
    except (httpx.HTTPStatusError, ValueError, OSError) as e:
        logger.exception("Error loading OpenAPI spec")
        return json.dumps({"status": "error", "message": f"Error: {e}"})

    try:
        compiled = re.compile(pattern, re.IGNORECASE if case_insensitive else 0)
    except re.error as e:
        return json.dumps({"status": "error", "message": f"Invalid regex pattern: {e}"})

    string_values = _walk_string_values(spec, keys_filter=_SEARCHABLE_KEYS)

    matches: list[dict[str, str]] = []
    for json_path, value in string_values:
        if compiled.search(value):
            matches.append({"path": json_path, "value": value if len(value) <= 300 else value[:300] + "..."})

    if not matches:
        return json.dumps({"status": "success", "result": "No matches found"})

    if len(matches) > _GREP_MATCH_LIMIT:
        total = len(matches)
        matches = matches[:_GREP_MATCH_LIMIT]
        matches.append({"path": "...", "value": f"({total - _GREP_MATCH_LIMIT} more matches)"})

    return json.dumps({"status": "success", "matches": len(matches), "result": matches})


# ---------------------------------------------------------------------------
# Sub-agent
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """You search the Rossum API OpenAPI spec to answer user questions about the API.

Use elis_openapi_grep to discover endpoints/schemas by keyword, then elis_openapi_jq for details.

Provide: endpoint paths, HTTP methods, request/response schemas, required fields, code examples."""

_TOOLS = [elis_openapi_jq.to_dict(), elis_openapi_grep.to_dict()]


class ElisDocsSubAgent(SubAgent):
    """Sub-agent for searching Elis API documentation."""

    def __init__(self) -> None:
        super().__init__(
            SubAgentConfig(
                tool_name="search_elis_docs",
                system_prompt=_SYSTEM_PROMPT,
                tools=_TOOLS,  # ty:ignore[invalid-argument-type] - BetaToolParam is structurally dict[str, Any]
                max_iterations=5,
            )
        )

    def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        if tool_name == "elis_openapi_jq":
            result = elis_openapi_jq(tool_input["jq_query"])
        elif tool_name == "elis_openapi_grep":
            result = elis_openapi_grep(tool_input["pattern"], tool_input.get("case_insensitive", True))
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        # Truncate inside the JSON envelope to avoid feeding broken JSON to the LLM
        if len(result) > _TOOL_RESULT_LIMIT:
            try:
                parsed = json.loads(result)
                if (
                    "result" in parsed
                    and isinstance(parsed["result"], str)
                    and len(parsed["result"]) > _TOOL_RESULT_INNER_LIMIT
                ):
                    parsed["result"] = (
                        parsed["result"][:_TOOL_RESULT_INNER_LIMIT] + "\n... (truncated, refine your query)"
                    )
                    return json.dumps(parsed)
            except (json.JSONDecodeError, TypeError):
                pass
            return result[:_TOOL_RESULT_LIMIT] + "\n... (truncated, refine your query)"
        return result


@beta_tool
def search_elis_docs(query: str) -> str:
    """Sub-agent that thoroughly explores the OpenAPI spec for comprehensive API answers.

    Iterates through the spec to find related endpoints, schemas, and connections.
    Good for complex questions requiring multiple lookups or discovering related APIs.

    Args:
        query: API question. Examples: 'webhook payload schema', 'annotation export flow',
        'document splitting endpoint', 'all fields in annotation response'.

    Returns:
        JSON with analysis of relevant API documentation.
    """
    if not query.strip():
        return json.dumps({"status": "error", "message": "Query is required"})

    try:
        agent = ElisDocsSubAgent()
        result = agent.run(query)
    except Exception as e:
        logger.exception("search_elis_docs failed")
        return json.dumps({"status": "error", "message": f"Sub-agent error: {e}"})

    response: dict[str, object] = {
        "status": "success",
        "answer": result.analysis,
        "iterations": result.iterations_used,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }
    if result.tool_calls:
        response["searches"] = result.tool_calls
    return json.dumps(response)
