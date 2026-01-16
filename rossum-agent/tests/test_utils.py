"""Tests for rossum_agent.utils module."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from rossum_agent.utils import (
    BASE_OUTPUT_DIR,
    cleanup_session_output_dir,
    create_session_output_dir,
    generate_chat_id,
    get_generated_files,
    get_generated_files_with_metadata,
    get_session_output_dir,
    is_valid_chat_id,
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


class TestGenerateChatId:
    """Test generate_chat_id function."""

    def test_generates_unique_ids(self):
        """Test that multiple calls generate unique chat IDs."""
        chat_id_1 = generate_chat_id()
        chat_id_2 = generate_chat_id()

        assert chat_id_1 != chat_id_2

    def test_returns_string(self):
        """Test that chat ID is a string."""
        chat_id = generate_chat_id()

        assert isinstance(chat_id, str)

    def test_format_matches_expected_pattern(self):
        """Test that chat ID matches the expected format."""
        chat_id = generate_chat_id()

        pattern = r"^chat_\d{14}_[0-9a-f]{12}$"
        assert re.match(pattern, chat_id), f"Chat ID '{chat_id}' doesn't match expected pattern"

    def test_starts_with_chat_prefix(self):
        """Test that chat ID starts with 'chat_' prefix."""
        chat_id = generate_chat_id()

        assert chat_id.startswith("chat_")

    def test_contains_timestamp_component(self):
        """Test that chat ID contains a timestamp component."""
        chat_id = generate_chat_id()

        parts = chat_id.split("_")
        assert len(parts) == 3

        timestamp = parts[1]
        assert len(timestamp) == 14
        assert timestamp.isdigit()

    def test_contains_hex_uuid_component(self):
        """Test that chat ID contains a 12-character hex UUID component."""
        chat_id = generate_chat_id()

        parts = chat_id.split("_")
        uuid_part = parts[2]

        assert len(uuid_part) == 12
        assert all(c in "0123456789abcdef" for c in uuid_part)


class TestIsValidChatId:
    """Test is_valid_chat_id function."""

    def test_valid_chat_id_returns_true(self):
        """Test that a valid chat ID returns True."""
        chat_id = generate_chat_id()

        assert is_valid_chat_id(chat_id) is True

    def test_invalid_type_returns_false(self):
        """Test that non-string input returns False."""
        assert is_valid_chat_id(123) is False
        assert is_valid_chat_id(None) is False
        assert is_valid_chat_id([]) is False

    def test_wrong_prefix_returns_false(self):
        """Test that chat ID with wrong prefix returns False."""
        assert is_valid_chat_id("wrong_20231203120000_abc123def456") is False

    def test_wrong_number_of_parts_returns_false(self):
        """Test that chat ID with wrong number of parts returns False."""
        assert is_valid_chat_id("chat_20231203120000") is False
        assert is_valid_chat_id("chat_20231203120000_abc_def") is False

    def test_invalid_timestamp_returns_false(self):
        """Test that chat ID with invalid timestamp returns False."""
        assert is_valid_chat_id("chat_2023120312_abc123def456") is False
        assert is_valid_chat_id("chat_20231203120000X_abc123def456") is False
        assert is_valid_chat_id("chat_abcd1203120000_abc123def456") is False

    def test_invalid_uuid_length_returns_false(self):
        """Test that chat ID with wrong UUID length returns False."""
        assert is_valid_chat_id("chat_20231203120000_abc123") is False
        assert is_valid_chat_id("chat_20231203120000_abc123def456789") is False

    def test_invalid_uuid_characters_returns_false(self):
        """Test that chat ID with non-hex UUID returns False."""
        assert is_valid_chat_id("chat_20231203120000_xyz123def456") is False
        assert is_valid_chat_id("chat_20231203120000_ABC123DEF456") is False

    def test_empty_string_returns_false(self):
        """Test that empty string returns False."""
        assert is_valid_chat_id("") is False


class TestCreateSessionOutputDir:
    """Test create_session_output_dir function."""

    def test_creates_new_directory(self):
        """Test that a new session directory is created."""
        session_dir = create_session_output_dir()

        assert session_dir.exists()
        assert session_dir.is_dir()

        cleanup_session_output_dir(session_dir)

    def test_creates_unique_directories(self):
        """Test that each call creates a unique directory."""
        dir1 = create_session_output_dir()
        dir2 = create_session_output_dir()

        assert dir1 != dir2
        assert dir1.exists()
        assert dir2.exists()

        cleanup_session_output_dir(dir1)
        cleanup_session_output_dir(dir2)

    def test_directory_is_under_base_output_dir(self):
        """Test that session directory is under the base output directory."""
        session_dir = create_session_output_dir()

        assert str(session_dir).startswith(str(BASE_OUTPUT_DIR))

        cleanup_session_output_dir(session_dir)


class TestCleanupSessionOutputDir:
    """Test cleanup_session_output_dir function."""

    def test_removes_existing_directory(self, tmp_path):
        """Test that an existing directory is removed."""
        test_dir = tmp_path / "session_to_clean"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")
        (test_dir / "subdir").mkdir()
        (test_dir / "subdir" / "nested.txt").write_text("nested")

        cleanup_session_output_dir(test_dir)

        assert not test_dir.exists()

    def test_handles_nonexistent_directory(self, tmp_path):
        """Test that cleaning a nonexistent directory doesn't raise error."""
        nonexistent = tmp_path / "does_not_exist"

        cleanup_session_output_dir(nonexistent)

    def test_handles_file_instead_of_directory(self, tmp_path):
        """Test that cleaning a file path doesn't raise error."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")

        cleanup_session_output_dir(file_path)

        assert file_path.exists()


class TestGetGeneratedFilesWithMetadata:
    """Test get_generated_files_with_metadata function."""

    def test_returns_empty_dict_when_dir_not_exists(self):
        """Test empty dict is returned for nonexistent directory."""
        temp_dir = Path(tempfile.mkdtemp()) / "nonexistent"

        result = get_generated_files_with_metadata(temp_dir)

        assert result == {}

    def test_returns_files_with_mtime(self, tmp_path):
        """Test that files are returned with modification times."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()

        file1 = output_dir / "file1.txt"
        file1.write_text("content1")
        file2 = output_dir / "file2.md"
        file2.write_text("content2")

        result = get_generated_files_with_metadata(output_dir)

        assert len(result) == 2
        for _path, mtime in result.items():
            assert isinstance(mtime, float)
            assert mtime > 0

    def test_returns_absolute_paths_as_keys(self, tmp_path):
        """Test that returned paths are absolute."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        (output_dir / "test.txt").write_text("content")

        result = get_generated_files_with_metadata(output_dir)

        for path in result:
            assert Path(path).is_absolute()

    def test_excludes_directories(self, tmp_path):
        """Test that directories are excluded from results."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        (output_dir / "file.txt").write_text("content")
        (output_dir / "subdir").mkdir()

        result = get_generated_files_with_metadata(output_dir)

        assert len(result) == 1
        assert any("file.txt" in path for path in result)

    def test_includes_nested_files(self, tmp_path):
        """Test that nested files are included."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        (output_dir / "file1.txt").write_text("content1")
        subdir = output_dir / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").write_text("content2")

        result = get_generated_files_with_metadata(output_dir)

        assert len(result) == 2

    def test_uses_session_context_when_no_arg_provided(self, tmp_path):
        """Test that session context is used when no output_dir is provided."""
        output_dir = tmp_path / "session_outputs"
        output_dir.mkdir()
        (output_dir / "session_file.txt").write_text("content")

        set_session_output_dir(output_dir)

        result = get_generated_files_with_metadata()

        assert len(result) == 1
        assert any("session_file.txt" in path for path in result)


class TestSessionOutputDirFallback:
    """Test session output directory fallback behavior."""

    def test_fallback_creates_default_outputs_dir(self):
        """Test that fallback creates default ./outputs directory when context is None."""
        from rossum_agent.utils import _session_output_dir

        token = _session_output_dir.set(None)
        try:
            result = get_session_output_dir()
            assert isinstance(result, Path)
            assert result == Path("./outputs")
            assert result.exists()
        finally:
            _session_output_dir.reset(token)
            if Path("./outputs").exists() and not list(Path("./outputs").iterdir()):
                Path("./outputs").rmdir()
