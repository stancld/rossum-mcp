"""Tests for rossum_agent.internal_tools module."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from rossum_agent.internal_tools import (
    debug_hook,
    evaluate_python_hook,
    execute_internal_tool,
    get_internal_tool_names,
    get_internal_tools,
    write_file,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestGetInternalTools:
    """Test get_internal_tools function."""

    def test_returns_list_of_tools(self):
        """Test that get_internal_tools returns a list of tool definitions."""
        tools = get_internal_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_contains_write_file_tool(self):
        """Test that the write_file tool is included."""
        tools = get_internal_tools()
        tool_names = [t["name"] for t in tools]
        assert "write_file" in tool_names

    def test_tool_has_required_fields(self):
        """Test that each tool has required fields for Anthropic format."""
        tools = get_internal_tools()
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert isinstance(tool["input_schema"], dict)


class TestGetInternalToolNames:
    """Test get_internal_tool_names function."""

    def test_returns_set_of_names(self):
        """Test that get_internal_tool_names returns a set."""
        names = get_internal_tool_names()
        assert isinstance(names, set)
        assert len(names) > 0

    def test_contains_write_file(self):
        """Test that write_file is in the set."""
        names = get_internal_tool_names()
        assert "write_file" in names


class TestWriteFileTool:
    """Test write_file tool definition."""

    def test_tool_name(self):
        """Test that the tool has the correct name."""
        tools = get_internal_tools()
        write_file_tool = next(t for t in tools if t["name"] == "write_file")
        assert write_file_tool["name"] == "write_file"

    def test_tool_has_description(self):
        """Test that the tool has a description."""
        tools = get_internal_tools()
        write_file_tool = next(t for t in tools if t["name"] == "write_file")
        assert "description" in write_file_tool
        assert len(write_file_tool["description"]) > 0

    def test_input_schema_has_required_properties(self):
        """Test that the input schema has required properties."""
        tools = get_internal_tools()
        write_file_tool = next(t for t in tools if t["name"] == "write_file")
        schema = write_file_tool["input_schema"]
        assert schema["type"] == "object"
        assert "filename" in schema["properties"]
        assert "content" in schema["properties"]
        assert "filename" in schema["required"]
        assert "content" in schema["required"]


class TestExecuteInternalTool:
    """Test execute_internal_tool function."""

    def test_executes_write_file(self, tmp_path: Path):
        """Test that execute_internal_tool calls write_file for write_file."""
        with patch("rossum_agent.internal_tools.get_session_output_dir", return_value=tmp_path):
            result = execute_internal_tool("write_file", {"filename": "test.txt", "content": "Hello World"})

        assert "Successfully wrote" in result
        assert (tmp_path / "test.txt").exists()
        assert (tmp_path / "test.txt").read_text() == "Hello World"

    def test_raises_for_unknown_tool(self):
        """Test that ValueError is raised for unknown tool names."""
        with pytest.raises(ValueError, match="Unknown internal tool"):
            execute_internal_tool("nonexistent_tool", {})

    def test_handles_missing_arguments(self, tmp_path: Path):
        """Test that missing arguments are handled gracefully."""
        with patch("rossum_agent.internal_tools.get_session_output_dir", return_value=tmp_path):
            result = execute_internal_tool("write_file", {"filename": "", "content": ""})

        assert "Error" in result


class TestWriteFile:
    """Test write_file function."""

    def test_writes_file_successfully(self, tmp_path: Path):
        """Test successful file write."""
        with patch("rossum_agent.internal_tools.get_session_output_dir", return_value=tmp_path):
            result = write_file("output.txt", "Test content here")

        assert "Successfully wrote" in result
        assert "17 characters" in result
        assert (tmp_path / "output.txt").exists()
        assert (tmp_path / "output.txt").read_text() == "Test content here"

    def test_writes_markdown_file(self, tmp_path: Path):
        """Test writing markdown content."""
        markdown_content = "# Header\n\n- Item 1\n- Item 2\n"
        with patch("rossum_agent.internal_tools.get_session_output_dir", return_value=tmp_path):
            result = write_file("report.md", markdown_content)

        assert "Successfully wrote" in result
        assert (tmp_path / "report.md").exists()
        assert (tmp_path / "report.md").read_text() == markdown_content

    def test_returns_error_when_filename_empty(self, tmp_path: Path):
        """Test that empty filename returns error."""
        with patch("rossum_agent.internal_tools.get_session_output_dir", return_value=tmp_path):
            result = write_file("", "Some content")

        assert "Error" in result
        assert "filename is required" in result

    def test_returns_error_when_content_empty(self, tmp_path: Path):
        """Test that empty content returns error."""
        with patch("rossum_agent.internal_tools.get_session_output_dir", return_value=tmp_path):
            result = write_file("test.txt", "")

        assert "Error" in result
        assert "content is required" in result

    def test_sanitizes_path_traversal_attempts(self, tmp_path: Path):
        """Test that path traversal attacks are prevented."""
        with patch("rossum_agent.internal_tools.get_session_output_dir", return_value=tmp_path):
            result = write_file("../../../etc/passwd", "malicious content")

        assert "Successfully wrote" in result
        assert not (tmp_path.parent / "etc" / "passwd").exists()
        assert (tmp_path / "passwd").exists()
        assert (tmp_path / "passwd").read_text() == "malicious content"

    def test_sanitizes_absolute_path(self, tmp_path: Path):
        """Test that absolute paths are converted to just filename."""
        with patch("rossum_agent.internal_tools.get_session_output_dir", return_value=tmp_path):
            result = write_file("/absolute/path/to/file.txt", "content")

        assert "Successfully wrote" in result
        assert (tmp_path / "file.txt").exists()

    def test_handles_unicode_content(self, tmp_path: Path):
        """Test writing unicode content."""
        unicode_content = "Hello 世界 🌍 مرحبا"
        with patch("rossum_agent.internal_tools.get_session_output_dir", return_value=tmp_path):
            result = write_file("unicode.txt", unicode_content)

        assert "Successfully wrote" in result
        assert (tmp_path / "unicode.txt").read_text(encoding="utf-8") == unicode_content

    def test_overwrites_existing_file(self, tmp_path: Path):
        """Test that existing files are overwritten."""
        (tmp_path / "existing.txt").write_text("old content")

        with patch("rossum_agent.internal_tools.get_session_output_dir", return_value=tmp_path):
            result = write_file("existing.txt", "new content")

        assert "Successfully wrote" in result
        assert (tmp_path / "existing.txt").read_text() == "new content"

    def test_handles_write_permission_error(self, tmp_path: Path):
        """Test handling of permission errors during write."""
        with (
            patch(
                "rossum_agent.internal_tools.get_session_output_dir",
                return_value=tmp_path,
            ),
            patch("pathlib.Path.write_text", side_effect=PermissionError("Access denied")),
        ):
            result = write_file("test.txt", "content")

        assert "Error" in result
        assert "Access denied" in result

    def test_returns_error_for_invalid_filename(self, tmp_path: Path):
        """Test that invalid filenames (just path components) return error."""
        with patch("rossum_agent.internal_tools.get_session_output_dir", return_value=tmp_path):
            result = write_file(".", "content")

        assert "Error" in result
        assert "invalid filename" in result.lower()

    def test_handles_special_characters_in_filename(self, tmp_path: Path):
        """Test handling of special characters in filename."""
        with patch("rossum_agent.internal_tools.get_session_output_dir", return_value=tmp_path):
            result = write_file("file with spaces.txt", "content")

        assert "Successfully wrote" in result
        assert (tmp_path / "file with spaces.txt").exists()


class TestEvaluatePythonHookTool:
    """Test evaluate_python_hook tool definition."""

    def test_tool_is_registered(self):
        """Test that evaluate_python_hook is in the internal tools list."""
        tools = get_internal_tools()
        tool_names = [t["name"] for t in tools]
        assert "evaluate_python_hook" in tool_names

    def test_tool_in_tool_names(self):
        """Test that evaluate_python_hook is in get_internal_tool_names."""
        names = get_internal_tool_names()
        assert "evaluate_python_hook" in names

    def test_tool_has_description(self):
        """Test that the tool has a description."""
        tools = get_internal_tools()
        eval_tool = next(t for t in tools if t["name"] == "evaluate_python_hook")
        assert "description" in eval_tool
        assert "debugging" in eval_tool["description"].lower()

    def test_input_schema_has_required_properties(self):
        """Test that the input schema has required properties."""
        tools = get_internal_tools()
        eval_tool = next(t for t in tools if t["name"] == "evaluate_python_hook")
        schema = eval_tool["input_schema"]
        assert schema["type"] == "object"
        assert "code" in schema["properties"]
        assert "annotation_json" in schema["properties"]
        assert "schema_json" in schema["properties"]
        assert "code" in schema["required"]
        assert "annotation_json" in schema["required"]


class TestEvaluatePythonHook:
    """Test evaluate_python_hook function."""

    def test_successful_hook_execution(self):
        """Test successful execution of a simple hook."""
        code = """
