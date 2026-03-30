"""Tests for rossum_agent.agent.spillover module."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rossum_agent.agent.spillover import (
    SPILLOVER_THRESHOLD,
    _id_from_url,
    _summarize,
    maybe_spill,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestMaybeSpill:
    def test_small_content_unchanged(self, tmp_path: Path) -> None:
        content = "small result"
        result = maybe_spill(content, "test_tool", 1, tmp_path)
        assert result == content
        assert not (tmp_path / "workspace").exists()

    def test_at_threshold_unchanged(self, tmp_path: Path) -> None:
        content = "x" * SPILLOVER_THRESHOLD
        result = maybe_spill(content, "test_tool", 1, tmp_path)
        assert result == content

    def test_above_threshold_spills_to_file(self, tmp_path: Path) -> None:
        content = "x" * (SPILLOVER_THRESHOLD + 1)

        result = maybe_spill(content, "my_tool", 3, tmp_path)

        # File was created
        expected_file = tmp_path / "workspace" / "step3_my_tool.json"
        assert expected_file.is_file()
        assert expected_file.read_text() == content

        # Summary returned instead of full content
        assert str(expected_file) in result
        assert "run_jq" in result

    def test_spill_creates_workspace_dir(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "nested"
        content = "y" * (SPILLOVER_THRESHOLD + 1)

        maybe_spill(content, "tool", 1, output_dir)
        assert (output_dir / "workspace").is_dir()

    def test_spill_json_array_summary(self, tmp_path: Path) -> None:
        items = [{"id": i, "name": f"item_{i}", "data": "x" * 500} for i in range(100)]
        content = json.dumps(items, indent=2)

        result = maybe_spill(content, "list_schemas", 1, tmp_path)

        assert "100 items" in result
        # Preview shows first 3 items
        assert '"item_0"' in result
        assert '"item_1"' in result
        assert '"item_2"' in result
        assert "97 more items" in result

    def test_spill_json_object_summary(self, tmp_path: Path) -> None:
        obj = {f"key_{i}": f"value_{i}" * 200 for i in range(50)}
        content = json.dumps(obj, indent=2)

        result = maybe_spill(content, "get_schema", 2, tmp_path)

        assert "50 keys" in result
        assert "key_0" in result

    def test_spill_json_object_preserves_scalar_fields(self, tmp_path: Path) -> None:
        """Object summary should include all scalar values (IDs, names, URLs)."""
        obj = {
            "id": 12345,
            "name": "My Queue",
            "schema": "https://example.com/api/v1/schemas/67890",
            "active": True,
            "nested_data": {"large": "x" * 5000},
            "items": [1, 2, 3],
        }
        # Pad to exceed threshold
        obj["extra_data"] = "y" * SPILLOVER_THRESHOLD
        content = json.dumps(obj)

        result = maybe_spill(content, "create_queue", 1, tmp_path)

        # All scalar values preserved (URL extracted to numeric ID)
        assert "12345" in result
        assert "My Queue" in result
        assert "67890" in result
        assert "true" in result.lower() or "True" in result
        # Nested keys listed for jq access
        assert "nested_data" in result
        assert "items" in result

    def test_spill_plain_text_summary(self, tmp_path: Path) -> None:
        content = "line content here\n" * 3000

        result = maybe_spill(content, "some_tool", 1, tmp_path)

        assert "3001 lines" in result
        assert str(len(content)) + " chars" in result

    def test_spill_file_naming(self, tmp_path: Path) -> None:
        content = "z" * (SPILLOVER_THRESHOLD + 1)

        maybe_spill(content, "search", 7, tmp_path)
        assert (tmp_path / "workspace" / "step7_search.json").is_file()

    def test_spill_file_naming_uses_tool_call_id_to_avoid_overwrite(self, tmp_path: Path) -> None:
        first_content = "a" * (SPILLOVER_THRESHOLD + 1)
        second_content = "b" * (SPILLOVER_THRESHOLD + 1)

        first_result = maybe_spill(first_content, "search", 7, tmp_path, "toolu_01")
        second_result = maybe_spill(second_content, "search", 7, tmp_path, "toolu_02")

        workspace = tmp_path / "workspace"
        first_file = workspace / "step7_search_toolu_01.json"
        second_file = workspace / "step7_search_toolu_02.json"

        assert first_file.is_file()
        assert second_file.is_file()
        assert first_file.read_text() == first_content
        assert second_file.read_text() == second_content
        assert str(first_file) in first_result
        assert str(second_file) in second_result

    def test_spill_json_array_small_array(self, tmp_path: Path) -> None:
        """Array with fewer than 3 items should show all without 'more items'."""
        items = [{"id": 1}, {"id": 2}]
        # Pad to exceed threshold
        items[0]["data"] = "x" * SPILLOVER_THRESHOLD
        content = json.dumps(items)

        result = maybe_spill(content, "tool", 1, tmp_path)

        assert "2 items" in result
        assert "more items" not in result


class TestIdFromUrl:
    def test_extracts_numeric_id(self) -> None:
        assert _id_from_url("https://elis.rossum.ai/api/v1/queues/42") == 42

    def test_non_url_passthrough(self) -> None:
        assert _id_from_url("hello") == "hello"
        assert _id_from_url(123) == 123

    def test_trailing_slash(self) -> None:
        assert _id_from_url("https://elis.rossum.ai/api/v1/queues/42/") == 42

    def test_non_numeric_id(self) -> None:
        url = "https://example.com/api/abc"
        assert _id_from_url(url) == url


class TestSummarizeObjectDeep:
    """Tests for the generic object summarizer that recurses one level into nested dicts."""

    def test_extracts_nested_dict_scalars(self) -> None:
        obj = {
            "entity": "queue",
            "id": 123,
            "data": {
                "name": "Invoices - Brazil",
                "status": "active",
                "settings": {"large": "x" * 5000},
            },
        }
        content = json.dumps(obj)
        result = _summarize(content, "/mock/test.json")

        assert "entity: queue" in result
        assert "id: 123" in result
        assert "data.name: Invoices - Brazil" in result
        assert "data.status: active" in result
        assert "data: settings" in result

    def test_url_to_id_extraction(self) -> None:
        obj = {
            "id": 1,
            "workspace": "https://api.example.com/v1/workspaces/804135",
            "data": {
                "schema": "https://api.example.com/v1/schemas/2117537",
            },
        }
        content = json.dumps(obj)
        result = _summarize(content, "/mock/test.json")

        assert "workspace: 804135" in result
        assert "data.schema: 2117537" in result

    def test_nested_list_counts(self) -> None:
        obj = {
            "id": 1,
            "data": {
                "name": "Test",
                "hooks": [{"id": 1}, {"id": 2}, {"id": 3}],
            },
        }
        content = json.dumps(obj)
        result = _summarize(content, "/mock/test.json")

        assert "data: hooks (3 items)" in result

    def test_top_level_list_counts(self) -> None:
        obj = {"id": 1, "items": [1, 2, 3, 4, 5]}
        content = json.dumps(obj)
        result = _summarize(content, "/mock/test.json")

        assert "items (5 items)" in result

    def test_truncates_excess_scalar_fields(self) -> None:
        data = {f"field_{i}": f"value_{i}" for i in range(30)}
        obj = {"id": 1, "data": data}
        content = json.dumps(obj)
        result = _summarize(content, "/mock/test.json")

        # 1 top-level scalar + 30 nested = 31 total, capped at 20
        assert "... (" in result
        assert "more)" in result

    def test_truncates_long_string_values(self) -> None:
        obj = {"id": 1, "long_field": "x" * 200}
        content = json.dumps(obj)
        result = _summarize(content, "/mock/test.json")

        assert "long_field: " in result
        assert "..." in result

    def test_get_tool_uses_generic_deep_summary(self) -> None:
        """get() results use the generic deep summarizer (no entity-specific logic)."""
        obj = {
            "entity": "queue",
            "id": 123,
            "data": {
                "name": "My Queue",
                "workspace": "https://api.example.com/v1/workspaces/804135",
                "automation_enabled": True,
            },
        }
        content = json.dumps(obj)
        result = _summarize(content, "/mock/test.json", "get")

        assert "data.name: My Queue" in result
        assert "data.workspace: 804135" in result
        assert "data.automation_enabled: True" in result


class TestSummarizeSearchResult:
    """Tests for _summarize with tool_name='search'."""

    def test_queue_search(self) -> None:
        items = [
            {
                "id": 42,
                "name": "Invoices - Brazil",
                "automation_enabled": True,
                "status": "active",
            },
            {
                "id": 43,
                "name": "Invoices - Germany",
                "automation_enabled": True,
                "status": "active",
            },
            {
                "id": 44,
                "name": "POs - US",
                "automation_enabled": False,
                "status": "inactive",
            },
        ]
        content = json.dumps(items)
        result = _summarize(content, "/mock/test.json", "search")

        assert "3 queues" in result
        assert "id=42" in result
        assert "name=Invoices - Brazil" in result
        assert "status=active" in result

    def test_empty_search(self) -> None:
        content = json.dumps([])
        result = _summarize(content, "/mock/test.json", "search")

        assert "0 results" in result

    def test_hook_log_search_with_aggregations(self) -> None:
        items = [
            {
                "hook": "h1",
                "hook_id": 10,
                "level": "ERROR",
                "status_code": 500,
                "timestamp": "2024-01-01",
                "message": "fail",
            },
            {
                "hook": "h1",
                "hook_id": 10,
                "level": "ERROR",
                "status_code": 500,
                "timestamp": "2024-01-02",
                "message": "fail again",
            },
            {
                "hook": "h2",
                "hook_id": 20,
                "level": "INFO",
                "status_code": 200,
                "timestamp": "2024-01-03",
                "message": "ok",
            },
        ]
        content = json.dumps(items)
        result = _summarize(content, "/mock/test.json", "search")

        assert "3 hook_logs" in result
        assert "Aggregations:" in result
        assert "errors: 2" in result
        assert "unique hook IDs: 2" in result
        assert "500" in result

    def test_annotation_search_with_status_aggregation(self) -> None:
        items = [
            {"id": 1, "status": "confirmed", "queue": "q1", "document": "d1"},
            {"id": 2, "status": "confirmed", "queue": "q1", "document": "d2"},
            {"id": 3, "status": "to_review", "queue": "q1", "document": "d3"},
        ]
        content = json.dumps(items)
        result = _summarize(content, "/mock/test.json", "search")

        assert "3 annotations" in result
        assert "by status:" in result
        assert "confirmed (2)" in result
        assert "to_review (1)" in result

    def test_user_search(self) -> None:
        items = [
            {"id": 1, "username": "alice", "email": "alice@example.com"},
            {"id": 2, "username": "bob", "email": "bob@example.com"},
        ]
        content = json.dumps(items)
        result = _summarize(content, "/mock/test.json", "search")

        assert "2 users" in result
        assert "username=alice" in result

    def test_unknown_entity_shows_scalar_fields(self) -> None:
        items = [
            {"id": 1, "foo": "bar", "count": 5},
            {"id": 2, "foo": "baz", "count": 10},
        ]
        content = json.dumps(items)
        result = _summarize(content, "/mock/test.json", "search")

        assert "2 items" in result
        assert "id=1" in result
        assert "foo=bar" in result

    def test_search_truncates_long_values(self) -> None:
        items = [{"id": 1, "name": "x" * 100}]
        content = json.dumps(items)
        result = _summarize(content, "/mock/test.json", "search")

        assert "..." in result


class TestToolSummaryFallback:
    """Verify unknown tool names use generic summarizers."""

    def test_unknown_tool_uses_generic_array(self) -> None:
        items = [{"id": i} for i in range(5)]
        content = json.dumps(items)
        result = _summarize(content, "/mock/test.json", "list_something")

        assert "5 items" in result
        assert "Preview:" in result

    def test_unknown_tool_uses_generic_object(self) -> None:
        obj = {"key": "value", "nested": {"a": 1}}
        content = json.dumps(obj)
        result = _summarize(content, "/mock/test.json", "create_queue")

        assert "object with 2 keys" in result

    def test_empty_tool_name_uses_generic(self) -> None:
        items = [{"id": i} for i in range(5)]
        content = json.dumps(items)
        result = _summarize(content, "/mock/test.json", "")

        assert "5 items" in result

    def test_get_tool_falls_through_to_generic(self) -> None:
        """get() has no special summarizer — uses generic deep object summary."""
        obj = {"entity": "queue", "id": 1, "data": {"name": "Test"}}
        content = json.dumps(obj)
        result = _summarize(content, "/mock/test.json", "get")

        assert "object with 3 keys" in result
        assert "data.name: Test" in result

    def test_get_annotation_content_falls_through_to_generic(self) -> None:
        """get_annotation_content() returns a file path dict — no special handling."""
        obj = {"path": "/tmp/annotation_123.json"}
        content = json.dumps(obj)
        result = _summarize(content, "/mock/test.json", "get_annotation_content")

        assert "object with 1 keys" in result

    def test_get_schema_tree_structure_falls_through_to_generic(self) -> None:
        """get_schema_tree_structure() uses generic array summary."""
        items = [
            {"id": "s1", "label": "Section", "category": "section"},
            {"id": "f1", "label": "Field", "category": "datapoint"},
        ]
        content = json.dumps(items)
        result = _summarize(content, "/mock/test.json", "get_schema_tree_structure")

        assert "2 items" in result
        assert "Preview:" in result
