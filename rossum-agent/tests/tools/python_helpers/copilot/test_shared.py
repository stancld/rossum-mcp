"""Tests for copilot shared helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rossum_agent.tools.python_helpers.copilot._shared import (
    _fetch_schema_content,
    _find_field_in_schema,
    _inject_field_into_schema,
    _json_headers,
)


class TestJsonHeaders:
    def test_returns_auth_and_content_type(self) -> None:
        headers = _json_headers("my_token")
        assert headers == {"Authorization": "Bearer my_token", "Content-Type": "application/json"}


class TestFetchSchemaContent:
    @patch("rossum_agent.tools.python_helpers.copilot._shared.httpx.Client")
    def test_fetches_schema_content(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"id": "section", "category": "section", "children": []}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = _fetch_schema_content("https://api.rossum.ai/v1", "test_token", 123456)

        assert result == [{"id": "section", "category": "section", "children": []}]
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "schemas/123456" in call_args[0][0]


class TestFindFieldInSchema:
    def test_found(self) -> None:
        schema = [{"id": "section", "category": "section", "children": [{"id": "date_due"}]}]
        assert _find_field_in_schema(schema, "date_due") is True

    def test_not_found(self) -> None:
        schema = [{"id": "section", "category": "section", "children": []}]
        assert _find_field_in_schema(schema, "net_terms") is False

    def test_children_as_dict(self) -> None:
        schema = [{"id": "section", "category": "section", "children": {"id": "nested_field"}}]
        assert _find_field_in_schema(schema, "nested_field") is True

    def test_deeply_nested(self) -> None:
        schema = [
            {
                "id": "section",
                "category": "section",
                "children": [{"id": "subsection", "children": [{"id": "deep_field"}]}],
            }
        ]
        assert _find_field_in_schema(schema, "deep_field") is True


class TestInjectFieldIntoSchema:
    def _make_field(self, field_id: str = "new_field", label: str = "New Field") -> dict:
        return {"id": field_id, "label": label, "type": "string", "category": "datapoint"}

    def test_adds_to_section(self) -> None:
        schema = [{"id": "basic_info", "category": "section", "children": []}]
        result = _inject_field_into_schema(schema, self._make_field(), "basic_info")
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["id"] == "new_field"

    def test_skips_if_exists(self) -> None:
        schema = [{"id": "section", "category": "section", "children": [{"id": "new_field"}]}]
        result = _inject_field_into_schema(schema, self._make_field(), "section")
        assert len(result[0]["children"]) == 1

    def test_fallback_to_first_section(self) -> None:
        schema = [{"id": "other_section", "category": "section", "children": []}]
        result = _inject_field_into_schema(schema, self._make_field(), "nonexistent_section")
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["id"] == "new_field"

    def test_fallback_to_root_when_no_sections(self) -> None:
        schema = [{"id": "datapoint", "category": "datapoint"}]
        result = _inject_field_into_schema(schema, self._make_field(), "nonexistent")
        assert len(result) == 2
        assert result[1]["id"] == "new_field"

    def test_with_custom_field_id(self) -> None:
        schema = [{"id": "section", "category": "section", "children": []}]
        result = _inject_field_into_schema(schema, self._make_field("custom_id", "Custom"), "section")
        assert result[0]["children"][0]["id"] == "custom_id"
        assert result[0]["children"][0]["label"] == "Custom"

    def test_does_not_modify_original(self) -> None:
        schema = [{"id": "section", "category": "section", "children": []}]
        _inject_field_into_schema(schema, self._make_field(), "section")
        assert len(schema[0]["children"]) == 0

    def test_returns_original_when_no_field_id(self) -> None:
        schema = [{"id": "section", "category": "section", "children": []}]
        result = _inject_field_into_schema(schema, {"type": "string"}, "section")
        assert result is schema