def rossum_hook_request_handler(payload):
    annotation = payload["annotation"]
    return {"status": "ok", "document_id": annotation.get("document_id")}
"""
        annotation_json = json.dumps({"document_id": 12345, "status": "to_review"})

        result_json = evaluate_python_hook(code, annotation_json)
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert result["result"] == {"status": "ok", "document_id": 12345}
        assert result["exception"] is None
        assert "elapsed_ms" in result

    def test_hook_with_schema(self):
        """Test hook execution with schema data."""
        code = """
def rossum_hook_request_handler(payload):
    schema = payload.get("schema", {})
    return {"has_schema": bool(schema), "fields": len(schema.get("fields", []))}
"""
        annotation_json = json.dumps({"document_id": 1})
        schema_json = json.dumps({"fields": [{"id": "invoice_id"}, {"id": "amount"}]})

        result_json = evaluate_python_hook(code, annotation_json, schema_json)
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert result["result"] == {"has_schema": True, "fields": 2}

    def test_captures_stdout(self):
        """Test that stdout from print statements is captured."""
        code = """
def rossum_hook_request_handler(payload):
    print("Debug: Processing annotation")
    print(f"Document ID: {payload['annotation']['document_id']}")
    return "done"
"""
        annotation_json = json.dumps({"document_id": 999})

        result_json = evaluate_python_hook(code, annotation_json)
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert "Debug: Processing annotation" in result["stdout"]
        assert "Document ID: 999" in result["stdout"]

    def test_handles_exception_in_hook(self):
        """Test that exceptions in hook code are captured."""
        code = """
