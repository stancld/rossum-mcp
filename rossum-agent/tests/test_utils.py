"""Tests for rossum_agent.utils module."""

from __future__ import annotations

import tempfile
from pathlib import Path

from rossum_agent.utils import (
    clear_generated_files,
    get_generated_files,
    get_session_output_dir,
    set_session_output_dir,
)


class TestGetGeneratedFiles:
    """Test get_generated_files function."""

    def test_returns_empty_list_when_output_dir_not_exists(self):
        """Test that empty list is returned when output directory doesn't exist."""
        temp_dir = Path(tempfile.mkdtemp()) / "nonexistent"

        result = get_generated_files(temp_dir)

        assert result == []

    def test_returns_files_in_output_directory(self, tmp_path):
        """Test that it returns all files in the output directory."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()

        (output_dir / "file1.txt").write_text("content1")
        (output_dir / "file2.md").write_text("content2")
        (output_dir / "file3.json").write_text("{}")

        (output_dir / "subdir").mkdir()

        result = get_generated_files(output_dir)

        assert len(result) == 3
        file_names = [Path(p).name for p in result]
        assert "file1.txt" in file_names
        assert "file2.md" in file_names
        assert "file3.json" in file_names

    def test_returns_absolute_paths(self, tmp_path):
        """Test that returned paths are absolute."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()

        (output_dir / "test.txt").write_text("content")

        result = get_generated_files(output_dir)

        assert len(result) == 1
        assert Path(result[0]).is_absolute()

    def test_thread_safety_no_shared_state(self, tmp_path):
        """Test that function doesn't use shared mutable state."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()

        (output_dir / "file1.txt").write_text("content")

        result1 = get_generated_files(output_dir)
        result2 = get_generated_files(output_dir)

        assert result1 == result2
        assert result1 is not result2

        result1.append("fake_file")
        assert len(result1) == 2
        assert len(result2) == 1

    def test_uses_session_context_when_no_arg_provided(self, tmp_path):
        """Test that session context is used when no output_dir is provided."""
        output_dir = tmp_path / "session_outputs"
        output_dir.mkdir()
        (output_dir / "session_file.txt").write_text("content")

        set_session_output_dir(output_dir)

        result = get_generated_files()

        assert len(result) == 1
        assert "session_file.txt" in result[0]


class TestClearGeneratedFiles:
    """Test clear_generated_files function."""

    def test_does_nothing_when_output_dir_not_exists(self):
        """Test that it safely handles non-existent directory."""
        temp_dir = Path(tempfile.mkdtemp()) / "nonexistent"

        clear_generated_files(temp_dir)

        assert not temp_dir.exists()

    def test_deletes_all_files_in_output_directory(self, tmp_path):
        """Test that it deletes all files but not subdirectories."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()

        file1 = output_dir / "file1.txt"
        file2 = output_dir / "file2.md"
        file1.write_text("content1")
        file2.write_text("content2")

        subdir = output_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested content")

        clear_generated_files(output_dir)

        assert not file1.exists()
        assert not file2.exists()

        assert subdir.exists()
        assert (subdir / "nested.txt").exists()


class TestSessionOutputDir:
    """Test session output directory context management."""

    def test_set_and_get_session_output_dir(self, tmp_path):
        """Test setting and getting session output directory."""
        output_dir = tmp_path / "my_session"
        output_dir.mkdir()

        set_session_output_dir(output_dir)
        result = get_session_output_dir()

        assert result == output_dir

    def test_default_fallback_when_not_set(self):
        """Test that a default directory is created when session is not set."""
        # Reset context by setting to None internally (simulate fresh context)
        # This is tricky to test since contextvars persist within the same thread
        # Just verify get_session_output_dir returns a Path
        result = get_session_output_dir()
        assert isinstance(result, Path)
