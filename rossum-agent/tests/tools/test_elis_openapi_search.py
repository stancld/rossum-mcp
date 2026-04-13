"""Tests for OpenAPI search tools (inlined in subagents/elis_docs.py)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import rossum_agent.tools.subagents.elis_docs as openapi_module
from rossum_agent.tools.subagents.elis_docs import SpecCache

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _reset_spec_cache():
    """Reset the module-level cache singleton between tests."""
    openapi_module._cache = SpecCache()
    yield
    openapi_module._cache = SpecCache()


class TestElisOpenapiJq:
    """Tests for elis_openapi_jq tool."""

    @pytest.fixture
    def mock_spec_file(self, tmp_path: Path) -> Path:
        """Create a mock OpenAPI spec file."""
        spec = {
            "openapi": "3.0.0",
            "paths": {
                "/v1/queues": {"get": {"summary": "List queues"}},
                "/v1/queues/{id}": {"get": {"summary": "Get queue"}},
            },
            "components": {"schemas": {"Queue": {"type": "object", "properties": {"name": {"type": "string"}}}}},
        }
        spec_path = tmp_path / "rossum_elis_openapi.json"
        spec_path.write_text(json.dumps(spec))
        return spec_path

    def test_jq_query_success(self, mock_spec_file: Path) -> None:
        """Test successful jq query execution."""
        openapi_module._cache = SpecCache(mock_spec_file)
        result = json.loads(openapi_module.elis_openapi_jq(".openapi"))
        assert result["status"] == "success"
        assert "3.0.0" in result["result"]

    def test_jq_query_list_paths(self, mock_spec_file: Path) -> None:
        """Test listing paths from OpenAPI spec."""
        openapi_module._cache = SpecCache(mock_spec_file)
        result = json.loads(openapi_module.elis_openapi_jq(".paths | keys"))
        assert result["status"] == "success"
        assert "/v1/queues" in result["result"]

    def test_jq_invalid_query(self, mock_spec_file: Path) -> None:
        """Test that invalid jq query returns error."""
        openapi_module._cache = SpecCache(mock_spec_file)
        result = json.loads(openapi_module.elis_openapi_jq(".invalid["))
        assert result["status"] == "error"
        assert "jq error" in result["message"]

    def test_jq_spec_load_error(self) -> None:
        """Test error when spec cannot be loaded."""
        with patch.object(SpecCache, "load", side_effect=OSError("Disk read error")):
            result = json.loads(openapi_module.elis_openapi_jq("."))
            assert result["status"] == "error"
            assert "Disk read error" in result["message"]


class TestElisOpenapiGrep:
    """Tests for elis_openapi_grep tool."""

    @pytest.fixture
    def mock_spec_file(self, tmp_path: Path) -> Path:
        """Create a mock OpenAPI spec file with searchable content."""
        spec = {
            "openapi": "3.0.0",
            "paths": {
                "/v1/queues": {"get": {"summary": "List queues", "description": "Returns all queues with pagination"}},
                "/v1/annotations": {"get": {"summary": "List annotations"}},
            },
        }
        spec_path = tmp_path / "rossum_elis_openapi.json"
        spec_path.write_text(json.dumps(spec, indent=2))
        return spec_path

    def test_grep_finds_pattern(self, mock_spec_file: Path) -> None:
        """Test successful pattern search."""
        openapi_module._cache = SpecCache(mock_spec_file)
        result = json.loads(openapi_module.elis_openapi_grep("pagination"))
        assert result["status"] == "success"
        assert result["matches"] > 0
        assert any("pagination" in m["value"].lower() for m in result["result"])

    def test_grep_no_matches(self, mock_spec_file: Path) -> None:
        """Test when pattern has no matches."""
        openapi_module._cache = SpecCache(mock_spec_file)
        result = json.loads(openapi_module.elis_openapi_grep("nonexistentpattern12345"))
        assert result["status"] == "success"
        assert "No matches found" in result["result"]

    def test_grep_case_insensitive(self, mock_spec_file: Path) -> None:
        """Test case insensitive search."""
        openapi_module._cache = SpecCache(mock_spec_file)
        result = json.loads(openapi_module.elis_openapi_grep("PAGINATION", case_insensitive=True))
        assert result["status"] == "success"
        assert result["matches"] > 0

    def test_grep_case_sensitive(self, mock_spec_file: Path) -> None:
        """Test case sensitive search."""
        openapi_module._cache = SpecCache(mock_spec_file)
        result = json.loads(openapi_module.elis_openapi_grep("PAGINATION", case_insensitive=False))
        assert result["status"] == "success"
        assert "No matches found" in result["result"]

    def test_grep_correct_match_count(self, mock_spec_file: Path) -> None:
        """Test that match count reflects actual matches."""
        openapi_module._cache = SpecCache(mock_spec_file)
        result = json.loads(openapi_module.elis_openapi_grep("List"))
        assert result["status"] == "success"
        # "List queues" and "List annotations" in summary fields
        assert result["matches"] == 2

    def test_grep_invalid_regex(self, mock_spec_file: Path) -> None:
        """Test that invalid regex returns error."""
        openapi_module._cache = SpecCache(mock_spec_file)
        result = json.loads(openapi_module.elis_openapi_grep("[invalid"))
        assert result["status"] == "error"
        assert "Invalid regex" in result["message"]

    def test_grep_spec_load_error(self) -> None:
        """Test error when spec cannot be loaded."""
        with patch.object(SpecCache, "load", side_effect=OSError("Disk read error")):
            result = json.loads(openapi_module.elis_openapi_grep("pattern"))
            assert result["status"] == "error"
            assert "Disk read error" in result["message"]

    def test_grep_returns_json_paths(self, mock_spec_file: Path) -> None:
        """Test that grep results include JSON paths for context."""
        openapi_module._cache = SpecCache(mock_spec_file)
        result = json.loads(openapi_module.elis_openapi_grep("pagination"))
        assert result["status"] == "success"
        assert all("path" in m and "value" in m for m in result["result"])
        assert any("description" in m["path"] for m in result["result"])

    def test_grep_ignores_json_structure(self, mock_spec_file: Path) -> None:
        """Test that grep doesn't match JSON keys like 'type' or 'object'."""
        openapi_module._cache = SpecCache(mock_spec_file)
        # "openapi" appears as a key but not in any searchable field value
        result = json.loads(openapi_module.elis_openapi_grep("3\\.0\\.0"))
        assert result["status"] == "success"
        # Should not find matches - "3.0.0" is only in the "openapi" key's value,
        # which is not in _SEARCHABLE_KEYS (openapi is not a meaningful search field)
        assert "No matches found" in result["result"]