def rossum_hook_request_handler(payload):
    missing_key = payload["nonexistent_key"]
    return missing_key
"""
        annotation_json = json.dumps({"document_id": 1})

        result_json = evaluate_python_hook(code, annotation_json)
        result = json.loads(result_json)

        assert result["status"] == "error"
        assert result["exception"] is not None
        assert result["exception"]["type"] == "KeyError"
        assert "nonexistent_key" in result["exception"]["message"]

    def test_handles_missing_handler_function(self):
        """Test error when rossum_hook_request_handler is not defined."""
        code = """
def some_other_function(payload):
    return payload
"""
        annotation_json = json.dumps({"document_id": 1})

        result_json = evaluate_python_hook(code, annotation_json)
        result = json.loads(result_json)

        assert result["status"] == "error"
        assert result["exception"] is not None
        assert "rossum_hook_request_handler" in result["exception"]["message"]

    def test_handles_syntax_error(self):
        """Test error handling for syntax errors in code."""
        code = """
def rossum_hook_request_handler(payload):
    if True
        return "missing colon"
"""
        annotation_json = json.dumps({"document_id": 1})

        result_json = evaluate_python_hook(code, annotation_json)
        result = json.loads(result_json)

        assert result["status"] == "error"
        assert result["exception"] is not None
        assert result["exception"]["type"] == "SyntaxError"

    def test_handles_invalid_annotation_json(self):
        """Test error handling for invalid annotation JSON."""
        code = "def rossum_hook_request_handler(payload): return payload"
        annotation_json = "not valid json {"

        result_json = evaluate_python_hook(code, annotation_json)
        result = json.loads(result_json)

        assert result["status"] == "invalid_input"
        assert "Invalid annotation_json" in result["stderr"]

    def test_handles_invalid_schema_json(self):
        """Test error handling for invalid schema JSON."""
        code = "def rossum_hook_request_handler(payload): return payload"
        annotation_json = json.dumps({"document_id": 1})
        schema_json = "invalid json"

        result_json = evaluate_python_hook(code, annotation_json, schema_json)
        result = json.loads(result_json)

        assert result["status"] == "invalid_input"
        assert "Invalid schema_json" in result["stderr"]

    def test_handles_empty_code(self):
        """Test error handling for empty code."""
        annotation_json = json.dumps({"document_id": 1})

        result_json = evaluate_python_hook("", annotation_json)
        result = json.loads(result_json)

        assert result["status"] == "invalid_input"
        assert "No code provided" in result["stderr"]

    def test_import_is_blocked(self):
        """Test that import statements are blocked."""
        code = """
