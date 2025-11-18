"""Tests for rossum_agent.file_system_tools module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from rossum_agent.file_system_tools import (
    clear_generated_files,
    get_file_info,
    get_generated_files,
    list_files,
    read_file,
    write_file,
)


class TestGetGeneratedFiles:
    """Test get_generated_files function."""

    def test_returns_empty_list_when_output_dir_not_exists(self, monkeypatch):
        """Test that empty list is returned when output directory doesn't exist."""
        # Use a non-existent temporary directory
        temp_dir = Path(tempfile.mkdtemp()) / "nonexistent"
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", temp_dir)

        result = get_generated_files()

        assert result == []

    def test_returns_files_in_output_directory(self, monkeypatch, tmp_path):
        """Test that it returns all files in the output directory."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", output_dir)

        # Create some test files
        (output_dir / "file1.txt").write_text("content1")
        (output_dir / "file2.md").write_text("content2")
        (output_dir / "file3.json").write_text("{}")

        # Create a subdirectory (should not be included)
        (output_dir / "subdir").mkdir()

        result = get_generated_files()

        assert len(result) == 3
        file_names = [Path(p).name for p in result]
        assert "file1.txt" in file_names
        assert "file2.md" in file_names
        assert "file3.json" in file_names

    def test_returns_absolute_paths(self, monkeypatch, tmp_path):
        """Test that returned paths are absolute."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", output_dir)

        (output_dir / "test.txt").write_text("content")

        result = get_generated_files()

        assert len(result) == 1
        assert Path(result[0]).is_absolute()

    def test_thread_safety_no_shared_state(self, monkeypatch, tmp_path):
        """Test that function doesn't use shared mutable state."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", output_dir)

        (output_dir / "file1.txt").write_text("content")

        # Get files twice
        result1 = get_generated_files()
        result2 = get_generated_files()

        # They should be equal but not the same object
        assert result1 == result2
        assert result1 is not result2

        # Modifying one should not affect the other
        result1.append("fake_file")
        assert len(result1) == 2
        assert len(result2) == 1


class TestClearGeneratedFiles:
    """Test clear_generated_files function."""

    def test_does_nothing_when_output_dir_not_exists(self, monkeypatch):
        """Test that it safely handles non-existent directory."""
        temp_dir = Path(tempfile.mkdtemp()) / "nonexistent"
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", temp_dir)

        # Should not raise any exception
        clear_generated_files()

        assert not temp_dir.exists()

    def test_deletes_all_files_in_output_directory(self, monkeypatch, tmp_path):
        """Test that it deletes all files but not subdirectories."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", output_dir)

        # Create test files
        file1 = output_dir / "file1.txt"
        file2 = output_dir / "file2.md"
        file1.write_text("content1")
        file2.write_text("content2")

        # Create subdirectory with file (should not be deleted)
        subdir = output_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested content")

        clear_generated_files()

        # Files should be deleted
        assert not file1.exists()
        assert not file2.exists()

        # Subdirectory should remain
        assert subdir.exists()
        assert (subdir / "nested.txt").exists()

    def test_clears_files_after_write(self, monkeypatch, tmp_path):
        """Test integration with write_file."""
        output_dir = tmp_path / "outputs"
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", output_dir)

        # Write a file
        write_file("test.txt", "content")

        # Verify file exists
        files = get_generated_files()
        assert len(files) == 1

        # Clear files
        clear_generated_files()

        # Verify no files remain
        files = get_generated_files()
        assert len(files) == 0


