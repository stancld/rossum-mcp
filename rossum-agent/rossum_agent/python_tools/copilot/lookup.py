"""Lookup field suggestion and evaluation helpers for the Rossum Agent.

This module provides functions to get lookup field suggestions from Rossum's internal API
and evaluate them against real annotations.
"""

from __future__ import annotations

import copy
import json
import logging
import re
import time

import httpx
import jq as jq_lib  # ty: ignore[unresolved-import] - no type stubs for jq

from rossum_agent.python_tools.copilot._shared import (
    _fetch_schema_content,
    _inject_field_into_schema,
    _json_headers,
)
from rossum_agent.tools.core import get_context
from rossum_agent.tools.utils import _truncate_output

logger = logging.getLogger(__name__)

_SUGGEST_COMPUTED_FIELD_TIMEOUT = 60
_EVALUATE_COMPUTED_FIELDS_TIMEOUT = 60
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


def _request_with_retry(client: httpx.Client, method: str, url: str, **kwargs: object) -> httpx.Response:
    """Execute an HTTP request with retry on 429 Too Many Requests."""
    for attempt in range(_MAX_RETRIES + 1):
        response = getattr(client, method)(url, **kwargs)
        if response.status_code == 429 and attempt < _MAX_RETRIES:
            delay = _RETRY_BASE_DELAY * (2**attempt)
            logger.info(
                f"Rate limited (429) on {url}, retrying in {delay:.0f}s (attempt {attempt + 1}/{_MAX_RETRIES})"
            )
            time.sleep(delay)
            continue
        response.raise_for_status()
        return response
    raise RuntimeError("Unreachable")


def _build_suggest_computed_field_url(api_base_url: str) -> str:
    return f"{api_base_url.rstrip('/')}/internal/schemas/suggest_computed_field"


def _build_evaluate_computed_fields_url(api_base_url: str) -> str:
    return f"{api_base_url.rstrip('/')}/internal/schemas/evaluate_computed_fields"


def _build_mdh_datasets_url(api_base_url: str) -> str:
    base = re.sub(r"/(?:api/)?v1/?$", "", api_base_url.rstrip("/"))
    return f"{base}/svc/master-data-hub/api/v2/datasets?limit=1000"


def _build_mdh_aggregate_url(api_base_url: str) -> str:
    base = re.sub(r"/(?:api/)?v1/?$", "", api_base_url.rstrip("/"))
    return f"{base}/svc/master-data-hub/api/v1/data/aggregate"


# In-memory cache for downloaded datasets (keyed by resolved ID and input alias)
_dataset_cache: dict[str, object] = {}

# In-memory cache for suggested field definitions (keyed by field_schema_id)
_field_definition_cache: dict[str, dict] = {}

_JQ_OUTPUT_LIMIT = 50000


def _get_cached_dataset(dataset: str) -> object | None:
    """Look up a dataset in the cache by exact key or lowered alias."""
    stripped = dataset.strip()
    return _dataset_cache.get(stripped) or _dataset_cache.get(stripped.lower())


def _extract_rows(raw_response: object) -> list:
    """Extract the rows array from an MDH aggregate response."""
    if isinstance(raw_response, list):
        return raw_response
    if isinstance(raw_response, dict):
        list_val = raw_response.get("list")  # ty: ignore[invalid-argument-type] - dict[Unknown, Unknown] false positive
        if isinstance(list_val, list):
            return list_val
        results_val = raw_response.get("results")  # ty: ignore[invalid-argument-type] - dict[Unknown, Unknown] false positive
        if isinstance(results_val, list):
            return results_val
    return []


def _cache_dataset(resolved: str, alias: str, data: object) -> None:
    """Extract rows and store under both the resolved ID and the user-provided alias."""
    rows = _extract_rows(data)
    _dataset_cache[resolved] = rows
    lowered = alias.strip().lower()
    if lowered != resolved:
        _dataset_cache[lowered] = rows


