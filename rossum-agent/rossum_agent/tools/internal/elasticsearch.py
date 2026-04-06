"""Elasticsearch search tool for datapoint statistics and annotation analytics.

Depends on Rossum's closed-source infrastructure (internal Elasticsearch clusters).
Not available in the open-source distribution.

Defense-in-depth: execute_python blocks ``import elasticsearch`` (and other network
libraries) so the agent cannot bypass this tool's org-scoping and validation.
See ``TestExecPythonCannotBypassElasticsearch`` in tests/tools/internal/test_elasticsearch.py.
"""

from __future__ import annotations

import json
import logging
import os

from anthropic import beta_tool
from elasticsearch import Elasticsearch
from rossum_api import SyncRossumAPIClient
from rossum_api.dtos import Token

from rossum_agent.tools.core import get_context
from rossum_agent.tools.utils import _truncate_output

logger = logging.getLogger(__name__)

_OUTPUT_LIMIT = 50_000


# Safety gate: only these index prefixes are allowed. Prevents querying
# system indices, Kibana metadata, or other unintended data.
def _get_allowed_index_prefixes() -> tuple[str, ...]:
    """Read allowed index prefixes from env at call time (not import time)."""
    return tuple(p.strip() for p in os.environ.get("ELASTICSEARCH_ALLOWED_INDEX_PREFIXES", "").split(",") if p.strip())


# Only these top-level body keys may be passed to es.search(). Blocks
# runtime_mappings, script_fields, and other keys that could shadow fields
# or execute arbitrary scripts, bypassing the organization_id filter.
ALLOWED_BODY_KEYS: frozenset[str] = frozenset(
    {"query", "aggs", "aggregations", "size", "from", "sort", "_source", "track_total_hits"}
)

# Aggregation types that compute background statistics across the full index,
# leaking cross-organization term frequency information.
BLOCKED_AGG_TYPES: frozenset[str] = frozenset({"global", "significant_terms", "significant_text"})

# Keys that enable arbitrary Painless script execution inside aggregations.
# Note: "script" (used in script queries) is intentionally allowed — it's a
# legitimate DSL construct for analytical filters (e.g. string-length checks).
BLOCKED_SCRIPT_KEYS: frozenset[str] = frozenset({"scripted_metric", "bucket_script", "bucket_selector", "_script"})

# Elasticsearch uses both "aggs" and "aggregations" as equivalent keys.
_AGG_KEYS = ("aggs", "aggregations")


def _deployment_location_to_env_prefix(deployment_location: str) -> str:
    """Convert a deployment location (e.g., 'prod-eu2') to an env var prefix (e.g., 'PROD_EU2')."""
    return deployment_location.upper().replace("-", "_")


def _get_es_client(deployment_location: str) -> Elasticsearch:
    """Create an Elasticsearch client for the given deployment location.

    Looks up credentials from env vars named ELASTICSEARCH_{LOCATION}_URL, etc.
    Falls back to generic ELASTICSEARCH_URL if location-specific vars are not set.

    Raises:
        RuntimeError: If Elasticsearch credentials are not configured.
    """
    prefix = _deployment_location_to_env_prefix(deployment_location)
    es_url = os.environ.get(f"ELASTICSEARCH_{prefix}_URL") or os.environ.get("ELASTICSEARCH_URL")
    if not es_url:
        raise RuntimeError(
            f"Elasticsearch is not configured for deployment '{deployment_location}'. "
            f"Set ELASTICSEARCH_{prefix}_URL (or ELASTICSEARCH_URL as fallback), "
            f"ELASTICSEARCH_{prefix}_USERNAME, and ELASTICSEARCH_{prefix}_PASSWORD."
        )

    username = os.environ.get(f"ELASTICSEARCH_{prefix}_USERNAME") or os.environ.get("ELASTICSEARCH_USERNAME")
    password = os.environ.get(f"ELASTICSEARCH_{prefix}_PASSWORD") or os.environ.get("ELASTICSEARCH_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            f"Elasticsearch credentials missing for deployment '{deployment_location}'. "
            f"Set ELASTICSEARCH_{prefix}_USERNAME and ELASTICSEARCH_{prefix}_PASSWORD "
            f"(or ELASTICSEARCH_USERNAME/ELASTICSEARCH_PASSWORD as fallback)."
        )

    verify_certs_val = os.environ.get(f"ELASTICSEARCH_{prefix}_VERIFY_CERTS") or os.environ.get(
        "ELASTICSEARCH_VERIFY_CERTS", "true"
    )
    verify_certs = verify_certs_val.lower() not in ("0", "false", "no")

    return Elasticsearch(
        es_url,
        basic_auth=(username, password),
        verify_certs=verify_certs,
        ssl_show_warn=verify_certs,
        request_timeout=120,
    )


def _get_org_info() -> tuple[int, str]:
    """Resolve the organization ID and deployment location from the Rossum API.

    Every ES query must be scoped to the current organization, and the correct
    ES cluster is selected based on the deployment location.
    """
    ctx = get_context()
    credentials = ctx.get_rossum_credentials()
    if not credentials:
        raise RuntimeError("Rossum API credentials are not available. Cannot resolve organization ID.")

    base_url, api_token = credentials
    client = SyncRossumAPIClient(base_url=base_url, credentials=Token(token=api_token))

    org_id = next(client.list_organizations()).id
    org_group = next(client.list_organization_groups())

    return org_id, org_group.deployment_location


