"""Tests for Master Data Hub dataset listing and querying tools."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from rossum_agent.python_tools.master_data_hub import (
    _extract_dataset_name,
    _extract_field_names,
    list_datasets,
    search_dataset,
)
from rossum_agent.tools.core import AgentContext, set_context

_ENV = {"ROSSUM_API_BASE_URL": "https://example.rossum.app/api/v1", "ROSSUM_API_TOKEN": "test-token"}


class TestExtractDatasetName:
    def test_from_metadata_name(self) -> None:
        item = {"id": "imported-abc", "metadata": {"name": "Approved Vendors"}}
        assert _extract_dataset_name(item) == "Approved Vendors"

    def test_from_top_level_name(self) -> None:
        item = {"id": "imported-abc", "name": "vendors"}
        assert _extract_dataset_name(item) == "vendors"

    def test_metadata_takes_precedence(self) -> None:
        item = {"id": "imported-abc", "name": "vendors", "metadata": {"name": "Approved Vendors"}}
        assert _extract_dataset_name(item) == "Approved Vendors"

    def test_fallback_to_id(self) -> None:
        item = {"id": "imported-abc"}
        assert _extract_dataset_name(item) == "imported-abc"

    def test_empty_dict(self) -> None:
        assert _extract_dataset_name({}) == ""


class TestExtractFieldNames:
    def test_extracts_property_names(self) -> None:
        item = {"schema": {"properties": {"Name": {"type": "string"}, "VAT ID": {"type": "string"}}}}
        assert _extract_field_names(item) == ["Name", "VAT ID"]

    def test_no_schema(self) -> None:
        assert _extract_field_names({}) == []

    def test_no_properties(self) -> None:
        assert _extract_field_names({"schema": {}}) == []

    def test_schema_not_dict(self) -> None:
        assert _extract_field_names({"schema": "invalid"}) == []


class TestListDatasets:
    @patch.dict("os.environ", _ENV)
    @patch("rossum_agent.python_tools.master_data_hub.httpx.Client")
    def test_returns_formatted_datasets(self, mock_client_class: MagicMock) -> None:
        set_context(AgentContext())
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "imported-abc",
                    "name": "imported-abc",
                    "metadata": {"name": "Approved Vendors", "description": "Vendor master data"},
                    "schema": {"properties": {"Name": {"type": "string"}, "VAT ID": {"type": "string"}}},
                },
                {
                    "id": "imported-def",
                    "name": "imported-def",
                    "metadata": {"name": "Cost Centers"},
                    "schema": {"properties": {"Code": {"type": "string"}}},
                },
            ]
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = json.loads(list_datasets())

        assert result["status"] == "success"
        assert result["count"] == 2
        assert result["datasets"][0]["id"] == "imported-abc"
        assert result["datasets"][0]["name"] == "Approved Vendors"
        assert result["datasets"][0]["description"] == "Vendor master data"
        assert result["datasets"][0]["fields"] == ["Name", "VAT ID"]
        assert result["datasets"][1]["id"] == "imported-def"
        assert result["datasets"][1]["name"] == "Cost Centers"
        assert "description" not in result["datasets"][1]

    @patch.dict("os.environ", _ENV)
    @patch("rossum_agent.python_tools.master_data_hub.httpx.Client")
    def test_handles_list_response(self, mock_client_class: MagicMock) -> None:
        set_context(AgentContext())
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "imported-abc", "metadata": {"name": "Vendors"}, "schema": {"properties": {}}}
        ]
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = json.loads(list_datasets())

        assert result["status"] == "success"
        assert result["count"] == 1

    @patch.dict("os.environ", _ENV)
    @patch("rossum_agent.python_tools.master_data_hub.httpx.Client")
    def test_handles_empty_response(self, mock_client_class: MagicMock) -> None:
        set_context(AgentContext())
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = json.loads(list_datasets())

        assert result["status"] == "success"
        assert result["count"] == 0
        assert result["datasets"] == []

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        set_context(AgentContext())
        result = json.loads(list_datasets())
        assert result["status"] == "error"
        assert "credentials not available" in result["error"]


class TestSearchDataset:
    @patch.dict("os.environ", _ENV)
    @patch("rossum_agent.python_tools.master_data_hub._resolve_mdh_dataset_identifier")
    @patch("rossum_agent.python_tools.master_data_hub.httpx.Client")
    def test_simple_match_query(self, mock_client_class: MagicMock, mock_resolve: MagicMock) -> None:
        set_context(AgentContext())
        mock_resolve.return_value = "imported-abc"

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"Name": "Acme Corp", "VAT ID": "DE123"}]}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = json.loads(search_dataset(dataset="Vendors", match={"VAT ID": "DE123"}))

        assert result["status"] == "success"
        assert result["dataset"] == "imported-abc"
        assert result["row_count"] == 1
        assert result["rows"][0]["Name"] == "Acme Corp"

        # Verify the aggregate payload
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["dataset"] == "imported-abc"
        assert {"$match": {"VAT ID": "DE123"}} in payload["aggregate"]
        assert {"$limit": 50} in payload["aggregate"]

    @patch.dict("os.environ", _ENV)
    @patch("rossum_agent.python_tools.master_data_hub._resolve_mdh_dataset_identifier")
    @patch("rossum_agent.python_tools.master_data_hub.httpx.Client")
    def test_pipeline_query(self, mock_client_class: MagicMock, mock_resolve: MagicMock) -> None:
        set_context(AgentContext())
        mock_resolve.return_value = "imported-abc"

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"Name": "Acme"}]}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = json.loads(
            search_dataset(
                dataset="Vendors",
                pipeline=[{"$sort": {"Name": 1}}, {"$limit": 10}],
            )
        )

        assert result["status"] == "success"
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        # Pipeline already has $limit, should not append another
        assert payload["aggregate"] == [{"$sort": {"Name": 1}}, {"$limit": 10}]

    @patch.dict("os.environ", _ENV)
    @patch("rossum_agent.python_tools.master_data_hub._resolve_mdh_dataset_identifier")
    @patch("rossum_agent.python_tools.master_data_hub.httpx.Client")
    def test_match_plus_pipeline_combined(self, mock_client_class: MagicMock, mock_resolve: MagicMock) -> None:
        set_context(AgentContext())
        mock_resolve.return_value = "imported-abc"

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = json.loads(
            search_dataset(
                dataset="Vendors",
                match={"Country": "DE"},
                pipeline=[{"$sort": {"Name": 1}}],
            )
        )

        assert result["status"] == "success"
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["aggregate"][0] == {"$match": {"Country": "DE"}}
        assert payload["aggregate"][1] == {"$sort": {"Name": 1}}
        assert {"$limit": 50} in payload["aggregate"]

    @patch.dict("os.environ", _ENV)
    @patch("rossum_agent.python_tools.master_data_hub._resolve_mdh_dataset_identifier")
    @patch("rossum_agent.python_tools.master_data_hub.httpx.Client")
    def test_no_filters_fetches_first_rows(self, mock_client_class: MagicMock, mock_resolve: MagicMock) -> None:
        set_context(AgentContext())
        mock_resolve.return_value = "imported-abc"

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"a": 1}, {"a": 2}]}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = json.loads(search_dataset(dataset="Vendors", limit=5))

        assert result["status"] == "success"
        assert result["row_count"] == 2
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["aggregate"] == [{"$limit": 5}]

    @patch.dict("os.environ", _ENV)
    def test_empty_dataset_name_returns_error(self) -> None:
        set_context(AgentContext())
        result = json.loads(search_dataset(dataset="  "))
        assert result["status"] == "error"
        assert "non-empty" in result["error"]

    @patch.dict("os.environ", _ENV)
    @patch("rossum_agent.python_tools.master_data_hub._resolve_mdh_dataset_identifier")
    @patch("rossum_agent.python_tools.master_data_hub.httpx.Client")
    def test_handles_list_response_format(self, mock_client_class: MagicMock, mock_resolve: MagicMock) -> None:
        set_context(AgentContext())
        mock_resolve.return_value = "imported-abc"

        mock_response = MagicMock()
        mock_response.json.return_value = [{"Name": "Acme"}]
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = json.loads(search_dataset(dataset="Vendors", match={"Name": "Acme"}))

        assert result["status"] == "success"
        assert result["row_count"] == 1
        assert result["rows"] == [{"Name": "Acme"}]

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        set_context(AgentContext())
        result = json.loads(search_dataset(dataset="Vendors"))
        assert result["status"] == "error"
        assert "credentials not available" in result["error"]