_MDH_IDENTIFIER_KEYS = ("id", "_id", "dataset_id", "dataset", "name")
_MDH_ALIAS_KEYS = ("name", "label", "title", "dataset_name", "slug")


def _normalize_token(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value.strip().lower())


def _collect_dataset_aliases(item: dict) -> list[str]:
    aliases: list[str] = []
    for key in _MDH_ALIAS_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value:
            aliases.append(value)

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in _MDH_ALIAS_KEYS:
            value = metadata.get(key)
            if isinstance(value, str) and value:
                aliases.append(value)

    return aliases


def _collect_identifier_candidates(item: dict) -> list[str]:
    candidates: list[str] = []
    for key in _MDH_IDENTIFIER_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    return candidates


def _resolve_item_identifier(item: object, normalized_dataset: str) -> str | None:
    if not isinstance(item, dict):
        return None

    imported_identifiers = [
        candidate for candidate in _collect_identifier_candidates(item) if candidate.startswith("imported-")
    ]
    if not imported_identifiers:
        return None

    normalized_canonical = _normalize_token(normalized_dataset)
    for identifier in imported_identifiers:
        if identifier.lower() == normalized_dataset or _normalize_token(identifier) == normalized_canonical:
            return identifier

    aliases = _collect_dataset_aliases(item)
    if any(_normalize_token(alias) == normalized_canonical for alias in aliases):
        return imported_identifiers[0]
    return None


def _resolve_mdh_dataset_identifier(api_base_url: str, token: str, dataset: str) -> str | None:
    """Resolve a user-facing dataset name to an MDH imported dataset identifier."""
    normalized = dataset.strip().lower()
    if not normalized:
        return None
    if normalized.startswith("imported-"):
        return dataset.strip()

    try:
        url = _build_mdh_datasets_url(api_base_url)
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            response = _request_with_retry(client, "get", url, headers={"Authorization": f"Bearer {token}"})
            metadata = response.json()
    except Exception:
        logger.info(
            "Failed to resolve MDH dataset identifier from datasets endpoint; dataset preselection skipped.",
            exc_info=True,
        )
        return None

    dataset_items: list[object]
    if isinstance(metadata, list):
        dataset_items = metadata
    elif isinstance(metadata, dict) and isinstance(metadata.get("results"), list):
        dataset_items = metadata["results"]
    else:
        return None

    for item in dataset_items:
        identifier = _resolve_item_identifier(item, normalized)
        if identifier:
            return identifier
    return None


def _create_lookup_field_definition(label: str, field_schema_id: str | None = None) -> dict:
    """Create a properly structured lookup field definition stub."""
    return {
        "id": field_schema_id or label.lower().replace(" ", "_"),
        "label": label,
        "type": "enum",
        "category": "datapoint",
        "can_export": True,
        "constraints": {"required": False},
        "disable_prediction": False,
        "enum_value_type": "string",
        "hidden": False,
        "options": [],
        "rir_field_names": [],
        "score_threshold": 0,
        "suggest": True,
        "ui_configuration": {"type": "lookup", "edit": "disabled"},
        "matching": {
            "type": "master_data_hub",
            "configuration": {},
        },
    }


def _fetch_annotation_content(api_base_url: str, token: str, annotation_url: str) -> list[dict]:
    """Fetch annotation content from Rossum API."""
    if annotation_url.startswith("http"):
        url = annotation_url
    else:
        # annotation_url is "/api/v1/annotations/..." — strip to just "/annotations/..." to avoid
        # duplicating the /api/v1 prefix already present in api_base_url
        path = annotation_url.removeprefix("/api/v1")
        url = f"{api_base_url.rstrip('/')}{path}"
    with httpx.Client(timeout=30) as client:
        response = _request_with_retry(client, "get", f"{url}/content", headers={"Authorization": f"Bearer {token}"})
        return response.json()["content"]


