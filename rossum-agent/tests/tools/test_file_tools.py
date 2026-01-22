"""Tests for rossum_agent.tools.file_tools module."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rossum_agent.tools import set_output_dir
from rossum_agent.tools.file_tools import write_file

if TYPE_CHECKING:
    from pathlib import Path


class TestWriteFile:
    """Tests for write_file tool."""

    def test_write_file_success(self, tmp_path: Path) -> None:
        """Test successful file write."""
        set_output_dir(tmp_path)
        try:
            result_json = write_file(filename="test.txt", content="Hello, World!")
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert "test.txt" in result["message"]
            assert (tmp_path / "test.txt").read_text() == "Hello, World!"
        finally:
            set_output_dir(None)

    def test_write_file_json_content(self, tmp_path: Path) -> None:
        """Test writing JSON content."""
        set_output_dir(tmp_path)
        try:
            json_content = '{"key": "value", "number": 42}'
            result_json = write_file(filename="data.json", content=json_content)
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert (tmp_path / "data.json").read_text() == json_content
        finally:
            set_output_dir(None)

    def test_write_file_dict_content(self, tmp_path: Path) -> None:
        """Test writing dict content - automatically converted to JSON."""
        set_output_dir(tmp_path)
        try:
            dict_content = {"key": "value", "number": 42}
            result_json = write_file(filename="data.json", content=dict_content)
            result = json.loads(result_json)

            assert result["status"] == "success"
            written = json.loads((tmp_path / "data.json").read_text())
            assert written == dict_content
        finally:
            set_output_dir(None)

    def test_write_file_list_content(self, tmp_path: Path) -> None:
        """Test writing list content - automatically converted to JSON."""
        set_output_dir(tmp_path)
        try:
            list_content = [{"id": 1, "name": "foo"}, {"id": 2, "name": "bar"}]
            result_json = write_file(filename="data.json", content=list_content)
            result = json.loads(result_json)

            assert result["status"] == "success"
            written = json.loads((tmp_path / "data.json").read_text())
            assert written == list_content
        finally:
            set_output_dir(None)

    def test_write_file_empty_filename_error(self, tmp_path: Path) -> None:
        """Test error when filename is empty."""
        set_output_dir(tmp_path)
        try:
            result_json = write_file(filename="", content="some content")
            result = json.loads(result_json)

            assert result["status"] == "error"
            assert "filename is required" in result["message"]
        finally:
            set_output_dir(None)

    def test_write_file_whitespace_filename_error(self, tmp_path: Path) -> None:
        """Test error when filename is only whitespace."""
        set_output_dir(tmp_path)
        try:
            result_json = write_file(filename="   ", content="some content")
            result = json.loads(result_json)

            assert result["status"] == "error"
            assert "filename is required" in result["message"]
        finally:
            set_output_dir(None)

    def test_write_file_empty_content_error(self, tmp_path: Path) -> None:
        """Test error when content is empty."""
        set_output_dir(tmp_path)
        try:
            result_json = write_file(filename="test.txt", content="")
            result = json.loads(result_json)

            assert result["status"] == "error"
            assert "content is required" in result["message"]
        finally:
            set_output_dir(None)

    def test_write_file_sanitizes_path_traversal(self, tmp_path: Path) -> None:
        """Test that path traversal attempts are sanitized."""
        set_output_dir(tmp_path)
        try:
            result_json = write_file(filename="../../../etc/passwd", content="malicious")
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert (tmp_path / "passwd").exists()
            assert not (tmp_path.parent / "passwd").exists()
        finally:
            set_output_dir(None)

    def test_write_file_returns_path(self, tmp_path: Path) -> None:
        """Test that returned path is correct."""
        set_output_dir(tmp_path)
        try:
            result_json = write_file(filename="output.md", content="# Header")
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert result["path"] == str(tmp_path / "output.md")
        finally:
            set_output_dir(None)

    def test_write_file_creates_output_dir(self, tmp_path: Path) -> None:
        """Test that output directory is created if it doesn't exist."""
        nested_dir = tmp_path / "nested" / "output"
        set_output_dir(nested_dir)
        try:
            result_json = write_file(filename="test.txt", content="content")
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert nested_dir.exists()
            assert (nested_dir / "test.txt").exists()
        finally:
            set_output_dir(None)

    def test_write_file_overwrites_existing(self, tmp_path: Path) -> None:
        """Test that existing files are overwritten."""
        set_output_dir(tmp_path)
        try:
            (tmp_path / "test.txt").write_text("old content")

            result_json = write_file(filename="test.txt", content="new content")
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert (tmp_path / "test.txt").read_text() == "new content"
        finally:
            set_output_dir(None)

    def test_write_file_exception_handling(self, tmp_path: Path) -> None:
        """Test error handling when write fails."""
        from unittest.mock import patch

        set_output_dir(tmp_path)
        try:
            with patch(
                "rossum_agent.tools.file_tools.Path.write_text", side_effect=PermissionError("Permission denied")
            ):
                result_json = write_file(filename="test.txt", content="content")
                result = json.loads(result_json)

                assert result["status"] == "error"
                assert "Error writing file" in result["message"]
        finally:
            set_output_dir(None)