def _validate_index(index: str) -> None:
    """Validate that the index matches an allowed prefix.

    Raises:
        ValueError: If the index doesn't match any allowed prefix.
    """
    prefixes = _get_allowed_index_prefixes()
    if not any(index.startswith(prefix) for prefix in prefixes):
        allowed = ", ".join(f'"{p}*"' for p in prefixes)
        raise ValueError(f"Index {index!r} is not allowed. Permitted prefixes: {allowed}")


def _validate_body_deep(body: dict) -> None:
    """Recursively validate the DSL body for unsafe constructs.

    Blocks `global` aggregations (which bypass query-level filters) and
    script execution keys (which allow arbitrary Painless code).

    Raises:
        ValueError: If a blocked construct is found.
    """
    for key in _AGG_KEYS:
        aggs = body.get(key)
        if isinstance(aggs, dict):
            _validate_aggs(aggs)
    _reject_scripts(body)


def _validate_aggs(aggs: dict) -> None:
    for name, agg_body in aggs.items():
        if not isinstance(agg_body, dict):
            continue
        if blocked := set(agg_body.keys()) & BLOCKED_AGG_TYPES:
            raise ValueError(
                f"Aggregation {name!r} uses blocked type(s): {sorted(blocked)}. These bypass the organization filter."
            )
        for sub_key in _AGG_KEYS:
            sub = agg_body.get(sub_key)
            if isinstance(sub, dict):
                _validate_aggs(sub)


def _reject_scripts(obj: object, path: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in BLOCKED_SCRIPT_KEYS:
                raise ValueError(
                    f"Script key {key!r} at {path}.{key} is not allowed. Arbitrary script execution is blocked."
                )
            _reject_scripts(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _reject_scripts(item, f"{path}[{i}]")


def _inject_org_filter(body: dict, organization_id: int) -> dict:
    """Inject organization_id filter into a DSL query body.

    Ensures every query is scoped to the current organization. Adds a
    `term` filter for `organization_id` to the top-level `bool.filter`.
    """
    org_filter = {"term": {"organization_id": organization_id}}

    if (query := body.get("query")) is None:
        body["query"] = {"bool": {"filter": [org_filter]}}
        return body

    if (bool_clause := query.get("bool")) is None:
        body["query"] = {"bool": {"must": [query], "filter": [org_filter]}}
        return body

    existing_filter = bool_clause.get("filter")
    if existing_filter is None:
        bool_clause["filter"] = [org_filter]
    elif isinstance(existing_filter, list):
        existing_filter.append(org_filter)
    elif isinstance(existing_filter, dict):
        bool_clause["filter"] = [existing_filter, org_filter]

    return body


@beta_tool
def search_elasticsearch(index: str, query: str | dict, size: int = 10) -> str:
    """Search Elasticsearch for datapoint statistics and annotation analytics.

    Goal: Answer questions about annotation data via aggregations, filters, and search.

    organization_id is injected automatically — never include it.
    Datapoint fields require nested queries on path "datapoints".
    Refer to the Elasticsearch skill for index schema and query patterns.

    Args:
        index: Index or alias (e.g., "elis_ann_alias_*").
        query: Query string ("status:exported") or Elasticsearch DSL body (dict or JSON string).
        size: Max hits (default 10). Use 0 for aggregation-only queries.

    Returns:
        JSON with hits and/or aggregations, or error message.
    """
    if "," in index:
        return json.dumps({"status": "error", "message": "Multiple index patterns are not allowed."})

    try:
        _validate_index(index)
    except ValueError as e:
        return json.dumps({"status": "error", "message": str(e)})

    if isinstance(query, dict):
        body = query
    else:
        try:
            body = json.loads(query)
        except (json.JSONDecodeError, TypeError):
            body = None

    try:
        organization_id, deployment_location = _get_org_info()
        client = _get_es_client(deployment_location)
        if isinstance(body, dict):
            if disallowed := set(body.keys()) - ALLOWED_BODY_KEYS:
                return json.dumps(
                    {
                        "status": "error",
                        "message": f"Disallowed keys in query body: {sorted(disallowed)}. "
                        f"Permitted keys: {sorted(ALLOWED_BODY_KEYS)}",
                    }
                )
            _validate_body_deep(body)
            if "size" not in body:
                body["size"] = size
            _inject_org_filter(body, organization_id)
            response = client.search(index=index, **body)
        else:
            # For query string searches, wrap in a DSL body with org filter
            body = {
                "size": size,
                "query": {
                    "bool": {
                        "must": [{"query_string": {"query": query}}],
                        "filter": [{"term": {"organization_id": organization_id}}],
                    }
                },
            }
            response = client.search(index=index, **body)  # ty: ignore[invalid-argument-type] - DSL body keys map to es.search kwargs

        result = _format_response(response.body)
        serialized = json.dumps(result)
        if len(serialized) > _OUTPUT_LIMIT:
            serialized = _truncate_output(serialized, _OUTPUT_LIMIT)
            return json.dumps({"status": "success", "result": serialized, "truncated": True})
        return json.dumps({"status": "success", "result": result})

    except Exception as e:
        logger.exception("Elasticsearch query failed")
        return json.dumps({"status": "error", "message": f"Elasticsearch query failed: {e}"})


def _format_response(response: dict) -> dict:
    """Extract relevant data from the raw Elasticsearch response."""
    result: dict = {}

    hits = response.get("hits", {})
    result["total"] = hits.get("total", {}).get("value", 0)

    hit_list = hits.get("hits", [])
    if hit_list:
        result["hits"] = [
            {"_id": h.get("_id"), "_source": h.get("_source"), "_score": h.get("_score")} for h in hit_list
        ]

    if aggs := response.get("aggregations"):
        result["aggregations"] = aggs

    return result