def _replace_field_in_nodes(nodes: list[dict], field_id: str, replacement: dict) -> bool:
    """Recursively replace a field by id. Returns True if found and replaced."""
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        if node.get("id") == field_id:
            nodes[i] = replacement
            return True
        children = node.get("children")
        if isinstance(children, list) and _replace_field_in_nodes(children, field_id, replacement):
            return True
    return False


def _update_or_inject_field(schema_content: list[dict], field_definition: dict) -> list[dict]:
    """Return a copy of schema_content with field_definition merged in (replace existing or inject).

    Used by evaluate_lookup_field to test a candidate config in-memory without writing to the API.
    """
    field_id = field_definition.get("id")
    if not field_id:
        return schema_content
    modified = copy.deepcopy(schema_content)
    fd = copy.deepcopy(field_definition)
    if _replace_field_in_nodes(modified, field_id, fd):
        return modified
    # Not in schema yet — inject into first section found, or append to root
    for section in modified:
        if isinstance(section, dict) and section.get("category") == "section":
            section.setdefault("children", []).append(fd)
            return modified
    modified.append(fd)
    return modified


def _find_lookup_field_ids(schema_content: list[dict]) -> set[str]:
    """Find all schema IDs of lookup fields in the schema."""
    ids: set[str] = set()
    for node in schema_content:
        if not isinstance(node, dict):
            continue
        if node.get("ui_configuration", {}).get("type") == "lookup":
            ids.add(node["id"])
        children = node.get("children")
        if isinstance(children, list):
            ids.update(_find_lookup_field_ids(children))
    return ids


_FIELD_REF_RE = re.compile(r"field\.(\w+)")


def _get_placeholder_field_ids(schema_content: list[dict]) -> dict[str, set[str]]:
    """Map each lookup field ID to the set of field schema_ids referenced in its placeholders/variables."""
    result: dict[str, set[str]] = {}
    for node in schema_content:
        if not isinstance(node, dict):
            continue
        if node.get("ui_configuration", {}).get("type") == "lookup":
            config = node.get("matching", {}).get("configuration", {})
            # API may return field references under "placeholders" or "variables"
            placeholders = config.get("placeholders") or config.get("variables") or {}
            field_ids: set[str] = set()
            for placeholder in placeholders.values():
                formula = placeholder.get("__formula", "") if isinstance(placeholder, dict) else ""
                field_ids.update(_FIELD_REF_RE.findall(formula))
            result[node["id"]] = field_ids
        children = node.get("children")
        if isinstance(children, list):
            result.update(_get_placeholder_field_ids(children))
    return result


def _collect_datapoint_values(annotation_content: list[dict], field_ids: set[str]) -> dict[str, str]:
    """Walk annotation content and collect schema_id -> value for specified fields."""
    values: dict[str, str] = {}
    for node in annotation_content:
        if not isinstance(node, dict):
            continue
        if node.get("category") == "datapoint" and node.get("schema_id") in field_ids:
            values[node["schema_id"]] = node.get("content", {}).get("value", "")
        children = node.get("children")
        if isinstance(children, list):
            values.update(_collect_datapoint_values(children, field_ids))
    return values


def _extract_lookup_results(
    annotation_content: list[dict], lookup_ids: set[str], placeholder_map: dict[str, set[str]]
) -> list[dict]:
    """Extract lookup field results with matching context from evaluated annotation content."""
    # Collect all referenced field values in a single pass over the full tree
    all_ref_ids: set[str] = set()
    for ref_ids in placeholder_map.values():
        all_ref_ids.update(ref_ids)
    field_values = _collect_datapoint_values(annotation_content, all_ref_ids) if all_ref_ids else {}

    return _walk_for_lookup_results(annotation_content, lookup_ids, placeholder_map, field_values)


