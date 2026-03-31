"""Tests for rossum_agent.agent.spillover module."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rossum_agent.agent.spillover import SPILLOVER_THRESHOLD, maybe_spill

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

        assert "total_results: 100" in result
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
        content = json.dumps(obj)
        # Pad to exceed threshold
        obj["extra_data"] = "y" * SPILLOVER_THRESHOLD
        content = json.dumps(obj)

        result = maybe_spill(content, "create_queue", 1, tmp_path)

        # All scalar values preserved
        assert "12345" in result
        assert "My Queue" in result
        assert "schemas/67890" in result
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

        assert "total_results: 2" in result
        assert "more items" not in result
