"""Master Data Hub dataset listing and querying helpers for the Rossum Agent.

These functions let the agent explore MDH datasets and search entries directly,
complementing the lookup field tools in lookup.py.
"""

from __future__ import annotations

import json
import logging

import httpx

from rossum_agent.tools.core import get_context
from rossum_agent.tools.python_helpers.copilot._shared import (
    MDH_ALIAS_KEYS,
    OUTPUT_LIMIT,
    _build_mdh_aggregate_url,
    _build_mdh_datasets_url,
    _extract_rows,
    _handle_api_error,
    _json_headers,
    _request_with_retry,
    _resolve_mdh_dataset_identifier,
)
from rossum_agent.tools.utils import _truncate_output

logger = logging.getLogger(__name__)


def _extract_dataset_name(item: dict) -> str:
    """Extract a human-readable name, preferring metadata over top-level keys."""
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in MDH_ALIAS_KEYS:
            value = metadata.get(key)
            if isinstance(value, str) and value:
                return value
    for key in MDH_ALIAS_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return item.get("id", "")


def _extract_field_names(item: dict) -> list[str]:
    schema = item.get("schema")
    if isinstance(schema, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict):
            return [str(k) for k in properties]
    return []


def list_datasets() -> str:
    """List all Master Data Hub datasets with their names, IDs, and field schemas.

    Returns:
        JSON with status, dataset count, and a list of datasets. Each dataset
        includes id, name, description, and field names.
    """
    logger.info("list_datasets: fetching MDH dataset catalog")
    try:
        api_base_url, token = get_context().require_rossum_credentials()
        url = _build_mdh_datasets_url(api_base_url)

        with httpx.Client(timeout=20, follow_redirects=True) as client:
            response = _request_with_retry(client, "get", url, headers={"Authorization": f"Bearer {token}"})
            raw = response.json()

        items: list[dict]
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict) and isinstance(raw.get("results"), list):
            items = raw["results"]
        else:
            items = []

        datasets = []
        for item in items:
            if not isinstance(item, dict):
                continue
            entry: dict = {
                "id": item.get("id") or item.get("name", ""),
                "name": _extract_dataset_name(item),
                "fields": _extract_field_names(item),
            }
            metadata = item.get("metadata")
            if isinstance(metadata, dict) and metadata.get("description"):
                entry["description"] = metadata["description"]
            datasets.append(entry)

        output = json.dumps({"status": "success", "count": len(datasets), "datasets": datasets})
        return _truncate_output(output, OUTPUT_LIMIT)

    except Exception as e:
        return _handle_api_error(e, "list_datasets")


def search_dataset(
    dataset: str,
    match: dict | None = None,
    pipeline: list[dict] | None = None,
    limit: int = 50,
) -> str:
    """Search a Master Data Hub dataset using MongoDB-style queries.

    Use ``match`` for simple field:value filters (most common case).
    Use ``pipeline`` for full MongoDB aggregation stages (advanced).
    Both can be combined — ``match`` is prepended as a ``$match`` stage.
    Omit both to fetch the first ``limit`` rows.

    Args:
        dataset: Dataset name or imported-* identifier (e.g. 'Approved Vendors').
        match: Simple field:value filter dict.
            Supports MongoDB operators: ``{'vat_id': 'DE123'}`` (exact),
            ``{'name': {'$regex': 'acme', '$options': 'i'}}`` (regex).
        pipeline: Full MongoDB aggregation pipeline stages.
            Example: ``[{'$sort': {'name': 1}}, {'$project': {'name': 1, 'vat_id': 1}}]``
        limit: Maximum rows to return. Default 50. Auto-appended as ``$limit``
            unless already in the pipeline.

    Returns:
        JSON with dataset identifier, row_count, and rows array.
    """
    logger.info(f"search_dataset: dataset={dataset}, limit={limit}")
    try:
        api_base_url, token = get_context().require_rossum_credentials()
        aggregate_url = _build_mdh_aggregate_url(api_base_url)

        normalized = dataset.strip()
        if not normalized:
            return json.dumps({"status": "error", "error": "dataset must be a non-empty string"})

        resolved = _resolve_mdh_dataset_identifier(api_base_url, token, normalized) or normalized

        stages: list[dict] = []
        if match is not None:
            stages.append({"$match": match})
        if pipeline is not None:
            stages.extend(pipeline)

        has_limit = any("$limit" in stage for stage in stages)
        if not has_limit:
            stages.append({"$limit": limit})

        payload = {
            "dataset": resolved,
            "aggregate": stages,
            "collation": {},
            "let": {},
            "options": {},
        }

        with httpx.Client(timeout=30, follow_redirects=True) as client:
            response = _request_with_retry(client, "post", aggregate_url, json=payload, headers=_json_headers(token))
            raw = response.json()

        rows = _extract_rows(raw)

        output = json.dumps(
            {
                "status": "success",
                "dataset": resolved,
                "row_count": len(rows),
                "rows": rows,
            }
        )
        return _truncate_output(output, OUTPUT_LIMIT)

    except Exception as e:
        return _handle_api_error(e, "search_dataset")
