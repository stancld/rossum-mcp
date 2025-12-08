"""Tests for rossum_agent.internal_tools module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from rossum_agent.internal_tools import (
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
