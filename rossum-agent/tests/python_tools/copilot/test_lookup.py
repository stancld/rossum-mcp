"""Tests for the lookup field suggestion and evaluation tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from typing import ClassVar

import httpx
from rossum_agent.python_tools.copilot.lookup import (
    _build_evaluate_computed_fields_url,
    _build_mdh_aggregate_url,
    _build_mdh_datasets_url,
    _build_suggest_computed_field_url,
    _cache_dataset,
    _collect_datapoint_values,
    _create_lookup_field_definition,
    _dataset_cache,
    _extract_lookup_results,
    _fetch_annotation_content,
    _field_definition_cache,
    _find_lookup_field_ids,
    _get_placeholder_field_ids,
    _request_with_retry,
    _resolve_mdh_dataset_identifier,
    _update_or_inject_field,
    evaluate_lookup_field,
    get_lookup_dataset_raw_values,
    query_lookup_dataset,
    suggest_lookup_field,
)
from rossum_agent.tools.core import AgentContext, set_context


class TestBuildSuggestComputedFieldUrl:
    def test_appends_internal_path(self) -> None:
        url = _build_suggest_computed_field_url("https://elis.rossum.ai/api/v1")
        assert url == "https://elis.rossum.ai/api/v1/internal/schemas/suggest_computed_field"

    def test_handles_trailing_slash(self) -> None:
        url = _build_suggest_computed_field_url("https://elis.rossum.ai/api/v1/")
        assert url == "https://elis.rossum.ai/api/v1/internal/schemas/suggest_computed_field"


class TestBuildEvaluateComputedFieldsUrl:
    def test_appends_internal_path(self) -> None:
        url = _build_evaluate_computed_fields_url("https://elis.rossum.ai/api/v1")
        assert url == "https://elis.rossum.ai/api/v1/internal/schemas/evaluate_computed_fields"

    def test_handles_trailing_slash(self) -> None:
        url = _build_evaluate_computed_fields_url("https://elis.rossum.ai/api/v1/")
        assert url == "https://elis.rossum.ai/api/v1/internal/schemas/evaluate_computed_fields"


class TestBuildMdhDatasetsUrl:
    def test_appends_mdh_datasets_path(self) -> None:
        url = _build_mdh_datasets_url("https://elis.rossum.ai/api/v1")
        assert url == "https://elis.rossum.ai/svc/master-data-hub/api/v2/datasets?limit=1000"

    def test_handles_trailing_slash(self) -> None:
        url = _build_mdh_datasets_url("https://elis.rossum.ai/api/v1/")
        assert url == "https://elis.rossum.ai/svc/master-data-hub/api/v2/datasets?limit=1000"


class TestBuildMdhAggregateUrl:
    def test_appends_mdh_aggregate_path(self) -> None:
        url = _build_mdh_aggregate_url("https://elis.rossum.ai/api/v1")
        assert url == "https://elis.rossum.ai/svc/master-data-hub/api/v1/data/aggregate"

    def test_handles_trailing_slash(self) -> None:
        url = _build_mdh_aggregate_url("https://elis.rossum.ai/api/v1/")
        assert url == "https://elis.rossum.ai/svc/master-data-hub/api/v1/data/aggregate"


class TestResolveMdhDatasetIdentifier:
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_resolves_dataset_name_to_identifier(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b", "name": "approved-vendors"}
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        resolved = _resolve_mdh_dataset_identifier("https://example.rossum.app/api/v1", "token", "approved-vendors")

        assert resolved == "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b"

    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_resolves_when_id_is_not_imported_but_dataset_id_is(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "66f6f8b3f1a0f90f",
                "dataset_id": "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b",
                "name": "Vendors",
            }
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        resolved = _resolve_mdh_dataset_identifier("https://example.rossum.app/api/v1", "token", "Vendors")

        assert resolved == "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b"

    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_returns_none_when_not_found(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "imported-aaa", "name": "other-dataset"}]
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        resolved = _resolve_mdh_dataset_identifier("https://example.rossum.app/api/v1", "token", "approved-vendors")

        assert resolved is None

    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_keeps_imported_identifier_unchanged(self, mock_client_class: MagicMock) -> None:
        resolved = _resolve_mdh_dataset_identifier(
            "https://example.rossum.app/api/v1",
            "token",
            "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b",
        )

        assert resolved == "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b"
        mock_client_class.assert_not_called()

    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_matches_dataset_aliases_with_different_spacing(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b", "name": "approved-vendors"}
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        resolved = _resolve_mdh_dataset_identifier("https://example.rossum.app/api/v1", "token", "Approved vendors")

        assert resolved == "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b"

    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_reads_dataset_items_from_wrapped_results_payload(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"id": "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b", "name": "approved-vendors"}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        resolved = _resolve_mdh_dataset_identifier("https://example.rossum.app/api/v1", "token", "approved-vendors")

        assert resolved == "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b"

    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_matches_metadata_name_from_wrapped_results_payload(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "69947f328c0baeb1026f8ad7",
                    "name": "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b",
                    "metadata": {"name": "Approved vendors"},
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        resolved = _resolve_mdh_dataset_identifier("https://example.rossum.app/api/v1", "token", "Approved vendors")

        assert resolved == "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b"


class TestRequestWithRetry:
    def test_returns_on_success(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        result = _request_with_retry(mock_client, "get", "https://example.com/api")

        assert result is mock_response
        mock_client.get.assert_called_once()
        mock_response.raise_for_status.assert_called_once()

    @patch("rossum_agent.python_tools.copilot.lookup.time.sleep")
    def test_retries_on_429(self, mock_sleep: MagicMock) -> None:
        rate_limited = MagicMock()
        rate_limited.status_code = 429

        success = MagicMock()
        success.status_code = 200

        mock_client = MagicMock()
        mock_client.post.side_effect = [rate_limited, success]

        result = _request_with_retry(mock_client, "post", "https://example.com/api", json={"key": "val"})

        assert result is success
        assert mock_client.post.call_count == 2
        mock_sleep.assert_called_once_with(2.0)

    @patch("rossum_agent.python_tools.copilot.lookup.time.sleep")
    def test_exponential_backoff(self, mock_sleep: MagicMock) -> None:
        rate_limited = MagicMock()
        rate_limited.status_code = 429

        success = MagicMock()
        success.status_code = 200

        mock_client = MagicMock()
        mock_client.get.side_effect = [rate_limited, rate_limited, rate_limited, success]

        result = _request_with_retry(mock_client, "get", "https://example.com/api")

        assert result is success
        assert mock_client.get.call_count == 4
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(2.0)
        mock_sleep.assert_any_call(4.0)
        mock_sleep.assert_any_call(8.0)

    def test_raises_non_429_errors(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        import pytest

        with pytest.raises(httpx.HTTPStatusError):
            _request_with_retry(mock_client, "get", "https://example.com/api")

        mock_client.get.assert_called_once()


class TestFetchAnnotationContent:
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_strips_api_v1_prefix_from_relative_url(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"id": "section"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        _fetch_annotation_content("https://example.rossum.app/api/v1", "token", "/api/v1/annotations/123")

        mock_client.get.assert_called_once_with(
            "https://example.rossum.app/api/v1/annotations/123/content",
            headers={"Authorization": "Bearer token"},
        )

    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_uses_absolute_url_as_is(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        _fetch_annotation_content(
            "https://example.rossum.app/api/v1", "token", "https://other.app/api/v1/annotations/456"
        )

        mock_client.get.assert_called_once_with(
            "https://other.app/api/v1/annotations/456/content",
            headers={"Authorization": "Bearer token"},
        )


class TestCreateLookupFieldDefinition:
    def test_creates_with_explicit_id(self) -> None:
        field = _create_lookup_field_definition("Vendor Match", "vendor_match")
        assert field["id"] == "vendor_match"
        assert field["label"] == "Vendor Match"
        assert field["type"] == "enum"
        assert field["ui_configuration"] == {"type": "lookup", "edit": "disabled"}
        assert field["matching"] == {"type": "master_data_hub", "configuration": {}}
        assert field["enum_value_type"] == "string"

    def test_derives_id_from_label(self) -> None:
        field = _create_lookup_field_definition("Vendor Match")
        assert field["id"] == "vendor_match"
        assert field["label"] == "Vendor Match"


class TestUpdateOrInjectField:
    def test_replaces_existing_field(self) -> None:
        schema = [
            {
                "id": "section",
                "category": "section",
                "children": [{"id": "vendor_match", "type": "string", "matching": {}}],
            }
        ]
        new_def = {"id": "vendor_match", "type": "enum", "matching": {"type": "master_data_hub"}}
        result = _update_or_inject_field(schema, new_def)
        assert result[0]["children"][0]["type"] == "enum"
        assert result[0]["children"][0]["matching"] == {"type": "master_data_hub"}

    def test_replaces_nested_field(self) -> None:
        schema = [
            {
                "id": "section",
                "category": "section",
                "children": [
                    {"id": "other_field", "type": "string"},
                    {"id": "vendor_match", "type": "string"},
                ],
            }
        ]
        new_def = {"id": "vendor_match", "type": "enum"}
        result = _update_or_inject_field(schema, new_def)
        assert result[0]["children"][1]["type"] == "enum"
        assert result[0]["children"][0]["type"] == "string"

    def test_injects_into_first_section_when_not_found(self) -> None:
        schema = [{"id": "section", "category": "section", "children": [{"id": "other", "type": "string"}]}]
        new_def = {"id": "new_lookup", "type": "enum"}
        result = _update_or_inject_field(schema, new_def)
        assert len(result[0]["children"]) == 2
        assert result[0]["children"][-1]["id"] == "new_lookup"

    def test_appends_to_root_when_no_sections(self) -> None:
        schema = [{"id": "datapoint", "category": "datapoint"}]
        new_def = {"id": "new_lookup", "type": "enum"}
        result = _update_or_inject_field(schema, new_def)
        assert len(result) == 2
        assert result[1]["id"] == "new_lookup"

    def test_returns_original_when_field_id_missing(self) -> None:
        schema = [{"id": "section", "category": "section", "children": []}]
        result = _update_or_inject_field(schema, {"type": "enum"})
        assert result is schema

    def test_does_not_modify_original(self) -> None:
        schema = [{"id": "section", "category": "section", "children": [{"id": "vendor_match", "type": "string"}]}]
        _update_or_inject_field(schema, {"id": "vendor_match", "type": "enum"})
        assert schema[0]["children"][0]["type"] == "string"


class TestSuggestLookupField:
    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_dataset_appended_to_hint(self, mock_client_class: MagicMock, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [{"id": "section", "category": "section", "children": []}]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"matching": {"type": "master_data_hub", "configuration": {"dataset": "Vendors"}}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        suggest_lookup_field(
            label="Test",
            hint="Match by VAT",
            schema_id=12345,
            section_id="section",
            dataset="Vendors",
        )

        call_payload = mock_client.post.call_args[1]["json"]
        assert call_payload["hint"] == "Match by VAT (dataset: Vendors)"

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_successful_suggestion(self, mock_client_class: MagicMock, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [{"id": "vendor_section", "category": "section", "children": []}]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "matching": {
                        "type": "master_data_hub",
                        "configuration": {
                            "dataset": "Vendors",
                            "queries": '[{"//": "Exact match", "aggregate": []}]',
                            "placeholders": {"sender_vat": {"__formula": "field.sender_vat_id"}},
                        },
                    },
                    "ui_configuration": {"type": "lookup", "edit": "disabled"},
                    "type": "enum",
                    "options": [],
                    "enum_value_type": "string",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = suggest_lookup_field(
            label="Vendor Match",
            hint="Match vendors by VAT ID from the Vendors dataset",
            schema_id=12345,
            section_id="vendor_section",
            field_schema_id="vendor_match",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["field_schema_id"] == "vendor_match"
        assert parsed["matching"]["type"] == "master_data_hub"
        assert "placeholders" in parsed["matching"]["configuration"]
        assert "field_definition" not in parsed
        assert parsed["section_id"] == "vendor_section"
        assert parsed["dataset"] == "Vendors"
        mock_fetch.assert_called_once_with("https://api.rossum.ai/v1", "test_token", 12345)

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_no_suggestions(self, mock_client_class: MagicMock, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [{"id": "section", "category": "section", "children": []}]

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = suggest_lookup_field(
            label="Test",
            hint="test",
            schema_id=12345,
            section_id="section",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "no_suggestions"

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        set_context(AgentContext())
        result = suggest_lookup_field(
            label="Test",
            hint="test",
            schema_id=12345,
            section_id="section",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "credentials not available" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_dataset_in_top_level_response(self, mock_client_class: MagicMock, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [{"id": "section", "category": "section", "children": []}]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "matching": {
                        "type": "master_data_hub",
                        "configuration": {
                            "dataset": "imported-0d652b68-vendors",
                            "queries": '[{"//": "Match", "aggregate": []}]',
                        },
                    },
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = suggest_lookup_field(
            label="Vendor Match",
            hint="Match vendors",
            schema_id=12345,
            section_id="section",
            field_schema_id="vendor_match",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["dataset"] == "imported-0d652b68-vendors"

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_dataset_prepopulated_in_stub(self, mock_client_class: MagicMock, mock_fetch: MagicMock) -> None:
        """When dataset is provided, it's set in the stub so the backend shows it as 'Preselected dataset'."""
        mock_fetch.return_value = [{"id": "section", "category": "section", "children": []}]

        mock_metadata_response = MagicMock()
        mock_metadata_response.json.return_value = [
            {"id": "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b", "name": "approved-vendors"}
        ]
        mock_metadata_response.raise_for_status = MagicMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "matching": {
                        "type": "master_data_hub",
                        "configuration": {
                            "dataset": "imported-0d652b68-vendors",
                            "queries": '[{"//": "Match", "aggregate": []}]',
                        },
                    },
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_metadata_response
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = suggest_lookup_field(
            label="Vendor Match",
            hint="Match vendors",
            schema_id=12345,
            section_id="section",
            field_schema_id="vendor_match",
            dataset="approved-vendors",
        )

        # Verify dataset was set in the stub sent to the API
        call_payload = mock_client.post.call_args[1]["json"]
        stub_field = call_payload["schema_content"][0]["children"][0]
        assert stub_field["matching"]["configuration"]["dataset"] == "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b"

        # The returned dataset should be whatever the suggest API resolved (not the user-provided name)
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["dataset"] == "imported-0d652b68-vendors"

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_dataset_none_when_missing_from_config(self, mock_client_class: MagicMock, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [{"id": "section", "category": "section", "children": []}]

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"matching": {"type": "simple_lookup", "configuration": {}}}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = suggest_lookup_field(
            label="Test",
            hint="test",
            schema_id=12345,
            section_id="section",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["dataset"] is None

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_http_error(self, mock_client_class: MagicMock, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [{"id": "section", "category": "section", "children": []}]

        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = suggest_lookup_field(
            label="Test",
            hint="test",
            schema_id=12345,
            section_id="section",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "HTTP 500" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_caches_field_definition(self, mock_client_class: MagicMock, mock_fetch: MagicMock) -> None:
        _field_definition_cache.clear()
        mock_fetch.return_value = [{"id": "vendor_section", "category": "section", "children": []}]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "matching": {
                        "type": "master_data_hub",
                        "configuration": {"dataset": "Vendors", "queries": []},
                    },
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        suggest_lookup_field(
            label="Vendor Match",
            hint="Match vendors",
            schema_id=12345,
            section_id="vendor_section",
            field_schema_id="vendor_match",
        )

        assert "vendor_match" in _field_definition_cache
        cached = _field_definition_cache["vendor_match"]
        assert cached["id"] == "vendor_match"
        assert cached["matching"]["type"] == "master_data_hub"
        _field_definition_cache.clear()


class TestFindLookupFieldIds:
    def test_finds_lookup_in_section(self) -> None:
        schema = [
            {
                "id": "vendor_section",
                "category": "section",
                "children": [
                    {"id": "sender_name", "category": "datapoint"},
                    {
                        "id": "approved_vendor",
                        "category": "datapoint",
                        "ui_configuration": {"type": "lookup", "edit": "disabled"},
                    },
                ],
            }
        ]
        assert _find_lookup_field_ids(schema) == {"approved_vendor"}

    def test_returns_empty_when_no_lookup(self) -> None:
        schema = [
            {
                "id": "section",
                "category": "section",
                "children": [{"id": "field", "category": "datapoint"}],
            }
        ]
        assert _find_lookup_field_ids(schema) == set()

    def test_skips_non_dict_children(self) -> None:
        schema = [
            {
                "id": "section",
                "category": "section",
                "children": [
                    "some_string_child",
                    {"id": "vendor", "ui_configuration": {"type": "lookup"}},
                ],
            }
        ]
        assert _find_lookup_field_ids(schema) == {"vendor"}

    def test_finds_multiple_lookup_fields(self) -> None:
        schema = [
            {
                "id": "section",
                "category": "section",
                "children": [
                    {"id": "vendor", "ui_configuration": {"type": "lookup"}},
                    {"id": "product", "ui_configuration": {"type": "lookup"}},
                ],
            }
        ]
        assert _find_lookup_field_ids(schema) == {"vendor", "product"}


class TestGetPlaceholderFieldIds:
    def test_extracts_simple_field_ref(self) -> None:
        schema = [
            {
                "id": "section",
                "category": "section",
                "children": [
                    {
                        "id": "vendor_match",
                        "ui_configuration": {"type": "lookup"},
                        "matching": {
                            "type": "master_data_hub",
                            "configuration": {
                                "placeholders": {"vat": {"__formula": "field.sender_vat_id"}},
                            },
                        },
                    }
                ],
            }
        ]
        assert _get_placeholder_field_ids(schema) == {"vendor_match": {"sender_vat_id"}}

    def test_extracts_default_to_formula(self) -> None:
        schema = [
            {
                "id": "vendor",
                "ui_configuration": {"type": "lookup"},
                "matching": {
                    "configuration": {
                        "placeholders": {
                            "vat": {"__formula": 'default_to(field.sender_vat_id, "")'},
                            "name": {"__formula": "field.sender_name"},
                        },
                    },
                },
            }
        ]
        assert _get_placeholder_field_ids(schema) == {"vendor": {"sender_vat_id", "sender_name"}}

    def test_extracts_from_variables_key(self) -> None:
        schema = [
            {
                "id": "vendor",
                "ui_configuration": {"type": "lookup"},
                "matching": {
                    "configuration": {
                        "variables": {
                            "sender_name": {"__formula": 'default_to(field.sender_name, "UNKNOWN")'},
                            "sender_vat_id": {"__formula": 'default_to(field.sender_vat_id, "UNKNOWN")'},
                        },
                    },
                },
            }
        ]
        assert _get_placeholder_field_ids(schema) == {"vendor": {"sender_name", "sender_vat_id"}}

    def test_returns_empty_for_non_lookup(self) -> None:
        schema = [{"id": "section", "category": "section", "children": [{"id": "field", "category": "datapoint"}]}]
        assert _get_placeholder_field_ids(schema) == {}


class TestCollectDatapointValues:
    def test_collects_values(self) -> None:
        content = [
            {
                "category": "section",
                "children": [
                    {"category": "datapoint", "schema_id": "sender_name", "content": {"value": "ACME"}},
                    {"category": "datapoint", "schema_id": "sender_vat_id", "content": {"value": "CZ123"}},
                    {"category": "datapoint", "schema_id": "amount_total", "content": {"value": "100"}},
                ],
            }
        ]
        result = _collect_datapoint_values(content, {"sender_name", "sender_vat_id"})
        assert result == {"sender_name": "ACME", "sender_vat_id": "CZ123"}

    def test_returns_empty_for_no_match(self) -> None:
        content = [
            {
                "category": "section",
                "children": [{"category": "datapoint", "schema_id": "other", "content": {"value": "x"}}],
            }
        ]
        assert _collect_datapoint_values(content, {"sender_name"}) == {}


class TestExtractLookupResults:
    def test_extracts_with_matching_context(self) -> None:
        annotation_content = [
            {
                "category": "section",
                "schema_id": "vendor_section",
                "children": [
                    {"category": "datapoint", "schema_id": "sender_name", "content": {"value": "ACME Corp"}},
                    {"category": "datapoint", "schema_id": "sender_vat_id", "content": {"value": "CZ123"}},
                    {
                        "category": "datapoint",
                        "schema_id": "approved_vendor",
                        "content": {"value": "3", "options": [{"value": "3", "label": "ACME Corp"}]},
                    },
                ],
            }
        ]
        placeholder_map = {"approved_vendor": {"sender_name", "sender_vat_id"}}
        results = _extract_lookup_results(annotation_content, {"approved_vendor"}, placeholder_map)
        assert len(results) == 1
        assert results[0] == {
            "schema_id": "approved_vendor",
            "value": "3",
            "options": [{"value": "3", "label": "ACME Corp"}],
            "matching_fields": {"sender_name": "ACME Corp", "sender_vat_id": "CZ123"},
        }

    def test_returns_empty_for_no_match(self) -> None:
        annotation_content = [
            {
                "category": "section",
                "children": [{"category": "datapoint", "schema_id": "sender_name", "content": {"value": "X"}}],
            }
        ]
        assert _extract_lookup_results(annotation_content, {"approved_vendor"}, {}) == []

    def test_no_matching_fields_when_no_placeholders(self) -> None:
        annotation_content = [
            {
                "category": "section",
                "children": [
                    {"category": "datapoint", "schema_id": "vendor", "content": {"value": "", "options": []}}
                ],
            }
        ]
        results = _extract_lookup_results(annotation_content, {"vendor"}, {})
        assert results == [{"schema_id": "vendor", "value": "", "options": []}]


class TestEvaluateLookupField:
    _SCHEMA: ClassVar[list] = [
        {
            "id": "vendor_section",
            "category": "section",
            "children": [
                {"id": "sender_name", "category": "datapoint"},
                {"id": "sender_vat_id", "category": "datapoint"},
                {
                    "id": "vendor_match",
                    "category": "datapoint",
                    "ui_configuration": {"type": "lookup", "edit": "disabled"},
                    "matching": {
                        "type": "master_data_hub",
                        "configuration": {
                            "dataset": "Vendors",
                            "placeholders": {
                                "name": {"__formula": "field.sender_name"},
                                "vat": {"__formula": "field.sender_vat_id"},
                            },
                        },
                    },
                },
            ],
        }
    ]

    def _make_evaluated_content(self, name: str, vat: str, value: str, label: str) -> list:
        return [
            {
                "category": "section",
                "schema_id": "vendor_section",
                "children": [
                    {"schema_id": "sender_name", "category": "datapoint", "content": {"value": name}},
                    {"schema_id": "sender_vat_id", "category": "datapoint", "content": {"value": vat}},
                    {
                        "schema_id": "vendor_match",
                        "category": "datapoint",
                        "content": {"value": value, "options": [{"value": value, "label": label}]},
                    },
                ],
            }
        ]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_annotation_content")
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_single_annotation(
        self, mock_client_class: MagicMock, mock_fetch_schema: MagicMock, mock_fetch_annotation: MagicMock
    ) -> None:
        mock_fetch_schema.return_value = self._SCHEMA
        mock_fetch_annotation.return_value = [
            {
                "category": "section",
                "schema_id": "vendor_section",
                "children": [{"schema_id": "vendor_match", "category": "datapoint", "content": {"value": ""}}],
            }
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "annotation_content": self._make_evaluated_content("ACME Corp", "CZ123", "5", "ACME Corp"),
            "automation_blockers": [],
            "messages": [{"type": "info", "content": "Lookup resolved"}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = evaluate_lookup_field(schema_id=12345, annotation_urls=["/api/v1/annotations/67890"])

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert "schema_id" not in parsed
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["annotation_url"] == "/api/v1/annotations/67890"
        assert parsed["results"][0]["lookup_results"] == [
            {
                "schema_id": "vendor_match",
                "value": "5",
                "options": [{"value": "5", "label": "ACME Corp"}],
                "matching_fields": {"sender_name": "ACME Corp", "sender_vat_id": "CZ123"},
            }
        ]
        assert "automation_blockers" not in parsed["results"][0]
        assert parsed["results"][0]["messages"] == [{"type": "info", "content": "Lookup resolved"}]
        mock_fetch_schema.assert_called_once_with("https://api.rossum.ai/v1", "test_token", 12345)
        mock_fetch_annotation.assert_called_once_with(
            "https://api.rossum.ai/v1", "test_token", "/api/v1/annotations/67890"
        )

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_annotation_content")
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_multiple_annotations_fetches_schema_once(
        self, mock_client_class: MagicMock, mock_fetch_schema: MagicMock, mock_fetch_annotation: MagicMock
    ) -> None:
        mock_fetch_schema.return_value = self._SCHEMA
        mock_fetch_annotation.side_effect = [
            [{"category": "section", "schema_id": "vendor_section", "children": []}],
            [{"category": "section", "schema_id": "vendor_section", "children": []}],
        ]

        mock_response = MagicMock()
        mock_response.json.side_effect = [
            {
                "annotation_content": self._make_evaluated_content("ACME Corp", "CZ123", "5", "ACME Corp"),
                "automation_blockers": [],
                "messages": [],
            },
            {
                "annotation_content": self._make_evaluated_content("Beta Inc", "DE456", "7", "Beta Inc"),
                "automation_blockers": [],
                "messages": [],
            },
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = evaluate_lookup_field(
            schema_id=12345,
            annotation_urls=["/api/v1/annotations/100", "/api/v1/annotations/200"],
        )

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["annotation_url"] == "/api/v1/annotations/100"
        assert parsed["results"][1]["annotation_url"] == "/api/v1/annotations/200"
        # Schema fetched only once
        mock_fetch_schema.assert_called_once()
        assert mock_fetch_annotation.call_count == 2
        assert mock_client.post.call_count == 2

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        set_context(AgentContext())
        result = evaluate_lookup_field(schema_id=12345, annotation_urls=["/api/v1/annotations/67890"])

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "credentials not available" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_annotation_content")
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_http_error(
        self, mock_client_class: MagicMock, mock_fetch_schema: MagicMock, mock_fetch_annotation: MagicMock
    ) -> None:
        mock_fetch_schema.return_value = [{"id": "section", "category": "section", "children": []}]
        mock_fetch_annotation.return_value = [{"id": "section", "children": []}]

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Client Error", request=MagicMock(), response=mock_response
        )

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = evaluate_lookup_field(schema_id=12345, annotation_urls=["/api/v1/annotations/67890"])

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "HTTP 400" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_annotation_content")
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_field_definition_overrides_schema(
        self, mock_client_class: MagicMock, mock_fetch_schema: MagicMock, mock_fetch_annotation: MagicMock
    ) -> None:
        # Schema on the API has vendor_match with old (empty) matching config
        mock_fetch_schema.return_value = [
            {
                "id": "vendor_section",
                "category": "section",
                "children": [
                    {"id": "sender_name", "category": "datapoint"},
                    {
                        "id": "vendor_match",
                        "category": "datapoint",
                        "ui_configuration": {"type": "lookup", "edit": "disabled"},
                        "matching": {"type": "master_data_hub", "configuration": {}},
                    },
                ],
            }
        ]
        mock_fetch_annotation.return_value = [
            {
                "category": "section",
                "schema_id": "vendor_section",
                "children": [{"schema_id": "vendor_match", "category": "datapoint", "content": {"value": ""}}],
            }
        ]
        evaluated_content = [
            {
                "category": "section",
                "schema_id": "vendor_section",
                "children": [
                    {"schema_id": "sender_name", "category": "datapoint", "content": {"value": "ACME Corp"}},
                    {
                        "schema_id": "vendor_match",
                        "category": "datapoint",
                        "content": {"value": "ACME Corp", "options": [{"value": "ACME Corp", "label": "ACME Corp"}]},
                    },
                ],
            }
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "annotation_content": evaluated_content,
            "automation_blockers": [],
            "messages": [],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Provide a new field_definition with updated matching config
        new_field_def = {
            "id": "vendor_match",
            "type": "enum",
            "category": "datapoint",
            "ui_configuration": {"type": "lookup", "edit": "disabled"},
            "matching": {
                "type": "master_data_hub",
                "configuration": {
                    "dataset": "imported-abc",
                    "queries": [{"aggregate": []}],
                    "variables": {"sender_name": {"__formula": "field.sender_name"}},
                },
            },
        }

        result = evaluate_lookup_field(
            schema_id=12345,
            annotation_urls=["/api/v1/annotations/67890"],
            field_definition=new_field_def,
        )

        parsed = json.loads(result)
        assert parsed["status"] == "success"

        # Verify the schema sent to the evaluate API contains the new field_definition, not the old one
        posted_payload = mock_client.post.call_args[1]["json"]
        sent_schema = posted_payload["schema_content"]
        sent_field = next(c for s in sent_schema for c in s.get("children", []) if c.get("id") == "vendor_match")
        assert sent_field["matching"]["configuration"]["dataset"] == "imported-abc"

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_annotation_content")
    @patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_uses_cached_definition_via_field_schema_id(
        self, mock_client_class: MagicMock, mock_fetch_schema: MagicMock, mock_fetch_annotation: MagicMock
    ) -> None:
        cached_def = {
            "id": "vendor_match",
            "type": "enum",
            "category": "datapoint",
            "ui_configuration": {"type": "lookup", "edit": "disabled"},
            "matching": {
                "type": "master_data_hub",
                "configuration": {
                    "dataset": "imported-cached",
                    "queries": [],
                    "variables": {"sender_name": {"__formula": "field.sender_name"}},
                },
            },
        }
        _field_definition_cache["vendor_match"] = cached_def

        mock_fetch_schema.return_value = [
            {
                "id": "vendor_section",
                "category": "section",
                "children": [{"id": "sender_name", "category": "datapoint"}],
            }
        ]
        mock_fetch_annotation.return_value = [{"category": "section", "schema_id": "vendor_section", "children": []}]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "annotation_content": [
                {
                    "category": "section",
                    "schema_id": "vendor_section",
                    "children": [
                        {
                            "schema_id": "vendor_match",
                            "category": "datapoint",
                            "content": {"value": "ACME", "options": []},
                        }
                    ],
                }
            ],
            "automation_blockers": [],
            "messages": [],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = evaluate_lookup_field(
            schema_id=12345,
            annotation_urls=["/api/v1/annotations/67890"],
            field_schema_id="vendor_match",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        # Verify cached definition was injected
        posted_payload = mock_client.post.call_args[1]["json"]
        schema_in_payload = posted_payload["schema_content"]
        injected = next(
            (c for s in schema_in_payload for c in s.get("children", []) if c.get("id") == "vendor_match"), None
        )
        assert injected is not None
        assert injected["matching"]["configuration"]["dataset"] == "imported-cached"
        _field_definition_cache.clear()

    def test_returns_error_for_unknown_field_schema_id(self) -> None:
        _field_definition_cache.clear()
        result = evaluate_lookup_field(
            schema_id=12345,
            annotation_urls=["/api/v1/annotations/67890"],
            field_schema_id="nonexistent_field",
        )
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "nonexistent_field" in parsed["error"]

    def test_omits_empty_automation_blockers_and_messages(self) -> None:
        """Empty automation_blockers and messages are not included in results."""
        import json as json_module

        with (
            patch.dict(
                "os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"}
            ),
            patch("rossum_agent.python_tools.copilot.lookup._fetch_annotation_content") as mock_fetch_annotation,
            patch("rossum_agent.python_tools.copilot.lookup._fetch_schema_content") as mock_fetch_schema,
            patch("rossum_agent.python_tools.copilot.lookup.httpx.Client") as mock_client_class,
        ):
            mock_fetch_schema.return_value = self._SCHEMA
            mock_fetch_annotation.return_value = [{"category": "section", "children": []}]

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "annotation_content": [],
                "automation_blockers": [],
                "messages": [],
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = evaluate_lookup_field(schema_id=12345, annotation_urls=["/api/v1/annotations/1"])
            parsed = json_module.loads(result)
            assert parsed["status"] == "success"
            assert "automation_blockers" not in parsed["results"][0]
            assert "messages" not in parsed["results"][0]


class TestGetLookupDatasetRawValues:
    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._resolve_mdh_dataset_identifier")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_fetches_raw_dataset(self, mock_client_class: MagicMock, mock_resolve_dataset: MagicMock) -> None:
        mock_resolve_dataset.return_value = "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b"

        mock_response = MagicMock()
        mock_response.json.return_value = {"list": [{"name": "a"}, {"name": "b"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = get_lookup_dataset_raw_values(dataset="approved-vendors", limit=250)

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["dataset"] == "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b"
        assert parsed["limit"] == 250
        assert parsed["row_count"] == 2
        assert "raw_data" not in parsed
        assert "note" in parsed

        mock_client.post.assert_called_once_with(
            "https://api.rossum.ai/svc/master-data-hub/api/v1/data/aggregate",
            json={
                "aggregate": [{"$limit": 250}],
                "collation": {},
                "let": {},
                "options": {},
                "dataset": "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b",
            },
            headers={"Authorization": "Bearer test_token", "Content-Type": "application/json"},
        )

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.python_tools.copilot.lookup._resolve_mdh_dataset_identifier")
    @patch("rossum_agent.python_tools.copilot.lookup.httpx.Client")
    def test_populates_cache(self, mock_client_class: MagicMock, mock_resolve_dataset: MagicMock) -> None:
        _dataset_cache.clear()
        mock_resolve_dataset.return_value = "imported-abc123"

        mock_response = MagicMock()
        mock_response.json.return_value = {"list": [{"x": 1}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        get_lookup_dataset_raw_values(dataset="my-dataset", limit=100)

        assert _dataset_cache.get("imported-abc123") == [{"x": 1}]
        assert _dataset_cache.get("my-dataset") == [{"x": 1}]
        _dataset_cache.clear()

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        set_context(AgentContext())

        result = get_lookup_dataset_raw_values(dataset="approved-vendors")

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "credentials not available" in parsed["error"]


class TestQueryLookupDataset:
    def setup_method(self) -> None:
        _dataset_cache.clear()

    def teardown_method(self) -> None:
        _dataset_cache.clear()

    def test_jq_query_on_cached_dataset(self) -> None:
        _cache_dataset("imported-abc", "vendors", {"list": [{"name": "Acme"}, {"name": "Beta"}]})

        result = query_lookup_dataset(dataset="imported-abc", jq_query="length")
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["result"].strip() == "2"

    def test_lookup_by_alias(self) -> None:
        _cache_dataset("imported-abc", "vendors", {"list": [{"name": "Acme"}]})

        result = query_lookup_dataset(dataset="vendors", jq_query=".[0].name")
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["result"].strip() == '"Acme"'

    def test_filter_rows(self) -> None:
        _cache_dataset(
            "imported-abc",
            "vendors",
            {
                "list": [
                    {"name": "Acme Corp", "vat": "CZ123"},
                    {"name": "Beta Inc", "vat": "DE456"},
                    {"name": "Acme Ltd", "vat": "CZ789"},
                ]
            },
        )

        result = query_lookup_dataset(dataset="vendors", jq_query='.[] | select(.name | test("acme"; "i")) | .vat')
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert '"CZ123"' in parsed["result"]
        assert '"CZ789"' in parsed["result"]
        assert '"DE456"' not in parsed["result"]

    def test_get_column_names(self) -> None:
        _cache_dataset("imported-abc", "ds", {"list": [{"name": "a", "vat": "b", "city": "c"}]})

        result = query_lookup_dataset(dataset="ds", jq_query=".[0] | keys")
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        for col in ["city", "name", "vat"]:
            assert col in parsed["result"]

    def test_dataset_not_cached(self) -> None:
        result = query_lookup_dataset(dataset="nonexistent", jq_query=".")
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "not found in cache" in parsed["error"]

    def test_invalid_jq_query(self) -> None:
        _cache_dataset("imported-abc", "ds", {"list": []})

        result = query_lookup_dataset(dataset="ds", jq_query="invalid[[[")
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "jq error" in parsed["error"]

    def test_extracts_rows_from_results_key(self) -> None:
        _cache_dataset("imported-abc", "ds", {"results": [{"a": 1}, {"a": 2}]})

        result = query_lookup_dataset(dataset="ds", jq_query="length")
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["result"].strip() == "2"

    def test_extracts_rows_from_flat_array(self) -> None:
        _cache_dataset("imported-abc", "ds", [{"a": 1}])

        result = query_lookup_dataset(dataset="ds", jq_query=".[0].a")
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["result"].strip() == "1"
