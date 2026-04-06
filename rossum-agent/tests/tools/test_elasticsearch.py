"""Tests for elasticsearch tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.tools.internal.elasticsearch import (
    _deployment_location_to_env_prefix,
    _format_response,
    _inject_org_filter,
    _reject_scripts,
    _validate_aggs,
    _validate_index,
    search_elasticsearch,
)

ORG_ID = 327033
DEPLOYMENT_LOCATION = "prod-eu2"


@pytest.fixture(autouse=True)
def _set_allowed_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELASTICSEARCH_ALLOWED_INDEX_PREFIXES", "elis_ann_alias_")


class TestValidateIndex:
    def test_allows_annotation_alias_wildcard(self) -> None:
        _validate_index("elis_ann_alias_*")

    def test_allows_specific_annotation_alias(self) -> None:
        _validate_index("elis_ann_alias_12345")

    @pytest.mark.parametrize(
        "index",
        [
            ".kibana",
            "system_logs",
            "elis_other_index",
            "*",
            "",
            "elis_ann_alias",
        ],
    )
    def test_rejects_disallowed_indices(self, index: str) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            _validate_index(index)


class TestSearchElasticsearchIndexValidation:
    def test_rejects_disallowed_index(self) -> None:
        result = json.loads(search_elasticsearch(index=".kibana", query="*"))
        assert result["status"] == "error"
        assert "not allowed" in result["message"]


class TestValidateAggs:
    def test_blocks_global_aggregation(self) -> None:
        aggs = {"cross_tenant": {"global": {}, "aggs": {"count": {"value_count": {"field": "status"}}}}}
        with pytest.raises(ValueError, match="global"):
            _validate_aggs(aggs)

    def test_blocks_nested_global_aggregation(self) -> None:
        aggs = {
            "outer": {
                "nested": {"path": "datapoints"},
                "aggs": {"inner": {"global": {}, "aggs": {"count": {"value_count": {"field": "status"}}}}},
            }
        }
        with pytest.raises(ValueError, match="global"):
            _validate_aggs(aggs)

    def test_allows_safe_aggregations(self) -> None:
        aggs = {
            "dp": {
                "nested": {"path": "datapoints"},
                "aggs": {
                    "filtered": {
                        "filter": {"term": {"datapoints.schema_id": "currency"}},
                        "aggs": {"result": {"terms": {"field": "datapoints.text.keyword", "size": 20}}},
                    }
                },
            }
        }
        _validate_aggs(aggs)


class TestRejectScripts:
    def test_allows_script_query(self) -> None:
        body = {"query": {"script": {"script": {"source": "true"}}}}
        _reject_scripts(body)  # script queries are legitimate DSL constructs

    def test_blocks_scripted_metric_in_aggs(self) -> None:
        body = {
            "aggs": {
                "steal": {
                    "scripted_metric": {
                        "init_script": "state.data = []",
                        "map_script": "state.data.add(1)",
                        "combine_script": "return state.data",
                        "reduce_script": "return states",
                    }
                }
            }
        }
        with pytest.raises(ValueError, match="scripted_metric"):
            _reject_scripts(body)

    def test_blocks_script_sort(self) -> None:
        body = {"sort": [{"_script": {"type": "number", "script": {"source": "1"}}}]}
        with pytest.raises(ValueError, match="_script"):
            _reject_scripts(body)

    def test_blocks_bucket_script(self) -> None:
        body = {"aggs": {"x": {"bucket_script": {"buckets_path": {"a": "a"}, "script": "1"}}}}
        with pytest.raises(ValueError, match="bucket_script"):
            _reject_scripts(body)

    def test_allows_safe_body(self) -> None:
        body = {
            "query": {"bool": {"filter": [{"terms": {"queue_id": [123]}}]}},
            "aggs": {"count": {"value_count": {"field": "status"}}},
            "size": 0,
        }
        _reject_scripts(body)


class TestSearchElasticsearchMultiIndex:
    def test_rejects_comma_separated_indices(self) -> None:
        result = json.loads(search_elasticsearch(index="elis_ann_alias_*,.kibana", query="*"))
        assert result["status"] == "error"
        assert "Multiple index" in result["message"]


class TestSearchElasticsearchDeepValidation:
    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    @patch("rossum_agent.tools.internal.elasticsearch._get_es_client")
    def test_rejects_global_aggregation(self, mock_get_client: MagicMock, mock_get_org_info: MagicMock) -> None:
        dsl = json.dumps(
            {
                "size": 0,
                "aggs": {"cross_tenant": {"global": {}, "aggs": {"count": {"value_count": {"field": "status"}}}}},
            }
        )
        result = json.loads(search_elasticsearch(index="elis_ann_alias_*", query=dsl))
        assert result["status"] == "error"
        assert "global" in result["message"]
        mock_get_client.return_value.search.assert_not_called()

    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    @patch("rossum_agent.tools.internal.elasticsearch._get_es_client")
    def test_allows_script_in_query(self, mock_get_client: MagicMock, mock_get_org_info: MagicMock) -> None:
        mock_get_client.return_value.search.return_value = MagicMock(
            body={"hits": {"total": {"value": 0}, "hits": []}}
        )
        dsl = json.dumps({"query": {"script": {"script": {"source": "true"}}}})
        result = json.loads(search_elasticsearch(index="elis_ann_alias_*", query=dsl))
        assert result["status"] == "success"
        # Verify org filter was still injected (body is splatted as kwargs)
        call_kwargs = mock_get_client.return_value.search.call_args[1]
        filters = call_kwargs["query"]["bool"]["filter"]
        assert {"term": {"organization_id": ORG_ID}} in filters

    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    @patch("rossum_agent.tools.internal.elasticsearch._get_es_client")
    def test_rejects_scripted_metric_in_aggs(self, mock_get_client: MagicMock, mock_get_org_info: MagicMock) -> None:
        dsl = json.dumps(
            {
                "size": 0,
                "aggs": {
                    "steal": {
                        "scripted_metric": {
                            "init_script": "state.data = []",
                            "map_script": "state.data.add(1)",
                            "combine_script": "return state.data",
                            "reduce_script": "return states",
                        }
                    }
                },
            }
        )
        result = json.loads(search_elasticsearch(index="elis_ann_alias_*", query=dsl))
        assert result["status"] == "error"
        assert "scripted_metric" in result["message"]
        mock_get_client.return_value.search.assert_not_called()


class TestSearchElasticsearchBodyKeyValidation:
    """Verify that dangerous top-level DSL keys are rejected to prevent org filter bypass."""

    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    @patch("rossum_agent.tools.internal.elasticsearch._get_es_client")
    def test_rejects_runtime_mappings(self, mock_get_client: MagicMock, mock_get_org_info: MagicMock) -> None:
        dsl = json.dumps(
            {
                "runtime_mappings": {"organization_id": {"type": "long", "script": {"source": "emit(1L)"}}},
                "query": {"match_all": {}},
            }
        )
        result = json.loads(search_elasticsearch(index="elis_ann_alias_*", query=dsl))
        assert result["status"] == "error"
        assert "runtime_mappings" in result["message"]
        mock_get_client.return_value.search.assert_not_called()

    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    @patch("rossum_agent.tools.internal.elasticsearch._get_es_client")
    def test_rejects_script_fields(self, mock_get_client: MagicMock, mock_get_org_info: MagicMock) -> None:
        dsl = json.dumps(
            {
                "script_fields": {"evil": {"script": {"source": "doc['organization_id'].value"}}},
                "query": {"match_all": {}},
            }
        )
        result = json.loads(search_elasticsearch(index="elis_ann_alias_*", query=dsl))
        assert result["status"] == "error"
        assert "script_fields" in result["message"]

    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    @patch("rossum_agent.tools.internal.elasticsearch._get_es_client")
    def test_allows_permitted_keys(self, mock_get_client: MagicMock, mock_get_org_info: MagicMock) -> None:
        mock_es = MagicMock()
        mock_es.search.return_value = MagicMock(body={"hits": {"total": {"value": 0}, "hits": []}})
        mock_get_client.return_value = mock_es

        dsl = json.dumps(
            {
                "query": {"match_all": {}},
                "aggs": {"count": {"value_count": {"field": "status"}}},
                "size": 0,
                "sort": [{"created_at": "desc"}],
                "track_total_hits": True,
            }
        )
        result = json.loads(search_elasticsearch(index="elis_ann_alias_*", query=dsl))
        assert result["status"] == "success"


class TestInjectOrgFilter:
    def test_injects_into_empty_body(self) -> None:
        body: dict = {}
        _inject_org_filter(body, ORG_ID)
        assert body["query"]["bool"]["filter"] == [{"term": {"organization_id": ORG_ID}}]

    def test_injects_into_existing_bool_without_filter(self) -> None:
        body: dict = {"query": {"bool": {"must": [{"match_all": {}}]}}}
        _inject_org_filter(body, ORG_ID)
        assert {"term": {"organization_id": ORG_ID}} in body["query"]["bool"]["filter"]
        assert body["query"]["bool"]["must"] == [{"match_all": {}}]

    def test_appends_to_existing_filter_list(self) -> None:
        body: dict = {"query": {"bool": {"filter": [{"terms": {"queue_id": [1]}}]}}}
        _inject_org_filter(body, ORG_ID)
        assert len(body["query"]["bool"]["filter"]) == 2
        assert {"term": {"organization_id": ORG_ID}} in body["query"]["bool"]["filter"]

    def test_converts_dict_filter_to_list(self) -> None:
        body: dict = {"query": {"bool": {"filter": {"terms": {"queue_id": [1]}}}}}
        _inject_org_filter(body, ORG_ID)
        assert isinstance(body["query"]["bool"]["filter"], list)
        assert len(body["query"]["bool"]["filter"]) == 2

    def test_wraps_non_bool_query(self) -> None:
        body: dict = {"query": {"match_all": {}}}
        _inject_org_filter(body, ORG_ID)
        assert body["query"]["bool"]["must"] == [{"match_all": {}}]
        assert {"term": {"organization_id": ORG_ID}} in body["query"]["bool"]["filter"]


class TestSearchElasticsearch:
    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    def test_returns_error_when_es_not_configured(self, mock_get_org_info: MagicMock) -> None:
        with patch.dict("os.environ", {"ELASTICSEARCH_ALLOWED_INDEX_PREFIXES": "elis_ann_alias_"}, clear=True):
            result = json.loads(search_elasticsearch(index="elis_ann_alias_test", query="*"))
        assert result["status"] == "error"
        assert "not configured" in result["message"]

    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    @patch("rossum_agent.tools.internal.elasticsearch._get_es_client")
    def test_query_string_search(self, mock_get_client: MagicMock, mock_get_org_info: MagicMock) -> None:
        mock_es = MagicMock()
        mock_es.search.return_value = MagicMock(
            body={
                "hits": {
                    "total": {"value": 1},
                    "hits": [{"_id": "123", "_source": {"status": "exported"}, "_score": 1.0}],
                }
            }
        )
        mock_get_client.return_value = mock_es

        result = json.loads(search_elasticsearch(index="elis_ann_alias_*", query="status:exported", size=5))

        assert result["status"] == "success"
        assert result["result"]["total"] == 1
        # Verify org filter was injected into the query kwargs
        call_kwargs = mock_es.search.call_args.kwargs
        assert call_kwargs["query"]["bool"]["filter"] == [{"term": {"organization_id": ORG_ID}}]
        assert call_kwargs["size"] == 5

    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    @patch("rossum_agent.tools.internal.elasticsearch._get_es_client")
    def test_dsl_query_with_aggregations(self, mock_get_client: MagicMock, mock_get_org_info: MagicMock) -> None:
        mock_es = MagicMock()
        mock_es.search.return_value = MagicMock(
            body={
                "hits": {"total": {"value": 0}, "hits": []},
                "aggregations": {
                    "dp": {
                        "doc_count": 500,
                        "filtered": {"doc_count": 120, "result": {"buckets": [{"key": "GBP", "doc_count": 80}]}},
                    }
                },
            }
        )
        mock_get_client.return_value = mock_es

        dsl = json.dumps(
            {
                "size": 0,
                "query": {"bool": {"filter": [{"terms": {"queue_id": [123]}}]}},
                "aggs": {
                    "dp": {
                        "nested": {"path": "datapoints"},
                        "aggs": {
                            "filtered": {
                                "filter": {"term": {"datapoints.schema_id": "currency"}},
                                "aggs": {"result": {"terms": {"field": "datapoints.text.keyword", "size": 20}}},
                            }
                        },
                    }
                },
            }
        )
        result = json.loads(search_elasticsearch(index="elis_ann_alias_*", query=dsl))

        assert result["status"] == "success"
        assert "aggregations" in result["result"]
        buckets = result["result"]["aggregations"]["dp"]["filtered"]["result"]["buckets"]
        assert buckets[0]["key"] == "GBP"
        # Verify org filter was injected alongside queue filter
        call_kwargs = mock_es.search.call_args.kwargs
        filters = call_kwargs["query"]["bool"]["filter"]
        assert {"term": {"organization_id": ORG_ID}} in filters
        assert {"terms": {"queue_id": [123]}} in filters

    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    @patch("rossum_agent.tools.internal.elasticsearch._get_es_client")
    def test_dsl_query_as_dict(self, mock_get_client: MagicMock, mock_get_org_info: MagicMock) -> None:
        """When the LLM passes query as a dict (not a JSON string), it should work the same."""
        mock_es = MagicMock()
        mock_es.search.return_value = MagicMock(
            body={
                "hits": {"total": {"value": 0}, "hits": []},
                "aggregations": {
                    "dp": {
                        "doc_count": 100,
                        "filtered": {
                            "doc_count": 50,
                            "result": {"buckets": [{"key": "Acme Corp", "doc_count": 30}]},
                        },
                    }
                },
            }
        )
        mock_get_client.return_value = mock_es

        dsl_dict = {
            "size": 0,
            "query": {"bool": {"filter": [{"terms": {"queue_id": [4111995]}}]}},
            "aggs": {
                "dp": {
                    "nested": {"path": "datapoints"},
                    "aggs": {
                        "filtered": {
                            "filter": {"term": {"datapoints.schema_id": "sender_name"}},
                            "aggs": {"result": {"terms": {"field": "datapoints.text.keyword", "size": 50}}},
                        }
                    },
                }
            },
        }
        result = json.loads(search_elasticsearch(index="elis_ann_alias_*", query=dsl_dict))

        assert result["status"] == "success"
        assert "aggregations" in result["result"]
        # Verify org filter was injected
        call_kwargs = mock_es.search.call_args.kwargs
        filters = call_kwargs["query"]["bool"]["filter"]
        assert {"term": {"organization_id": ORG_ID}} in filters

    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    @patch("rossum_agent.tools.internal.elasticsearch._get_es_client")
    def test_dsl_query_injects_default_size(self, mock_get_client: MagicMock, mock_get_org_info: MagicMock) -> None:
        mock_es = MagicMock()
        mock_es.search.return_value = MagicMock(body={"hits": {"total": {"value": 0}, "hits": []}})
        mock_get_client.return_value = mock_es

        dsl = json.dumps({"query": {"match_all": {}}})
        search_elasticsearch(index="elis_ann_alias_test", query=dsl, size=5)

        call_kwargs = mock_es.search.call_args.kwargs
        assert call_kwargs["size"] == 5

    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    @patch("rossum_agent.tools.internal.elasticsearch._get_es_client")
    def test_handles_es_exception(self, mock_get_client: MagicMock, mock_get_org_info: MagicMock) -> None:
        mock_es = MagicMock()
        mock_es.search.side_effect = Exception("Connection refused")
        mock_get_client.return_value = mock_es

        result = json.loads(search_elasticsearch(index="elis_ann_alias_test", query="*"))

        assert result["status"] == "error"
        assert "Connection refused" in result["message"]

    @patch("rossum_agent.tools.internal.elasticsearch._get_org_info", return_value=(ORG_ID, DEPLOYMENT_LOCATION))
    @patch("rossum_agent.tools.internal.elasticsearch._get_es_client")
    def test_truncates_large_output(self, mock_get_client: MagicMock, mock_get_org_info: MagicMock) -> None:
        mock_es = MagicMock()
        large_hits = [{"_id": str(i), "_source": {"data": "x" * 500}, "_score": 1.0} for i in range(200)]
        mock_es.search.return_value = MagicMock(body={"hits": {"total": {"value": 200}, "hits": large_hits}})
        mock_get_client.return_value = mock_es

        result = json.loads(search_elasticsearch(index="elis_ann_alias_test", query="*", size=200))

        assert result["status"] == "success"
        assert result["truncated"] is True


class TestDeploymentLocationToEnvPrefix:
    @pytest.mark.parametrize(
        ("location", "expected"),
        [
            ("prod-eu2", "PROD_EU2"),
            ("prod-us1", "PROD_US1"),
            ("staging-eu1", "STAGING_EU1"),
            ("PROD-EU2", "PROD_EU2"),
            ("prod_eu2", "PROD_EU2"),
        ],
    )
    def test_converts_location_to_prefix(self, location: str, expected: str) -> None:
        assert _deployment_location_to_env_prefix(location) == expected


class TestGetOrgInfo:
    @patch("rossum_agent.tools.internal.elasticsearch.SyncRossumAPIClient")
    @patch("rossum_agent.tools.internal.elasticsearch.get_context")
    def test_resolves_org_info(self, mock_get_context: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_ctx = MagicMock()
        mock_ctx.get_rossum_credentials.return_value = ("https://example.com", "tok")
        mock_get_context.return_value = mock_ctx

        mock_org = MagicMock()
        mock_org.id = ORG_ID
        mock_og = MagicMock()
        mock_og.deployment_location = DEPLOYMENT_LOCATION
        mock_client = MagicMock()
        mock_client.list_organizations.return_value = iter([mock_org])
        mock_client.list_organization_groups.return_value = iter([mock_og])
        mock_client_cls.return_value = mock_client

        from rossum_agent.tools.internal.elasticsearch import _get_org_info

        org_id, deployment_location = _get_org_info()
        assert org_id == ORG_ID
        assert deployment_location == DEPLOYMENT_LOCATION

    @patch("rossum_agent.tools.internal.elasticsearch.get_context")
    def test_raises_when_no_credentials(self, mock_get_context: MagicMock) -> None:
        mock_ctx = MagicMock()
        mock_ctx.get_rossum_credentials.return_value = None
        mock_get_context.return_value = mock_ctx

        from rossum_agent.tools.internal.elasticsearch import _get_org_info

        with pytest.raises(RuntimeError, match="credentials are not available"):
            _get_org_info()


class TestFormatResponse:
    def test_extracts_hits_and_total(self) -> None:
        raw = {
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {"_id": "1", "_source": {"name": "doc1"}, "_score": 1.5},
                    {"_id": "2", "_source": {"name": "doc2"}, "_score": 1.0},
                ],
            }
        }
        result = _format_response(raw)
        assert result["total"] == 2
        assert len(result["hits"]) == 2
        assert result["hits"][0]["_id"] == "1"

    def test_extracts_aggregations(self) -> None:
        raw = {
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {"my_agg": {"value": 42}},
        }
        result = _format_response(raw)
        assert result["total"] == 0
        assert "hits" not in result
        assert result["aggregations"]["my_agg"]["value"] == 42

    def test_handles_empty_response(self) -> None:
        raw = {"hits": {"total": {"value": 0}, "hits": []}}
        result = _format_response(raw)
        assert result["total"] == 0
        assert "hits" not in result
        assert "aggregations" not in result
