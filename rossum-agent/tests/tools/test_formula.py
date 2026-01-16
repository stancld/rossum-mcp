"""Tests for the suggest_formula_field tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from rossum_agent.tools.formula import (
    _build_suggest_formula_url,
    _clean_html,
    _create_formula_field_definition,
    _find_field_in_schema,
    _inject_formula_field,
    suggest_formula_field,
)


class TestBuildSuggestFormulaUrl:
    """Tests for _build_suggest_formula_url."""

    def test_appends_internal_path(self) -> None:
        url = _build_suggest_formula_url("https://elis.rossum.ai/api/v1")
        assert url == "https://elis.rossum.ai/api/v1/internal/schemas/suggest_formula"

    def test_handles_trailing_slash(self) -> None:
        url = _build_suggest_formula_url("https://elis.rossum.ai/api/v1/")
        assert url == "https://elis.rossum.ai/api/v1/internal/schemas/suggest_formula"


class TestCleanHtml:
    """Tests for _clean_html."""

    def test_removes_span_tags(self) -> None:
        text = 'Calculates <span class="field">Due Date</span> minus <span class="field">Issue Date</span>'
        result = _clean_html(text)
        assert result == "Calculates Due Date minus Issue Date"

    def test_preserves_plain_text(self) -> None:
        text = "Simple text without HTML"
        assert _clean_html(text) == text


class TestFormulaFieldHelpers:
    """Tests for formula field helper functions."""

    def test_create_formula_field_definition(self) -> None:
        field = _create_formula_field_definition("Net Terms", "net_terms")
        assert field["id"] == "net_terms"
        assert field["label"] == "Net Terms"
        assert field["ui_configuration"] == {"type": "formula", "edit": "disabled"}
        assert field["disable_prediction"] is True
        assert field["formula"] == ""

    def test_create_formula_field_definition_derives_id(self) -> None:
        field = _create_formula_field_definition("Net Terms")
        assert field["id"] == "net_terms"
        assert field["label"] == "Net Terms"

    def test_find_field_in_schema_found(self) -> None:
        schema = [{"id": "section", "category": "section", "children": [{"id": "date_due"}]}]
        assert _find_field_in_schema(schema, "date_due") is True

    def test_find_field_in_schema_not_found(self) -> None:
        schema = [{"id": "section", "category": "section", "children": []}]
        assert _find_field_in_schema(schema, "net_terms") is False

    def test_inject_formula_field_adds_to_section(self) -> None:
        schema = [{"id": "basic_info", "category": "section", "children": []}]
        result = _inject_formula_field(schema, "Net Terms", "basic_info")
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["id"] == "net_terms"

    def test_inject_formula_field_skips_if_exists(self) -> None:
        schema = [{"id": "section", "category": "section", "children": [{"id": "net_terms"}]}]
        result = _inject_formula_field(schema, "Net Terms", "section")
        assert len(result[0]["children"]) == 1


class TestSuggestFormulaField:
    """Tests for suggest_formula_field tool."""

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.formula.httpx.Client")
    def test_successful_suggestion(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "formula": "('Net 15' if (field.date_due - field.date_issue).days <= 15 else 'Net 30')",
                    "name": "Payment Terms",
                    "summary": 'Calculates <span class="field">payment terms</span>',
                    "description": "Computes payment terms based on dates",
                    "type": "snippet",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = suggest_formula_field(
            label="Net Terms",
            hint="Compute payment terms based on due date and issue date",
            schema_content=[{"id": "basic_info", "category": "section", "children": []}],
            section_id="basic_info",
            field_schema_id="net_terms",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert "formula" in parsed
        assert parsed["summary"] == "Calculates payment terms"
        assert parsed["field_definition"]["id"] == "net_terms"
        assert parsed["field_definition"]["formula"] == parsed["formula"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.formula.httpx.Client")
    def test_no_suggestions(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = suggest_formula_field(
            label="Test",
            hint="test",
            schema_content=[],
            section_id="basic_info",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "no_suggestions"

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        result = suggest_formula_field(
            label="Test",
            hint="test",
            schema_content=[],
            section_id="basic_info",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "ROSSUM_API_BASE_URL" in parsed["error"]