class TestExtractSpecFromRedocly:
    """Tests for _extract_spec_from_redocly function."""

    def test_extract_valid_redocly_html(self) -> None:
        """Test extracting spec from valid Redocly HTML."""
        html = """
        <html>
        <script>
        var __redoc_state = {"spec": {"data": {"openapi": "3.0.0", "info": {"title": "Test"}}}};
        </script>
        </html>
        """
        spec = openapi_module._extract_spec_from_redocly(html)
        assert spec["openapi"] == "3.0.0"
        assert spec["info"]["title"] == "Test"

    def test_extract_missing_redoc_state(self) -> None:
        """Test error when __redoc_state is missing."""
        html = "<html><body>No redoc state here</body></html>"
        with pytest.raises(ValueError, match="Could not find __redoc_state"):
            openapi_module._extract_spec_from_redocly(html)

    def test_extract_invalid_spec(self) -> None:
        """Test error when extracted data is not OpenAPI spec."""
        html = 'var __redoc_state = {"spec": {"data": {"notOpenapi": true}}};'
        with pytest.raises(ValueError, match="does not contain OpenAPI spec"):
            openapi_module._extract_spec_from_redocly(html)

    def test_extract_handles_escaped_backslashes(self) -> None:
        """Test that escaped backslashes in JSON strings are parsed correctly."""
        html = r'var __redoc_state = {"spec": {"data": {"openapi": "3.0.0", "info": {"title": "path\\to\\thing"}}}};'
        spec = openapi_module._extract_spec_from_redocly(html)
        assert spec["openapi"] == "3.0.0"
        assert spec["info"]["title"] == "path\\to\\thing"

    def test_extract_no_json_after_redoc_state(self) -> None:
        """Test error when no JSON object follows __redoc_state."""
        html = "var __redoc_state = not_json;"
        with pytest.raises(ValueError, match="Could not find JSON object"):
            openapi_module._extract_spec_from_redocly(html)