def _walk_for_lookup_results(
    nodes: list[dict], lookup_ids: set[str], placeholder_map: dict[str, set[str]], field_values: dict[str, str]
) -> list[dict]:
    results: list[dict] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("category") == "datapoint" and node.get("schema_id") in lookup_ids:
            content = node.get("content") or {}
            entry: dict = {
                "schema_id": node["schema_id"],
                "value": content.get("value", ""),
                "options": content.get("options", []),
            }
            ref_ids = placeholder_map.get(node["schema_id"], set())
            if ref_ids:
                entry["matching_fields"] = {fid: field_values.get(fid, "") for fid in sorted(ref_ids)}
            results.append(entry)
        children = node.get("children")
        if isinstance(children, list):
            results.extend(_walk_for_lookup_results(children, lookup_ids, placeholder_map, field_values))
    return results


def suggest_lookup_field(
    label: str,
    hint: str,
    schema_id: int,
    section_id: str,
    field_schema_id: str | None = None,
    dataset: str | None = None,
) -> str:
    """Get AI-generated lookup field matching configuration.

    Args:
        label: Display label for the field (e.g., 'Vendor Match').
        hint: Natural language description of the lookup logic (e.g., 'Match vendors by VAT ID').
        schema_id: The numeric schema ID. Get this from get(entity="queue", id=queue_id) or search(query={"entity": "queue"}).
        section_id: Section ID where the field belongs. Ask the user if not specified.
        field_schema_id: Optional ID for the lookup field. Defaults to label.lower().replace(" ", "_").
        dataset: Optional Master Data Hub dataset name (e.g., 'Vendors'). Appended to hint for the API.

    Returns:
        JSON with suggested matching configuration and field_definition for use with patch_schema.
    """
    field_schema_id = field_schema_id or label.lower().replace(" ", "_")
    if dataset:
        hint = f"{hint} (dataset: {dataset})"
    logger.info(f"suggest_lookup_field: {field_schema_id=}, {schema_id=}, {section_id=}, hint={hint[:100]}...")

    try:
        api_base_url, token = get_context().require_rossum_credentials()
        url = _build_suggest_computed_field_url(api_base_url)

        schema_content = _fetch_schema_content(api_base_url, token, schema_id)
        field_def = _create_lookup_field_definition(label, field_schema_id)
        enriched_schema = _inject_field_into_schema(schema_content, field_def, section_id)

        # Pre-populate dataset in the stub so the backend prompt shows "Preselected dataset: <name>".
        # Only injected when we can resolve to a concrete imported identifier.
        if dataset:
            resolved_dataset = _resolve_mdh_dataset_identifier(api_base_url, token, dataset)
            if resolved_dataset:
                logger.info(
                    "suggest_lookup_field: injecting matching.configuration.dataset only when resolved to imported ID "
                    f"(input='{dataset}', resolved='{resolved_dataset}')"
                )
                for section in enriched_schema:
                    for child in section.get("children", []):
                        if child.get("id") == field_schema_id:
                            child.get("matching", {}).get("configuration", {})["dataset"] = resolved_dataset
                            break
            else:
                logger.info(
                    "suggest_lookup_field: skipping matching.configuration.dataset injection because input did not "
                    f"resolve to imported ID (input='{dataset}')"
                )

        payload = {"field_schema_id": field_schema_id, "hint": hint, "schema_content": enriched_schema}

        logger.debug(f"Calling suggest_computed_field API: {url}")

        with httpx.Client(timeout=_SUGGEST_COMPUTED_FIELD_TIMEOUT) as client:
            response = _request_with_retry(
                client,
                "post",
                url,
                json=payload,
                headers=_json_headers(token),
            )
            result = response.json()

        suggestions = result.get("results", [])
        if not suggestions:
            return json.dumps(
                {
                    "status": "no_suggestions",
                    "message": "No lookup field suggestions returned. Try rephrasing the hint.",
                }
            )

        top = suggestions[0]

        field_definition = _create_lookup_field_definition(label, field_schema_id)
        for key in ("matching", "ui_configuration", "type", "options", "enum_value_type"):
            if key in top:
                field_definition[key] = top[key]

        _field_definition_cache[field_schema_id] = field_definition

        dataset_name = field_definition.get("matching", {}).get("configuration", {}).get("dataset")

        return json.dumps(
            {
                "status": "success",
                "field_schema_id": field_schema_id,
                "section_id": section_id,
                "dataset": dataset_name,
                "matching": field_definition.get("matching", {}),
            }
        )

    except httpx.HTTPStatusError as e:
        logger.exception("HTTP error in suggest_lookup_field")
        return json.dumps(
            {
                "status": "error",
                "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}",
            }
        )
    except Exception as e:
        logger.exception("Error in suggest_lookup_field")
        return json.dumps({"status": "error", "error": str(e)})


