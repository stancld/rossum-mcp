"""Tests for data_tools module (general-purpose jq and grep)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from rossum_agent.tools.data_tools import _GREP_MATCH_LIMIT, _JQ_OUTPUT_LIMIT, run_grep, run_jq


class TestResolveContent:
    def test_jq_reads_file_path(self, tmp_path: Path) -> None:
        data = [{"id": 1, "status": "active"}, {"id": 2, "status": "inactive"}]
        f = tmp_path / "data.json"
        f.write_text(json.dumps(data))
        result = json.loads(run_jq('.[] | select(.status == "active") | .id', str(f)))
        assert result["status"] == "success"
        assert result["result"] == 1

    def test_grep_reads_file_path(self, tmp_path: Path) -> None:
        f = tmp_path / "content.txt"
        f.write_text("hello world\nfoo bar\nhello again")
        result = json.loads(run_grep("hello", str(f)))
        assert result["status"] == "success"
        assert result["matches"] == 2

    def test_jq_falls_back_to_raw_string_when_no_file(self) -> None:
        # A path that doesn't exist should be treated as raw JSON
        data = json.dumps({"key": "value"})
        result = json.loads(run_jq(".key", data))
        assert result["status"] == "success"
        assert result["result"] == "value"

    def test_grep_falls_back_to_raw_string_when_no_file(self) -> None:
        result = json.loads(run_grep("hello", "hello world\nfoo bar"))
        assert result["status"] == "success"
        assert result["matches"] == 1

    def test_jq_accepts_dict_data(self) -> None:
        data = {"content": [{"id": "vendor_match", "type": "enum"}]}
        result = json.loads(run_jq('[.. | objects | select(.id == "vendor_match")] | .[0].type', data))
        assert result["status"] == "success"
        assert result["result"] == "enum"

    def test_jq_on_annotation_content_path_pattern(self, tmp_path: Path) -> None:
        # Mirrors the real-world case: get_annotation_content returns a /tmp path
        annotation = [{"schema_id": "amount_total", "value": "100.00"}]
        f = tmp_path / "rossum_annotation_34537548_content.json"
        f.write_text(json.dumps(annotation))
        result = json.loads(run_jq('.[] | select(.schema_id == "amount_total") | .value', str(f)))
        assert result["status"] == "success"
        assert result["result"] == "100.00"


class TestRunJq:
    def test_simple_field_extraction(self) -> None:
        data = json.dumps({"name": "Alice", "age": 30})
        result = json.loads(run_jq(".name", data))
        assert result["status"] == "success"
        assert result["result"] == "Alice"

    def test_array_filter(self) -> None:
        data = json.dumps([{"id": 1, "active": True}, {"id": 2, "active": False}])
        result = json.loads(run_jq(".[] | select(.active) | .id", data))
        assert result["status"] == "success"
        assert result["result"] == 1

    def test_keys_query(self) -> None:
        data = json.dumps({"a": 1, "b": 2, "c": 3})
        result = json.loads(run_jq("keys", data))
        assert result["status"] == "success"
        assert result["result"] == ["a", "b", "c"]

    def test_invalid_json_input(self) -> None:
        result = json.loads(run_jq(".", "not json"))
        assert result["status"] == "error"
        assert "Invalid JSON" in result["message"]

    def test_invalid_jq_expression(self) -> None:
        data = json.dumps({"x": 1})
        result = json.loads(run_jq(".invalid[", data))
        assert result["status"] == "error"
        assert "jq error" in result["message"]

    def test_truncates_long_output(self) -> None:
        data = json.dumps({f"key_{i}": "v" * 200 for i in range(500)})
        result = json.loads(run_jq(".", data))
        assert result["status"] == "success"
        assert result["truncated"] is True
        assert isinstance(result["result"], str)
        assert result["result"].endswith("... (truncated)")
        assert len(result["result"]) <= _JQ_OUTPUT_LIMIT + len("\n... (truncated)")

    def test_nested_extraction(self) -> None:
        data = json.dumps({"a": {"b": {"c": 42}}})
        result = json.loads(run_jq(".a.b.c", data))
        assert result["status"] == "success"
        assert result["result"] == 42

    def test_map_field(self) -> None:
        data = json.dumps([{"id": 10}, {"id": 20}, {"id": 30}])
        result = json.loads(run_jq("map(.id)", data))
        assert result["status"] == "success"
        assert result["result"] == [10, 20, 30]


class TestRunGrep:
    def test_finds_matching_lines(self) -> None:
        text = "hello world\nfoo bar\nhello again"
        result = json.loads(run_grep("hello", text))
        assert result["status"] == "success"
        assert result["matches"] == 2
        lines = [m["text"] for m in result["result"]]
        assert "hello world" in lines
        assert "hello again" in lines

    def test_no_matches(self) -> None:
        text = "line one\nline two\nline three"
        result = json.loads(run_grep("nonexistent", text))
        assert result["status"] == "success"
        assert "No matches found" in result["result"]

    def test_case_insensitive_by_default(self) -> None:
        text = "Hello World\nfoo bar"
        result = json.loads(run_grep("HELLO", text))
        assert result["status"] == "success"
        assert result["matches"] == 1

    def test_case_sensitive(self) -> None:
        text = "Hello World\nhello world"
        result = json.loads(run_grep("Hello", text, case_insensitive=False))
        assert result["status"] == "success"
        assert result["matches"] == 1
        assert result["result"][0]["text"] == "Hello World"

    def test_returns_line_numbers(self) -> None:
        text = "first\nsecond\nthird\nfourth"
        result = json.loads(run_grep("third", text))
        assert result["status"] == "success"
        assert result["result"][0]["line"] == 3

    def test_invalid_regex(self) -> None:
        result = json.loads(run_grep("[invalid", "some text"))
        assert result["status"] == "error"
        assert "Invalid regex" in result["message"]

    def test_regex_pattern(self) -> None:
        text = "error: 404\ninfo: ok\nerror: 500\nwarning: slow"
        result = json.loads(run_grep(r"error: \d+", text))
        assert result["status"] == "success"
        assert result["matches"] == 2

    def test_truncates_many_matches(self) -> None:
        text = "\n".join(f"match line {i}" for i in range(_GREP_MATCH_LIMIT + 50))
        result = json.loads(run_grep("match", text))
        assert result["status"] == "success"
        assert result["matches"] == _GREP_MATCH_LIMIT
        # Last entry is the truncation notice
        assert "more matches" in result["result"][-1]["text"]

    def test_empty_text(self) -> None:
        result = json.loads(run_grep("anything", ""))
        assert result["status"] == "success"
        assert "No matches found" in result["result"]

    def test_single_line_match(self) -> None:
        result = json.loads(run_grep("hello", "hello"))
        assert result["status"] == "success"
        assert result["matches"] == 1
        assert result["result"][0]["line"] == 1
