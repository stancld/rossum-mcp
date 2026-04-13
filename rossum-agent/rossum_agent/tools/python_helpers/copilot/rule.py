"""Rule suggestion helpers for the Rossum Agent."""

from __future__ import annotations

import json

import httpx
import structlog

from rossum_agent.tools.core import get_context
from rossum_agent.tools.python_helpers.copilot._shared import _handle_api_error, _json_headers, _request_with_retry

logger = structlog.get_logger(__name__)

_SUGGEST_RULE_TIMEOUT = 60


def _build_suggest_rule_url(api_base_url: str) -> str:
    return f"{api_base_url.rstrip('/')}/internal/rules/suggest_rule"


def _build_evaluate_rules_url(api_base_url: str) -> str:
    return f"{api_base_url.rstrip('/')}/internal/rules/evaluate_rules"


def _build_queue_url(api_base_url: str, queue_id: int) -> str:
    return f"{api_base_url.rstrip('/')}/queues/{queue_id}"


def _build_annotation_url(api_base_url: str, annotation_id: int) -> str:
    return f"{api_base_url.rstrip('/')}/annotations/{annotation_id}"


def _build_annotation_content_url(api_base_url: str, annotation_id: int) -> str:
    return f"{api_base_url.rstrip('/')}/annotations/{annotation_id}/content"


def suggest_rule(user_query: str, queue_id: int) -> str:
    """Get an AI-generated rule suggestion (trigger condition + actions) from a natural language description.

    Args:
        user_query: Natural language description of the desired rule behavior.
        queue_id: The numeric queue ID (e.g., 2519495). Get this from search(query={"entity": "queue"}).

    Returns:
        JSON with the suggested rule (name, trigger_condition, actions) ready for create_rule.
    """
    logger.info(f"suggest_rule: {queue_id=}, query={user_query[:100]}...")

    try:
        api_base_url, token = get_context().require_rossum_credentials()
        queue_url = _build_queue_url(api_base_url, queue_id)
        payload = {"queue": queue_url, "user_query": user_query}

        with httpx.Client(timeout=_SUGGEST_RULE_TIMEOUT) as client:
            response = _request_with_retry(
                client,
                "post",
                _build_suggest_rule_url(api_base_url),
                json=payload,
                headers=_json_headers(token),
            )
            result = response.json()

        suggestions = result.get("results", [])
        if not suggestions:
            return json.dumps(
                {"status": "no_suggestions", "message": "No rule suggestions returned. Try rephrasing the query."}
            )

        top = suggestions[0]
        return json.dumps(
            {
                "status": "success",
                "name": top.get("name", ""),
                "trigger_condition": top.get("trigger_condition", ""),
                "trigger_condition_summary": top.get("trigger_condition_summary", ""),
                "actions": top.get("actions", []),
                "enabled": top.get("enabled", True),
            }
        )

    except Exception as e:
        return _handle_api_error(e, "suggest_rule")


def evaluate_rules(queue_id: int, annotation_id: int, schema_rules: list[dict]) -> str:
    """Test rules against a real document annotation to preview triggered messages and actions.

    Args:
        queue_id: The numeric queue ID.
        annotation_id: The numeric annotation ID (a document in the queue).
        schema_rules: List of rule dicts from suggest_rule (name, trigger_condition, actions, enabled).

    Returns:
        JSON with condition_values (per-rule bool), triggered actions, and messages.
    """
    logger.info(f"evaluate_rules: {queue_id=}, {annotation_id=}, rules={len(schema_rules)}")

    try:
        api_base_url, token = get_context().require_rossum_credentials()
        headers = _json_headers(token)

        with httpx.Client(timeout=_SUGGEST_RULE_TIMEOUT) as client:
            content_response = _request_with_retry(
                client,
                "get",
                _build_annotation_content_url(api_base_url, annotation_id),
                headers=headers,
            )
            content_data = content_response.json()
            annotation_content = (
                content_data.get("results", content_data) if isinstance(content_data, dict) else content_data
            )

            payload = {
                "queue": _build_queue_url(api_base_url, queue_id),
                "annotation": _build_annotation_url(api_base_url, annotation_id),
                "annotation_content": annotation_content,
                "schema_rules": schema_rules,
            }
            eval_response = _request_with_retry(
                client,
                "post",
                _build_evaluate_rules_url(api_base_url),
                json=payload,
                headers=headers,
            )
            result = eval_response.json()

        return json.dumps({"status": "success", **result})

    except Exception as e:
        return _handle_api_error(e, "evaluate_rules")
