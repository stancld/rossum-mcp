"""Tests for rossum_agent.utils module."""

from __future__ import annotations

import tempfile
from pathlib import Path

from rossum_agent.agent import _parse_aws_role_based_params
from rossum_agent.utils import clear_generated_files, get_generated_files


class TestGetGeneratedFiles:
    """Test get_generated_files function."""

    def test_returns_empty_list_when_output_dir_not_exists(self, monkeypatch):
        """Test that empty list is returned when output directory doesn't exist."""
        temp_dir = Path(tempfile.mkdtemp()) / "nonexistent"
        monkeypatch.setattr("rossum_agent.utils.OUTPUT_DIR", temp_dir)

        result = get_generated_files()

        assert result == []

    def test_returns_files_in_output_directory(self, monkeypatch, tmp_path):
        """Test that it returns all files in the output directory."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        monkeypatch.setattr("rossum_agent.utils.OUTPUT_DIR", output_dir)

        (output_dir / "file1.txt").write_text("content1")
        (output_dir / "file2.md").write_text("content2")
        (output_dir / "file3.json").write_text("{}")

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
        monkeypatch.setattr("rossum_agent.utils.OUTPUT_DIR", output_dir)

        (output_dir / "test.txt").write_text("content")

        result = get_generated_files()

        assert len(result) == 1
        assert Path(result[0]).is_absolute()

    def test_thread_safety_no_shared_state(self, monkeypatch, tmp_path):
        """Test that function doesn't use shared mutable state."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        monkeypatch.setattr("rossum_agent.utils.OUTPUT_DIR", output_dir)

        (output_dir / "file1.txt").write_text("content")

        result1 = get_generated_files()
        result2 = get_generated_files()

        assert result1 == result2
        assert result1 is not result2

        result1.append("fake_file")
        assert len(result1) == 2
        assert len(result2) == 1


class TestClearGeneratedFiles:
    """Test clear_generated_files function."""

    def test_does_nothing_when_output_dir_not_exists(self, monkeypatch):
        """Test that it safely handles non-existent directory."""
        temp_dir = Path(tempfile.mkdtemp()) / "nonexistent"
        monkeypatch.setattr("rossum_agent.utils.OUTPUT_DIR", temp_dir)

        clear_generated_files()

        assert not temp_dir.exists()

    def test_deletes_all_files_in_output_directory(self, monkeypatch, tmp_path):
        """Test that it deletes all files but not subdirectories."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        monkeypatch.setattr("rossum_agent.utils.OUTPUT_DIR", output_dir)

        file1 = output_dir / "file1.txt"
        file2 = output_dir / "file2.md"
        file1.write_text("content1")
        file2.write_text("content2")

        subdir = output_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested content")

        clear_generated_files()

        assert not file1.exists()
        assert not file2.exists()

        assert subdir.exists()
        assert (subdir / "nested.txt").exists()


class TestParseAwsRoleBasedParams:
    """Test _parse_aws_role_based_params function."""

    def test_returns_empty_dict_when_no_env_vars_set(self, monkeypatch):
        """Test that empty dict is returned when no AWS env vars are set."""
        monkeypatch.delenv("AWS_ROLE_NAME", raising=False)
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

        result = _parse_aws_role_based_params()

        assert result == {}

    def test_returns_all_keys_when_all_env_vars_set(self, monkeypatch):
        """Test that all keys are returned when all AWS env vars are set."""
        monkeypatch.setenv("AWS_ROLE_NAME", "test-role")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key-id")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret-key")

        result = _parse_aws_role_based_params()

        assert result == {
            "aws_role_name": "test-role",
            "aws_access_key_id": "test-key-id",
            "aws_secret_access_key": "test-secret-key",
        }

    def test_returns_only_set_keys(self, monkeypatch):
        """Test that only set env vars are included in the result."""
        monkeypatch.delenv("AWS_ROLE_NAME", raising=False)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key-id")
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

        result = _parse_aws_role_based_params()

        assert result == {"aws_access_key_id": "test-key-id"}

    def test_keys_are_lowercased(self, monkeypatch):
        """Test that returned keys are lowercase versions of env var names."""
        monkeypatch.setenv("AWS_ROLE_NAME", "my-role")

        result = _parse_aws_role_based_params()

        assert "aws_role_name" in result
        assert "AWS_ROLE_NAME" not in result