class TestWriteFile:
    """Test write_file tool function."""

    def test_creates_output_directory_if_not_exists(self, monkeypatch, tmp_path):
        """Test that output directory is created automatically."""
        output_dir = tmp_path / "outputs"
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", output_dir)

        assert not output_dir.exists()

        write_file("test.txt", "content")

        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_writes_file_to_output_directory(self, monkeypatch, tmp_path):
        """Test that file is written to correct location."""
        output_dir = tmp_path / "outputs"
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", output_dir)

        result_json = write_file("test.txt", "Hello, World!")
        result = json.loads(result_json)

        assert result["success"] is True
        assert (output_dir / "test.txt").exists()
        assert (output_dir / "test.txt").read_text() == "Hello, World!"

    def test_extracts_filename_from_absolute_path(self, monkeypatch, tmp_path):
        """Test that only filename is used from absolute paths."""
        output_dir = tmp_path / "outputs"
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", output_dir)

        result_json = write_file("/some/absolute/path/myfile.txt", "content")
        result = json.loads(result_json)

        assert result["success"] is True
        assert (output_dir / "myfile.txt").exists()
        # Original path should not be created
        assert not Path("/some/absolute/path/myfile.txt").exists()

    def test_respects_overwrite_false(self, monkeypatch, tmp_path):
        """Test that overwrite=False prevents overwriting."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", output_dir)

        # Write initial file
        (output_dir / "test.txt").write_text("original")

        # Attempt to overwrite with overwrite=False
        result_json = write_file("test.txt", "new content", overwrite=False)
        result = json.loads(result_json)

        assert "error" in result
        assert "already exists" in result["error"]
        assert (output_dir / "test.txt").read_text() == "original"

    def test_overwrites_by_default(self, monkeypatch, tmp_path):
        """Test that files are overwritten by default."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", output_dir)

        # Write initial file
        write_file("test.txt", "original")

        # Overwrite
        write_file("test.txt", "new content")

        assert (output_dir / "test.txt").read_text() == "new content"

    def test_returns_correct_metadata(self, monkeypatch, tmp_path):
        """Test that result includes correct metadata."""
        output_dir = tmp_path / "outputs"
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", output_dir)

        content = "Test content with some length"
        result_json = write_file("test.txt", content)
        result = json.loads(result_json)

        assert result["success"] is True
        assert "path" in result
        assert "test.txt" in result["path"]
        assert result["size"] == len(content)
        assert "message" in result

    def test_handles_relative_paths(self, monkeypatch, tmp_path):
        """Test that relative paths extract just the filename."""
        output_dir = tmp_path / "outputs"
        monkeypatch.setattr("rossum_agent.file_system_tools.OUTPUT_DIR", output_dir)

        # Relative path with subdirectory - should extract just the filename
        result_json = write_file("subdir/myfile.txt", "content")
        result = json.loads(result_json)

        assert result["success"] is True
        # Should flatten the path and create the file with just the filename
        assert (output_dir / "myfile.txt").exists()
        assert not (output_dir / "subdir").exists()


class TestListFiles:
    """Test list_files tool function."""

    def test_lists_files_in_directory(self, tmp_path):
        """Test basic file listing."""
        # Create test files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.md").write_text("content2")
        (tmp_path / "subdir").mkdir()

        result_json = list_files(str(tmp_path))
        result = json.loads(result_json)

        assert result["directory"] == str(tmp_path)
        assert result["count"] == 3
        names = [f["name"] for f in result["files"]]
        assert "file1.txt" in names
        assert "file2.md" in names
        assert "subdir" in names

    def test_filters_by_pattern(self, tmp_path):
        """Test pattern filtering."""
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        (tmp_path / "file3.md").write_text("content3")

        result_json = list_files(str(tmp_path), pattern="*.txt")
        result = json.loads(result_json)

        assert result["count"] == 2
        names = [f["name"] for f in result["files"]]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "file3.md" not in names

    def test_returns_error_for_nonexistent_directory(self, tmp_path):
        """Test error handling for non-existent directory."""
        nonexistent = tmp_path / "nonexistent"

        result_json = list_files(str(nonexistent))
        result = json.loads(result_json)

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_returns_error_for_file_path(self, tmp_path):
        """Test error when path is a file, not directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")

        result_json = list_files(str(file_path))
        result = json.loads(result_json)

        assert "error" in result
        assert "not a directory" in result["error"].lower()


class TestReadFile:
    """Test read_file tool function."""

    def test_reads_file_content(self, tmp_path):
        """Test basic file reading."""
        file_path = tmp_path / "test.txt"
        content = "Hello, World!\nSecond line."
        file_path.write_text(content)

        result_json = read_file(str(file_path))
        result = json.loads(result_json)

        assert result["content"] == content
        assert "path" in result
        assert result["size"] == len(content)
        assert "modified" in result

    def test_returns_error_for_nonexistent_file(self, tmp_path):
        """Test error handling for non-existent file."""
        nonexistent = tmp_path / "nonexistent.txt"

        result_json = read_file(str(nonexistent))
        result = json.loads(result_json)

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_returns_error_for_directory(self, tmp_path):
        """Test error when path is a directory."""
        result_json = read_file(str(tmp_path))
        result = json.loads(result_json)

        assert "error" in result
        assert "not a file" in result["error"].lower()


class TestGetFileInfo:
    """Test get_file_info tool function."""

    def test_gets_file_info(self, tmp_path):
        """Test getting file metadata."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        result_json = get_file_info(str(file_path))
        result = json.loads(result_json)

        assert result["name"] == "test.txt"
        assert result["type"] == "file"
        assert result["size"] > 0
        assert "created" in result
        assert "modified" in result
        assert "accessed" in result

    def test_gets_directory_info(self, tmp_path):
        """Test getting directory metadata."""
        result_json = get_file_info(str(tmp_path))
        result = json.loads(result_json)

        assert result["type"] == "directory"
        assert "size" in result
        assert "created" in result

    def test_returns_error_for_nonexistent_path(self, tmp_path):
        """Test error handling for non-existent path."""
        nonexistent = tmp_path / "nonexistent"

        result_json = get_file_info(str(nonexistent))
        result = json.loads(result_json)

        assert "error" in result
        assert "not found" in result["error"].lower()