class TestSpecCacheEnsureDownloaded:
    """Tests for SpecCache._ensure_downloaded method."""

    def test_uses_cached_file(self, tmp_path: Path) -> None:
        """Test that cached file is used when valid."""
        cache_file = tmp_path / "rossum_elis_openapi.json"
        cache_file.write_text('{"openapi": "3.0.0"}')
        cache = SpecCache(cache_file)
        result = cache._ensure_downloaded()
        assert result == cache_file

    def test_downloads_fresh_spec(self, tmp_path: Path) -> None:
        """Test downloading fresh spec when cache doesn't exist."""
        cache_file = tmp_path / "rossum_elis_openapi.json"
        cache = SpecCache(cache_file)

        mock_response = MagicMock()
        mock_response.text = '{"openapi": "3.0.0", "info": {"title": "Test"}}'
        mock_response.raise_for_status = MagicMock()

        with patch("rossum_agent.tools.subagents.elis_docs.httpx.get", return_value=mock_response):
            result = cache._ensure_downloaded()
            assert result == cache_file
            assert cache_file.exists()

    def test_redownloads_if_cache_expired(self, tmp_path: Path) -> None:
        """Test that expired cache (>24h) triggers re-download."""
        import os

        cache_file = tmp_path / "rossum_elis_openapi.json"
        cache_file.write_text('{"openapi": "3.0.0"}')
        old_mtime = cache_file.stat().st_mtime - (25 * 60 * 60)
        os.utime(cache_file, (old_mtime, old_mtime))

        mock_response = MagicMock()
        mock_response.text = '{"openapi": "3.1.0", "info": {"title": "Updated"}}'
        mock_response.raise_for_status = MagicMock()

        cache = SpecCache(cache_file)
        with patch("rossum_agent.tools.subagents.elis_docs.httpx.get", return_value=mock_response):
            result = cache._ensure_downloaded()
            assert result == cache_file
            content = json.loads(cache_file.read_text())
            assert content["openapi"] == "3.1.0"

    def test_extracts_from_redocly_html(self, tmp_path: Path) -> None:
        """Test extracting spec from Redocly HTML response."""
        cache_file = tmp_path / "rossum_elis_openapi.json"
        cache = SpecCache(cache_file)

        html = 'var __redoc_state = {"spec": {"data": {"openapi": "3.0.0", "info": {"title": "Rossum"}}}};'
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch("rossum_agent.tools.subagents.elis_docs.httpx.get", return_value=mock_response):
            result = cache._ensure_downloaded()
            assert result == cache_file
            content = json.loads(cache_file.read_text())
            assert content["openapi"] == "3.0.0"


class TestSpecCacheLoad:
    """Tests for SpecCache.load method."""

    def test_loads_and_caches_spec(self, tmp_path: Path) -> None:
        """Test that spec is loaded and cached in memory."""
        cache_file = tmp_path / "rossum_elis_openapi.json"
        spec = {"openapi": "3.0.0", "paths": {}}
        cache_file.write_text(json.dumps(spec))

        cache = SpecCache(cache_file)
        result_spec = cache.load()
        assert result_spec == spec
        assert cache._spec == spec

    def test_uses_memory_cache_on_second_call(self, tmp_path: Path) -> None:
        """Test that second call uses in-memory cache (same object returned)."""
        cache_file = tmp_path / "rossum_elis_openapi.json"
        spec = {"openapi": "3.0.0", "paths": {}}
        cache_file.write_text(json.dumps(spec))

        cache = SpecCache(cache_file)
        spec1 = cache.load()
        spec2 = cache.load()
        assert spec1 is spec2

    def test_redownloads_if_cache_corrupt(self, tmp_path: Path) -> None:
        """Test that corrupt cache triggers re-download."""
        cache_file = tmp_path / "rossum_elis_openapi.json"
        cache_file.write_text("not valid json")

        mock_response = MagicMock()
        mock_response.text = '{"openapi": "3.0.0"}'
        mock_response.raise_for_status = MagicMock()

        cache = SpecCache(cache_file)
        with patch("rossum_agent.tools.subagents.elis_docs.httpx.get", return_value=mock_response):
            spec = cache.load()
            assert spec["openapi"] == "3.0.0"