def evaluate_lookup_field(
    schema_id: int,
    annotation_urls: list[str],
    field_definition: dict | None = None,
    field_schema_id: str | None = None,
) -> str:
    """Evaluate lookup fields on one or more annotations to test matching configuration.

    Args:
        schema_id: The numeric schema ID containing the lookup field.
        annotation_urls: List of annotation URLs or paths (e.g., ['/api/v1/annotations/123456']).
        field_definition: Optional field definition dict. When provided, merged into schema in-memory.
        field_schema_id: Alternative to field_definition — looks up the cached definition from the
            most recent suggest_lookup_field call. Preferred over passing field_definition directly.

    Returns:
        JSON with per-annotation lookup field results (schema_id, value, options), automation blockers, and messages.
        Empty automation_blockers and messages lists are omitted.
    """
    logger.info(f"evaluate_lookup_field: {schema_id=}, {len(annotation_urls)} annotation(s)")

    try:
        if field_definition is None and field_schema_id:
            field_definition = _field_definition_cache.get(field_schema_id)
            if field_definition is None:
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"No cached definition for '{field_schema_id}'. Call suggest_lookup_field first or provide field_definition directly.",
                    }
                )

        api_base_url, token = get_context().require_rossum_credentials()
        url = _build_evaluate_computed_fields_url(api_base_url)

        schema_content = _fetch_schema_content(api_base_url, token, schema_id)
        if field_definition:
            schema_content = _update_or_inject_field(schema_content, field_definition)
        lookup_ids = _find_lookup_field_ids(schema_content)
        placeholder_map = _get_placeholder_field_ids(schema_content)

        results = []
        with httpx.Client(timeout=_EVALUATE_COMPUTED_FIELDS_TIMEOUT) as client:
            for annotation_url in annotation_urls:
                annotation_content = _fetch_annotation_content(api_base_url, token, annotation_url)
                annotation_ref = (
                    annotation_url
                    if annotation_url.startswith("http")
                    else f"{api_base_url.rstrip('/')}{annotation_url.removeprefix('/api/v1')}"
                )
                payload = {
                    "schema_content": schema_content,
                    "annotation_content": annotation_content,
                    "annotation": annotation_ref,
                }
                response = _request_with_retry(
                    client,
                    "post",
                    url,
                    json=payload,
                    headers=_json_headers(token),
                )
                result = response.json()
                lookup_results = _extract_lookup_results(
                    result.get("annotation_content", []), lookup_ids, placeholder_map
                )
                entry: dict = {"annotation_url": annotation_url, "lookup_results": lookup_results}
                if automation_blockers := result.get("automation_blockers"):
                    entry["automation_blockers"] = automation_blockers
                if messages := result.get("messages"):
                    entry["messages"] = messages
                results.append(entry)

        return json.dumps({"status": "success", "results": results})

    except httpx.HTTPStatusError as e:
        logger.exception("HTTP error in evaluate_lookup_field")
        return json.dumps(
            {
                "status": "error",
                "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}",
            }
        )
    except Exception as e:
        logger.exception("Error in evaluate_lookup_field")
        return json.dumps({"status": "error", "error": str(e)})


