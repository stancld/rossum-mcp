"""Automation setup helpers for the Rossum Agent.

This module provides functions to retrieve automation statistics, run projections,
and manage automation targets for document processing queues via the Rossum API.
"""

from __future__ import annotations

import json
import logging

import httpx

from rossum_agent.python_tools.copilot._shared import _json_headers
from rossum_agent.tools.core import get_context

logger = logging.getLogger(__name__)

_AUTOMATION_SETUP_TIMEOUT = 60


def _build_current_stats_url(api_base_url: str, queue_id: int) -> str:
    return f"{api_base_url.rstrip('/')}/queues/{queue_id}/automation_setup_current_stats"


def _build_projections_url(api_base_url: str, queue_id: int) -> str:
    return f"{api_base_url.rstrip('/')}/queues/{queue_id}/automation_setup_projections"


def _build_automation_targets_url(api_base_url: str, queue_id: int) -> str:
    return f"{api_base_url.rstrip('/')}/queues/{queue_id}/automation_targets"


def get_automation_current_stats(queue_id: int) -> str:
    """Get current automation statistics for a queue.

    Args:
        queue_id: The numeric queue ID.

    Returns:
        JSON with estimated_error_rate, document_automation_rate, document_touchless_rate,
        document_blockers, datapoint_statistics, and timeseries data.
    """
    logger.info(f"get_automation_current_stats: {queue_id=}")

    try:
        api_base_url, token = get_context().require_rossum_credentials()
        url = _build_current_stats_url(api_base_url, queue_id)

        with httpx.Client(timeout=_AUTOMATION_SETUP_TIMEOUT) as client:
            response = client.get(url, headers=_json_headers(token))
            response.raise_for_status()
            result = response.json()

        return json.dumps({"status": "success", **result})

    except httpx.HTTPStatusError as e:
        logger.exception("HTTP error in get_automation_current_stats")
        return json.dumps({"status": "error", "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}"})
    except Exception as e:
        logger.exception("Error in get_automation_current_stats")
        return json.dumps({"status": "error", "error": str(e)})


def get_automation_projections(
    queue_id: int,
    fields: list[dict],
    exclude_blockers: list[str] | None = None,
) -> str:
    """Project automation stats for a queue given per-field error rate limits.

    Args:
        queue_id: The numeric queue ID.
        fields: List of dicts with schema_id (str) and error_rate_limit (float 0.0-1.0).
        exclude_blockers: Optional list of blocker types to exclude (e.g. ["error_message", "extension"]).

    Returns:
        JSON with total_document_count, used_document_count, baseline (current state),
        and projections (projected state after applying the error rate limits).
    """
    logger.info(f"get_automation_projections: {queue_id=}, fields={len(fields)}")

    try:
        api_base_url, token = get_context().require_rossum_credentials()
        url = _build_projections_url(api_base_url, queue_id)

        params = {}
        if exclude_blockers:
            params["exclude_blockers"] = ",".join(exclude_blockers)

        with httpx.Client(timeout=_AUTOMATION_SETUP_TIMEOUT) as client:
            response = client.post(
                url,
                json={"fields": fields},
                headers=_json_headers(token),
                params=params or None,
            )
            response.raise_for_status()
            result = response.json()

        return json.dumps({"status": "success", **result})

    except httpx.HTTPStatusError as e:
        logger.exception("HTTP error in get_automation_projections")
        return json.dumps({"status": "error", "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}"})
    except Exception as e:
        logger.exception("Error in get_automation_projections")
        return json.dumps({"status": "error", "error": str(e)})


def list_automation_targets(queue_id: int) -> str:
    """List saved automation targets for a queue.

    Args:
        queue_id: The numeric queue ID.

    Returns:
        JSON with results list of automation target snapshots.
    """
    logger.info(f"list_automation_targets: {queue_id=}")

    try:
        api_base_url, token = get_context().require_rossum_credentials()
        url = _build_automation_targets_url(api_base_url, queue_id)

        with httpx.Client(timeout=_AUTOMATION_SETUP_TIMEOUT) as client:
            response = client.get(url, headers=_json_headers(token))
            response.raise_for_status()
            result = response.json()

        return json.dumps({"status": "success", **result})

    except httpx.HTTPStatusError as e:
        logger.exception("HTTP error in list_automation_targets")
        return json.dumps({"status": "error", "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}"})
    except Exception as e:
        logger.exception("Error in list_automation_targets")
        return json.dumps({"status": "error", "error": str(e)})


def save_automation_target(
    queue_id: int,
    automation_rate_target: float,
    error_rate_target: float,
    datapoint_automation_targets: list[dict],
    target_type: str = "automation_assistant_v1",
) -> str:
    """Save an automation target for a queue.

    Args:
        queue_id: The numeric queue ID.
        automation_rate_target: Target automation rate (0.0-1.0).
        error_rate_target: Target error rate (0.0-1.0).
        datapoint_automation_targets: List of per-field targets, each with
            schema_id (str), error_rate_target (float), confidence_threshold (float),
            and optionally error_rate_limit (float).
        target_type: Target type — "automation_assistant_v1" or "legacy_thresholds".

    Returns:
        JSON with the saved automation target including datetime.
    """
    logger.info(f"save_automation_target: {queue_id=}, {target_type=}")

    ctx = get_context()
    if ctx.is_read_only:
        return json.dumps({"status": "error", "error": "save_automation_target requires read-write mode"})

    try:
        api_base_url, token = ctx.require_rossum_credentials()
        url = _build_automation_targets_url(api_base_url, queue_id)

        payload = {
            "automation_rate_target": automation_rate_target,
            "error_rate_target": error_rate_target,
            "datapoint_automation_targets": datapoint_automation_targets,
            "type": target_type,
        }

        with httpx.Client(timeout=_AUTOMATION_SETUP_TIMEOUT) as client:
            response = client.post(url, json=payload, headers=_json_headers(token))
            response.raise_for_status()
            result = response.json()

        return json.dumps({"status": "success", **result})

    except httpx.HTTPStatusError as e:
        logger.exception("HTTP error in save_automation_target")
        return json.dumps({"status": "error", "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}"})
    except Exception as e:
        logger.exception("Error in save_automation_target")
        return json.dumps({"status": "error", "error": str(e)})