class TestTruncateOutput:
    """Tests for truncate_output function."""

    def test_no_truncation_within_limit(self) -> None:
        """Test that output within limit is returned unchanged."""
        output = "short output"
        assert openapi_module.truncate_output(output, 100) == output

    def test_truncates_at_line_boundary(self) -> None:
        """Test that truncation happens at a line boundary."""
        output = "line1\nline2\nline3\nline4\nline5"
        result = openapi_module.truncate_output(output, 15)
        assert result.endswith("\n... (truncated)")
        content_before_marker = result.split("\n... (truncated)")[0]
        assert content_before_marker == "line1\nline2"

    def test_falls_back_to_char_limit_for_single_long_line(self) -> None:
        """Test char-based truncation when no line boundary found."""
        output = "x" * 100
        result = openapi_module.truncate_output(output, 50)
        assert len(result) == 50 + len("\n... (truncated)")
        assert result.endswith("\n... (truncated)")


class TestJqOutputTruncation:
    """Tests for jq output truncation."""

    def test_jq_truncates_long_output(self, tmp_path: Path) -> None:
        """Test that jq output exceeding limit is truncated."""
        spec = {"openapi": "3.0.0", "data": {f"key_{i}": "v" * 200 for i in range(500)}}
        cache_file = tmp_path / "rossum_elis_openapi.json"
        cache_file.write_text(json.dumps(spec))

        openapi_module._cache = SpecCache(cache_file)
        result = json.loads(openapi_module.elis_openapi_jq(".data"))
        assert result["status"] == "success"
        assert "truncated" in result["result"]


class TestGrepEdgeCases:
    """Tests for grep edge cases (truncation, errors)."""

    def test_grep_truncates_long_output(self, tmp_path: Path) -> None:
        """Test that grep output with many matches is truncated."""
        spec = {"openapi": "3.0.0", "paths": {}}
        for i in range(500):
            spec["paths"][f"/v1/endpoint_{i}"] = {"get": {"summary": f"Get item_{i} details"}}
        cache_file = tmp_path / "rossum_elis_openapi.json"
        cache_file.write_text(json.dumps(spec, indent=2))

        openapi_module._cache = SpecCache(cache_file)
        result = json.loads(openapi_module.elis_openapi_grep("item_"))
        assert result["status"] == "success"
        assert isinstance(result["result"], list)
        assert any("more matches" in m.get("value", "") for m in result["result"])


class TestWalkStringValues:
    """Tests for _walk_string_values function."""

    def test_walks_simple_dict(self) -> None:
        """Test walking a simple dict."""
        obj = {"summary": "Hello", "description": "World"}
        results = openapi_module._walk_string_values(obj, keys_filter=openapi_module._SEARCHABLE_KEYS)
        assert len(results) == 2
        paths = {r[0] for r in results}
        assert "$.summary" in paths
        assert "$.description" in paths

    def test_ignores_non_searchable_keys(self) -> None:
        """Test that non-searchable keys like 'type' are ignored."""
        obj = {"type": "object", "summary": "A queue", "properties": {"name": {"type": "string"}}}
        results = openapi_module._walk_string_values(obj, keys_filter=openapi_module._SEARCHABLE_KEYS)
        values = [r[1] for r in results]
        assert "A queue" in values
        assert "object" not in values
        assert "string" not in values

    def test_walks_nested_structure(self) -> None:
        """Test walking nested dicts and lists."""
        obj = {"paths": {"/v1/queues": {"get": {"summary": "List queues", "description": "Returns paginated queues"}}}}
        results = openapi_module._walk_string_values(obj, keys_filter=openapi_module._SEARCHABLE_KEYS)
        assert len(results) == 2
        assert any("List queues" in r[1] for r in results)
        assert any("paginated" in r[1] for r in results)

    def test_walks_lists(self) -> None:
        """Test walking lists of strings."""
        obj = {"enum": ["active", "inactive", "deleted"]}
        results = openapi_module._walk_string_values(obj, keys_filter=openapi_module._SEARCHABLE_KEYS)
        # enum is in _SEARCHABLE_KEYS but its value is a list, so the list items are walked
        values = [r[1] for r in results]
        assert "active" in values
        assert "inactive" in values
        assert "deleted" in values

    def test_stops_at_max_depth(self) -> None:
        """Test that recursion stops at _MAX_WALK_DEPTH."""
        # Build a structure deeper than the limit
        obj: dict = {"summary": "deep_leaf"}
        for _ in range(openapi_module._MAX_WALK_DEPTH + 10):
            obj = {"nested": obj}

        results = openapi_module._walk_string_values(obj, keys_filter=openapi_module._SEARCHABLE_KEYS)
        assert len(results) == 0