def get_lookup_dataset_raw_values(dataset: str, limit: int = 10000) -> str:
    """Fetch raw rows from a Master Data Hub dataset used by lookup matching.

    Args:
        dataset: Dataset identifier or human-readable name (for example 'approved-vendors').
        limit: Maximum number of rows to fetch. Defaults to 10000.

    Returns:
        JSON with resolved dataset identifier and row count. Raw data is cached in memory;
        use query_lookup_dataset to explore it without polluting the agent context.
    """
    logger.info(f"get_lookup_dataset_raw_values: dataset={dataset}, limit={limit}")

    try:
        api_base_url, token = get_context().require_rossum_credentials()
        aggregate_url = _build_mdh_aggregate_url(api_base_url)

        normalized_dataset = dataset.strip()
        if not normalized_dataset:
            return json.dumps({"status": "error", "error": "dataset must be a non-empty string"})

        resolved_dataset = (
            _resolve_mdh_dataset_identifier(api_base_url, token, normalized_dataset) or normalized_dataset
        )
        payload = {
            "aggregate": [{"$limit": limit}],
            "collation": {},
            "let": {},
            "options": {},
            "dataset": resolved_dataset,
        }

        with httpx.Client(timeout=60) as client:
            response = _request_with_retry(
                client,
                "post",
                aggregate_url,
                json=payload,
                headers=_json_headers(token),
            )
            raw_response = response.json()

        _cache_dataset(resolved_dataset, normalized_dataset, raw_response)

        row_count: int | None = None
        if isinstance(raw_response, list):
            row_count = len(raw_response)
        elif isinstance(raw_response, dict):
            if isinstance(raw_response.get("list"), list):
                row_count = len(raw_response["list"])
            elif isinstance(raw_response.get("results"), list):
                row_count = len(raw_response["results"])

        return json.dumps(
            {
                "status": "success",
                "dataset": resolved_dataset,
                "limit": limit,
                "row_count": row_count,
                "note": "Dataset cached. Use query_lookup_dataset to explore rows.",
            }
        )
    except httpx.HTTPStatusError as e:
        logger.exception("HTTP error in get_lookup_dataset_raw_values")
        return json.dumps({"status": "error", "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}"})
    except Exception as e:
        logger.exception("Error in get_lookup_dataset_raw_values")
        return json.dumps({"status": "error", "error": str(e)})


def query_lookup_dataset(dataset: str, jq_query: str) -> str:
    """Run a jq query on a previously downloaded MDH dataset (stored as a flat rows array).

    The dataset must have been fetched first with get_lookup_dataset_raw_values.
    The cached data is always a flat array of row objects — query with `.[]`, `.[0]`, etc.

    Always start with `.[0] | keys` to discover column names — they often contain spaces.
    Use `."Column Name"` syntax to reference keys with spaces.

    Common queries:
    - `length` — row count
    - `.[0] | keys` — column names (do this first)
    - `.[:5]` — first 5 rows
    - `.[] | select(.Name | test("acme"; "i"))` — filter rows by regex
    - `[.[] | ."VAT ID"] | unique` — unique values of a column with spaces in name
    - `.[] | select(."VAT ID" == "DE811234567")` — exact match

    Args:
        dataset: Dataset identifier or name (same as used in get_lookup_dataset_raw_values).
        jq_query: A jq query string to run against the cached rows array.

    Returns:
        JSON result from the jq query, or error if dataset not cached.
    """
    logger.info(f"query_lookup_dataset: dataset={dataset}, jq_query={jq_query}")

    cached = _get_cached_dataset(dataset)
    if cached is None:
        return json.dumps(
            {
                "status": "error",
                "error": f"Dataset '{dataset}' not found in cache. Call get_lookup_dataset_raw_values first.",
            }
        )

    try:
        output = jq_lib.compile(jq_query).input_value(cached).text()
    except (ValueError, SystemError) as e:
        return json.dumps({"status": "error", "error": f"jq error: {e}"})

    output = _truncate_output(output, _JQ_OUTPUT_LIMIT)
    return json.dumps({"status": "success", "result": output})