import os

def rossum_hook_request_handler(payload):
    return os.getcwd()
"""
        annotation_json = json.dumps({"document_id": 1})

        result_json = evaluate_python_hook(code, annotation_json)
        result = json.loads(result_json)

        assert result["status"] == "error"
        assert result["exception"] is not None

    def test_open_is_blocked(self):
        """Test that open() is not available."""
        code = """
def rossum_hook_request_handler(payload):
    with open("/etc/passwd") as f:
        return f.read()
"""
        annotation_json = json.dumps({"document_id": 1})

        result_json = evaluate_python_hook(code, annotation_json)
        result = json.loads(result_json)

        assert result["status"] == "error"
        assert result["exception"] is not None

    def test_basic_builtins_available(self):
        """Test that basic safe builtins are available."""
        code = """
def rossum_hook_request_handler(payload):
    items = [1, 2, 3, 4, 5]
    return {
        "len": len(items),
        "sum": sum(items),
        "max": max(items),
        "min": min(items),
        "sorted": sorted(items, reverse=True),
        "bool": bool(items),
        "str": str(items[0]),
        "int": int("42"),
        "float": float("3.14"),
    }
"""
        annotation_json = json.dumps({"document_id": 1})

        result_json = evaluate_python_hook(code, annotation_json)
        result = json.loads(result_json)

        assert result["status"] == "success"
        expected = {
            "len": 5,
            "sum": 15,
            "max": 5,
            "min": 1,
            "sorted": [5, 4, 3, 2, 1],
            "bool": True,
            "str": "1",
            "int": 42,
            "float": 3.14,
        }
        assert result["result"] == expected

    def test_complex_annotation_structure(self):
        """Test with realistic annotation content structure."""
        code = """
def rossum_hook_request_handler(payload):
    annotation = payload["annotation"]
    content = annotation.get("content", [])

    total = 0
    for field in content:
        if field.get("schema_id") == "amount_total":
            total = float(field.get("value", 0))
            break

    return {"total_amount": total, "field_count": len(content)}