@pytest.mark.integration
class TestRealOpenapiSpec:
    """Integration tests that download the real Elis API OpenAPI spec.

    Run with: pytest -m integration
    """

    @pytest.fixture(scope="class")
    def real_spec_cache(self, tmp_path_factory: pytest.TempPathFactory) -> SpecCache:
        """Download the real OpenAPI spec once for all tests in this class."""
        cache_dir = tmp_path_factory.mktemp("openapi")
        cache_file = cache_dir / "rossum_elis_openapi.json"
        cache = SpecCache(cache_file)
        result = cache._ensure_downloaded()
        assert result.exists(), "OpenAPI spec was not downloaded"
        content = json.loads(result.read_text())
        assert "openapi" in content or "swagger" in content, "Downloaded file is not an OpenAPI spec"
        return cache

    def test_jq_list_paths(self, real_spec_cache: SpecCache) -> None:
        """Test listing all API paths from the real spec."""
        openapi_module._cache = real_spec_cache
        result = json.loads(openapi_module.elis_openapi_jq(".paths | keys"))
        assert result["status"] == "success"
        paths = json.loads(result["result"])
        assert isinstance(paths, list)
        assert len(paths) > 10, "Expected many API paths in the real spec"
        assert any("queue" in p for p in paths)
        assert any("annotation" in p for p in paths)

    def test_jq_get_queue_endpoint(self, real_spec_cache: SpecCache) -> None:
        """Test querying a specific endpoint from the real spec."""
        openapi_module._cache = real_spec_cache
        result = json.loads(
            openapi_module.elis_openapi_jq('.paths | to_entries | map(select(.key | contains("queue"))) | map(.key)')
        )
        assert result["status"] == "success"
        queue_paths = json.loads(result["result"])
        assert len(queue_paths) > 0, "Expected queue-related paths"

    def test_jq_schema_lookup(self, real_spec_cache: SpecCache) -> None:
        """Test looking up component schemas from the real spec."""
        openapi_module._cache = real_spec_cache
        result = json.loads(openapi_module.elis_openapi_jq(".components.schemas | keys | length"))
        assert result["status"] == "success"
        schema_count = int(result["result"].strip())
        assert schema_count > 5, "Expected multiple schemas in the real spec"

    def test_grep_finds_annotation(self, real_spec_cache: SpecCache) -> None:
        """Test grepping for 'annotation' in the real spec."""
        openapi_module._cache = real_spec_cache
        result = json.loads(openapi_module.elis_openapi_grep("annotation"))
        assert result["status"] == "success"
        assert result["matches"] > 0, "Expected matches for 'annotation'"

    def test_grep_finds_queue(self, real_spec_cache: SpecCache) -> None:
        """Test grepping for 'queue' in the real spec."""
        openapi_module._cache = real_spec_cache
        result = json.loads(openapi_module.elis_openapi_grep("queue"))
        assert result["status"] == "success"
        assert result["matches"] > 0

    def test_grep_case_sensitive_vs_insensitive(self, real_spec_cache: SpecCache) -> None:
        """Test that case sensitivity works against real spec."""
        openapi_module._cache = real_spec_cache
        insensitive = json.loads(openapi_module.elis_openapi_grep("QUEUE", case_insensitive=True))
        sensitive = json.loads(openapi_module.elis_openapi_grep("QUEUE", case_insensitive=False))

        assert insensitive["status"] == "success"
        assert sensitive["status"] == "success"
        insensitive_matches = insensitive.get("matches", 0)
        sensitive_matches = sensitive.get("matches", 0) if isinstance(sensitive.get("result"), list) else 0
        assert insensitive_matches >= sensitive_matches
