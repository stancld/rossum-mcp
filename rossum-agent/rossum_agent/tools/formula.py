"""Formula field suggestion tool for the Rossum Agent.

This module provides a tool to get formula suggestions from Rossum's internal API
for formula fields based on natural language descriptions.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re

import httpx
from anthropic import beta_tool

logger = logging.getLogger(__name__)

_SUGGEST_FORMULA_TIMEOUT = 60


def _get_credentials() -> tuple[str, str]:
    """Get Rossum API credentials from environment.

    Returns:
        Tuple of (api_base_url, api_token).
    """
    if not (api_base := os.getenv("ROSSUM_API_BASE_URL")):
        raise ValueError("ROSSUM_API_BASE_URL environment variable is required")
    if not (token := os.getenv("ROSSUM_API_TOKEN")):
        raise ValueError("ROSSUM_API_TOKEN environment variable is required")

    return api_base, token


def _build_suggest_formula_url(api_base_url: str) -> str:
    """Build the suggest_formula endpoint URL.

    Uses the base URL directly (e.g., https://elis.rossum.ai/api/v1)
    and appends the internal endpoint path.
    """
    return f"{api_base_url.rstrip('/')}/internal/schemas/suggest_formula"


def _fetch_schema_content(api_base_url: str, token: str, schema_id: int) -> list[dict]:
    """Fetch schema content from Rossum API."""
    url = f"{api_base_url.rstrip('/')}/schemas/{schema_id}"
    with httpx.Client(timeout=30) as client:
        response = client.get(url, headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
        return response.json()["content"]


def _create_formula_field_definition(label: str, field_schema_id: str | None = None) -> dict:
    """Create a properly structured formula field definition."""
    if not field_schema_id:
        field_schema_id = label.lower().replace(" ", "_")
    return {
        "id": field_schema_id,
        "label": label,
        "type": "string",
        "category": "datapoint",
        "can_export": True,
        "constraints": {"required": False},
        "disable_prediction": False,
        "formula": "",
        "hidden": False,
        "rir_field_names": [],
        "score_threshold": 0,
        "suggest": True,
        "ui_configuration": {"type": "formula", "edit": "disabled"},
    }


def _find_field_in_schema(nodes: list[dict], field_id: str) -> bool:
    """Recursively search for a field ID in schema content."""
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


def _inject_formula_field(
    schema_content: list[dict], label: str, section_id: str, field_schema_id: str | None = None
) -> list[dict]:
    """Inject a formula field into the specified section of schema_content.

    The suggest_formula API requires the target field to exist in schema_content.
    """
    if not field_schema_id:
        field_schema_id = label.lower().replace(" ", "_")

    if _find_field_in_schema(schema_content, field_schema_id):
        return schema_content

    modified = copy.deepcopy(schema_content)
    formula_field = _create_formula_field_definition(label, field_schema_id)

    for section in modified:
        if section.get("id") == section_id and section.get("category") == "section":
            section.setdefault("children", []).append(formula_field)
            return modified

    if modified and modified[0].get("category") == "section":
        modified[0].setdefault("children", []).append(formula_field)
    else:
        modified.append(formula_field)

    return modified


@beta_tool
def suggest_formula_field(
    label: str, hint: str, schema_id: int, section_id: str, field_schema_id: str | None = None
) -> str:
    """Get AI-generated formula suggestions for a new formula field.

    Args:
        label: Display label for the field (e.g., 'Net Terms').
        hint: Natural language description of the formula logic.
        schema_id: The numeric schema ID (e.g., 9389721). Get this from get_schema or list_queues.
        section_id: Section ID where the field belongs. Ask the user if not specified.
        field_schema_id: Optional ID for the formula field. Defaults to label.lower().replace(" ", "_").

    Returns:
        JSON with formula suggestion and field_definition for use with patch_schema.
    """
    if not field_schema_id:
        field_schema_id = label.lower().replace(" ", "_")

    logger.info(f"suggest_formula_field: {field_schema_id=}, {schema_id=}, {section_id=}, hint={hint[:100]}...")

    try:
        api_base_url, token = _get_credentials()
        url = _build_suggest_formula_url(api_base_url)

        schema_content = _fetch_schema_content(api_base_url, token, schema_id)
        enriched_schema = _inject_formula_field(schema_content, label, section_id, field_schema_id)

        payload = {"field_schema_id": field_schema_id, "hint": hint, "schema_content": enriched_schema}

        logger.debug(f"Calling suggest_formula API: {url}")
        logger.debug(f"suggest_formula payload: {json.dumps(payload, indent=2)}")

        with httpx.Client(timeout=_SUGGEST_FORMULA_TIMEOUT) as client:
            response = client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

        suggestions = result.get("results", [])
        if not suggestions:
            return json.dumps(
                {"status": "no_suggestions", "message": "No formula suggestions returned. Try rephrasing the hint."}
            )

        top_suggestion = suggestions[0]
        formula = top_suggestion.get("formula", "")
        summary = top_suggestion.get("summary", "")
        if summary:
            summary = _clean_html(summary)

        field_definition = _create_formula_field_definition(label, field_schema_id)
        field_definition["formula"] = formula

        return json.dumps(
            {
                "status": "success",
                "formula": formula,
                "field_definition": field_definition,
                "section_id": section_id,
                "summary": summary,
                "description": _clean_html(top_suggestion.get("description", "")),
            }
        )

    except httpx.HTTPStatusError as e:
        logger.exception("HTTP error in suggest_formula_field")
        return json.dumps(
            {
                "status": "error",
                "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}",
            }
        )
    except Exception as e:
        logger.exception("Error in suggest_formula_field")
        return json.dumps({"status": "error", "error": str(e)})


def _clean_html(text: str) -> str:
    """Remove HTML tags from text (simple cleanup for display)."""
    return re.sub(r"<[^>]+>", "", text)
