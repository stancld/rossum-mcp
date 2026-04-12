"""Formula field suggestion helpers for the Rossum Agent."""

from __future__ import annotations

import json
import logging
import re
from typing import Literal

import httpx

from rossum_agent.tools.core import get_context
from rossum_agent.tools.python_helpers.copilot._shared import (
    _fetch_schema_content,
    _handle_api_error,
    _inject_field_into_schema,
    _json_headers,
    _request_with_retry,
)

FormulaFieldType = Literal["string", "number", "date", "enum"]

logger = logging.getLogger(__name__)

_SUGGEST_FORMULA_TIMEOUT = 60


def _build_suggest_formula_url(api_base_url: str) -> str:
    return f"{api_base_url.rstrip('/')}/internal/schemas/suggest_formula"


def _create_formula_field_definition(
    label: str,
    field_schema_id: str | None = None,
    field_type: FormulaFieldType = "string",
) -> dict:
    if not field_schema_id:
        field_schema_id = label.lower().replace(" ", "_")
    return {
        "id": field_schema_id,
        "label": label,
        "type": field_type,
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


def suggest_formula_field(
    label: str,
    hint: str,
    schema_id: int,
    section_id: str,
    field_schema_id: str | None = None,
    field_type: FormulaFieldType = "string",
) -> str:
    """Get AI-generated formula suggestions for a new formula field.

    Args:
        label: Display label for the field (e.g., 'Net Terms').
        hint: Natural language description of the formula logic.
        schema_id: The numeric schema ID (e.g., 9389721). Get this from get(entity="queue", id=queue_id) or search(query={"entity": "queue"}).
        section_id: Section ID where the field belongs. Ask the user if not specified.
        field_schema_id: Optional ID for the formula field. Defaults to label.lower().replace(" ", "_").
        field_type: Schema field type for the formula field (string, number, date, enum). Defaults to string.

    Returns:
        JSON with formula suggestion and field_definition for use with patch_schema.
    """
    field_schema_id = field_schema_id or label.lower().replace(" ", "_")
    logger.info(f"suggest_formula_field: {field_schema_id=}, {schema_id=}, {section_id=}, hint={hint[:100]}...")

    try:
        api_base_url, token = get_context().require_rossum_credentials()
        url = _build_suggest_formula_url(api_base_url)

        schema_content = _fetch_schema_content(api_base_url, token, schema_id)
        field_def = _create_formula_field_definition(label, field_schema_id, field_type)
        enriched_schema = _inject_field_into_schema(schema_content, field_def, section_id)

        payload = {"field_schema_id": field_schema_id, "hint": hint, "schema_content": enriched_schema}

        with httpx.Client(timeout=_SUGGEST_FORMULA_TIMEOUT) as client:
            response = _request_with_retry(client, "post", url, json=payload, headers=_json_headers(token))
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

        # Reuse field_def from above instead of creating a duplicate
        field_def["formula"] = formula

        return json.dumps(
            {
                "status": "success",
                "formula": formula,
                "field_definition": field_def,
                "section_id": section_id,
                "summary": summary,
                "description": _clean_html(top_suggestion.get("description", "")),
            }
        )

    except Exception as e:
        return _handle_api_error(e, "suggest_formula_field")


def _clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)