"""
        annotation = {
            "id": 123,
            "document_id": 456,
            "status": "to_review",
            "content": [
                {"schema_id": "invoice_id", "value": "INV-001", "id": 1001},
                {"schema_id": "amount_total", "value": "1500.00", "id": 1002},
                {"schema_id": "vendor_name", "value": "ACME Corp", "id": 1003},
            ],
        }
        annotation_json = json.dumps(annotation)

        result_json = evaluate_python_hook(code, annotation_json)
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert result["result"] == {"total_amount": 1500.0, "field_count": 3}

    def test_execute_internal_tool_integration(self):
        """Test that execute_internal_tool works with evaluate_python_hook."""
        code = "def rossum_hook_request_handler(payload): return payload['annotation']['id']"
        annotation_json = json.dumps({"id": 42})

        result_json = execute_internal_tool(
            "evaluate_python_hook",
            {"code": code, "annotation_json": annotation_json},
        )
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert result["result"] == 42


class TestDebugHookTool:
    """Test debug_hook tool definition."""

    def test_tool_is_registered(self):
        """Test that debug_hook is in the internal tools list."""
        tools = get_internal_tools()
        tool_names = [t["name"] for t in tools]
        assert "debug_hook" in tool_names

    def test_tool_in_tool_names(self):
        """Test that debug_hook is in get_internal_tool_names."""
        names = get_internal_tool_names()
        assert "debug_hook" in names

    def test_tool_has_description(self):
        """Test that the tool has a description."""
        tools = get_internal_tools()
        debug_tool = next(t for t in tools if t["name"] == "debug_hook")
        assert "description" in debug_tool
        assert "opus" in debug_tool["description"].lower()

    def test_input_schema_has_required_properties(self):
        """Test that the input schema has required properties."""
        tools = get_internal_tools()
        debug_tool = next(t for t in tools if t["name"] == "debug_hook")
        schema = debug_tool["input_schema"]
        assert schema["type"] == "object"
        assert "hook_id" in schema["properties"]
        assert "annotation_id" in schema["properties"]
        assert "schema_id" in schema["properties"]
        assert "hook_id" in schema["required"]
        assert "annotation_id" in schema["required"]


class TestDebugHook:
    """Test debug_hook function."""

    def test_handles_empty_hook_id(self):
        """Test error handling for empty hook_id."""
        result_json = debug_hook("", "123")
        result = json.loads(result_json)

        assert "error" in result
        assert "No hook_id provided" in result["error"]

    def test_handles_empty_annotation_id(self):
        """Test error handling for empty annotation_id."""
        result_json = debug_hook("123", "")
        result = json.loads(result_json)

        assert "error" in result
        assert "No annotation_id provided" in result["error"]

    def test_calls_opus_with_ids(self):
        """Test that debug_hook calls Opus sub-agent with correct IDs."""
        mock_analysis = "The hook correctly extracts the annotation ID and returns it."

        with patch("rossum_agent.internal_tools._call_opus_for_debug", return_value=mock_analysis) as mock_call:
            result_json = debug_hook("12345", "67890")
            result = json.loads(result_json)

        mock_call.assert_called_once_with("12345", "67890", None)
        assert result["hook_id"] == "12345"
        assert result["annotation_id"] == "67890"
        assert result["analysis"] == mock_analysis
        assert "elapsed_ms" in result

    def test_with_schema_id(self):
        """Test debug_hook with schema_id."""
        mock_analysis = "Hook correctly checks for schema presence."

        with patch("rossum_agent.internal_tools._call_opus_for_debug", return_value=mock_analysis) as mock_call:
            result_json = debug_hook("12345", "67890", "99999")
            result = json.loads(result_json)

        mock_call.assert_called_once_with("12345", "67890", "99999")
        assert result["hook_id"] == "12345"
        assert result["annotation_id"] == "67890"

    def test_handles_opus_call_failure(self):
        """Test graceful handling when Opus call fails."""
        with patch(
            "rossum_agent.internal_tools._call_opus_for_debug",
            return_value="Error calling Opus sub-agent: Connection failed",
        ):
            result_json = debug_hook("123", "456")
            result = json.loads(result_json)

        assert "analysis" in result
        assert "Error calling Opus" in result["analysis"]

    def test_execute_internal_tool_integration(self):
        """Test that execute_internal_tool works with debug_hook."""
        mock_analysis = "Simple hook that returns 'ok'."

        with patch("rossum_agent.internal_tools._call_opus_for_debug", return_value=mock_analysis):
            result_json = execute_internal_tool(
                "debug_hook",
                {"hook_id": "123", "annotation_id": "456"},
            )
            result = json.loads(result_json)

        assert result["analysis"] == mock_analysis
