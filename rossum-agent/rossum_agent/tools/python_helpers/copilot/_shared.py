"""Shared helpers for copilot and MDH functions."""

from __future__ import annotations

import copy
import json
import logging
import re
import time

import httpx

logger = logging.getLogger(__name__)


def _handle_api_error(e: Exception, func_name: str) -> str:
    """Format an API error into a JSON error response and log it."""
    if isinstance(e, httpx.HTTPStatusError):
        logger.exception(f"HTTP error in {func_name}")
        return json.dumps({"status": "error", "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}"})
    logger.exception(f"Error in {func_name}")
    return json.dumps({"status": "error", "error": str(e)})


_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0

MDH_ALIAS_KEYS = ("name", "label", "title", "dataset_name", "slug")
_MDH_IDENTIFIER_KEYS = ("id", "_id", "dataset_id", "dataset", "name")

OUTPUT_LIMIT = 50000


def _json_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


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


def _fetch_schema_content(api_base_url: str, token: str, schema_id: int) -> list[dict]:
    url = f"{api_base_url.rstrip('/')}/schemas/{schema_id}"
    with httpx.Client(timeout=30) as client:
        response = _request_with_retry(client, "get", url, headers={"Authorization": f"Bearer {token}"})
        return response.json()["content"]


def _find_field_in_schema(nodes: list[dict], field_id: str) -> bool:
    for node in nodes:
        if node.get("id") == field_id:
            return True
        if "children" in node:
            children = node["children"]
            if isinstance(children, list) and _find_field_in_schema(children, field_id):
                return True
            if isinstance(children, dict) and _find_field_in_schema([children], field_id):
                return True
    return False


def _inject_field_into_schema(schema_content: list[dict], field_def: dict, section_id: str) -> list[dict]:
    """Inject a field definition into the specified section of schema_content.

    The suggest_formula / suggest_computed_field APIs require the target field
    to exist in schema_content. Callers build the field_def via their own
    ``_create_*_field_definition`` helper and pass it here.
    """
    field_id = field_def.get("id")
    if not field_id or _find_field_in_schema(schema_content, field_id):
        return schema_content

    modified = copy.deepcopy(schema_content)

    for section in modified:
        if section.get("id") == section_id and section.get("category") == "section":
            section.setdefault("children", []).append(field_def)
            return modified

    if modified and modified[0].get("category") == "section":
        modified[0].setdefault("children", []).append(field_def)
    else:
        modified.append(field_def)

    return modified


# ---------------------------------------------------------------------------
# MDH shared utilities
# ---------------------------------------------------------------------------


def _build_mdh_datasets_url(api_base_url: str) -> str:
    base = re.sub(r"/(?:api/)?v1/?$", "", api_base_url.rstrip("/"))
    return f"{base}/svc/master-data-hub/api/v2/datasets?limit=1000"


def _build_mdh_aggregate_url(api_base_url: str) -> str:
    base = re.sub(r"/(?:api/)?v1/?$", "", api_base_url.rstrip("/"))
    return f"{base}/svc/master-data-hub/api/v1/data/aggregate"


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


def _normalize_token(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value.strip().lower())


def _collect_dataset_aliases(item: dict) -> list[str]:
    aliases: list[str] = []
    for key in MDH_ALIAS_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value:
            aliases.append(value)

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in MDH_ALIAS_KEYS:
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
