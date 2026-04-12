"""Tests for the suggest_formula_field tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.tools.core import AgentContext, set_context
from rossum_agent.tools.python_helpers.copilot.formula import (
    _build_suggest_formula_url,
    _clean_html,
    _create_formula_field_definition,
    suggest_formula_field,
)


class TestBuildSuggestFormulaUrl:
    """Tests for _build_suggest_formula_url."""

    @pytest.mark.parametrize(
        "base_url",
        ["https://elis.rossum.ai/api/v1", "https://elis.rossum.ai/api/v1/"],
        ids=["clean", "trailing_slash"],
    )
    def test_appends_internal_path(self, base_url: str) -> None:
        url = _build_suggest_formula_url(base_url)
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


class TestCreateFormulaFieldDefinition:
    def test_creates_with_explicit_id(self) -> None:
        field = _create_formula_field_definition("Net Terms", "net_terms")
        assert field["id"] == "net_terms"
        assert field["label"] == "Net Terms"
        assert field["ui_configuration"] == {"type": "formula", "edit": "disabled"}
        assert field["disable_prediction"] is False
        assert field["formula"] == ""

    def test_derives_id_from_label(self) -> None:
        field = _create_formula_field_definition("Net Terms")
        assert field["id"] == "net_terms"
        assert field["label"] == "Net Terms"

    def test_default_type_is_string(self) -> None:
        field = _create_formula_field_definition("Test")
        assert field["type"] == "string"

    @pytest.mark.parametrize(
        ("label", "field_type"),
        [("Amount", "number"), ("Due Date", "date")],
    )
    def test_respects_field_type(self, label: str, field_type: str) -> None:
        field = _create_formula_field_definition(label, field_type=field_type)
        assert field["type"] == field_type


class TestSuggestFormulaField:
    """Tests for suggest_formula_field tool."""

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.formula._fetch_schema_content")
    @patch("rossum_agent.tools.python_helpers.copilot.formula.httpx.Client")
    def test_successful_suggestion(self, mock_client_class: MagicMock, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [{"id": "basic_info", "category": "section", "children": []}]

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
            schema_id=123456,
            section_id="basic_info",
            field_schema_id="net_terms",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert "formula" in parsed
        assert parsed["summary"] == "Calculates payment terms"
        assert parsed["field_definition"]["id"] == "net_terms"
        assert parsed["field_definition"]["formula"] == parsed["formula"]
        assert parsed["field_definition"]["type"] == "string"
        mock_fetch.assert_called_once_with("https://api.rossum.ai/v1", "test_token", 123456)

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.formula._fetch_schema_content")
    @patch("rossum_agent.tools.python_helpers.copilot.formula.httpx.Client")
    def test_field_type_propagates_to_definition(self, mock_client_class: MagicMock, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [{"id": "basic_info", "category": "section", "children": []}]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"formula": "field.date_due - field.date_issue", "summary": "", "description": ""}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = suggest_formula_field(
            label="Net Terms",
            hint="days between dates",
            schema_id=123456,
            section_id="basic_info",
            field_type="number",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["field_definition"]["type"] == "number"

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.formula._fetch_schema_content")
    @patch("rossum_agent.tools.python_helpers.copilot.formula.httpx.Client")
    def test_no_suggestions(self, mock_client_class: MagicMock, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [{"id": "basic_info", "category": "section", "children": []}]

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
            schema_id=123456,
            section_id="basic_info",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "no_suggestions"

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        set_context(AgentContext())
        result = suggest_formula_field(
            label="Test",
            hint="test",
            schema_id=123456,
            section_id="basic_info",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "credentials not available" in parsed["error"]
