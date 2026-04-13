"""Tests for rossum_agent.postgres_storage module."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy as sa
from rossum_agent.chat_models import ChatMetadata, extract_preview_from_first_msg
from rossum_agent.postgres_storage import PostgresStorage
from sqlalchemy.exc import SQLAlchemyError


def _make_storage_with_mock_engine():
    """Create a PostgresStorage with a mocked SQLAlchemy engine."""
    storage = PostgresStorage.__new__(PostgresStorage)
    storage.host = "localhost"
    storage.port = 5432
    storage.dbname = "test_db"
    storage.user = "test_user"
    storage.password = "test_pass"
    storage.sslmode = None
    storage.ttl = __import__("datetime").timedelta(days=30)
    storage._engine = MagicMock(spec=sa.engine.Engine)
    return storage


@pytest.fixture
def pg_storage():
    """Create a PostgresStorage with mocked engine and connection."""
    storage = _make_storage_with_mock_engine()
    mock_conn = MagicMock()
    # Make engine.begin() and engine.connect() return context managers yielding mock_conn
    storage._engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    storage._engine.begin.return_value.__exit__ = MagicMock(return_value=False)
    storage._engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    storage._engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    return storage, mock_conn


class TestPostgresStorageInit:
    """Test PostgresStorage initialization."""

    def test_default_values(self):
        """Test defaults from env."""
        with patch.dict("os.environ", {}, clear=True):
            storage = PostgresStorage.__new__(PostgresStorage)
            storage.__init__()
            assert storage.host == "localhost"
            assert storage.port == 5432
            assert storage.dbname == "rossum_agent"
            assert storage.user == "rossum"
            assert storage.password == "rossum"
            assert storage.sslmode is None

    def test_custom_values(self):
        """Test custom constructor values."""
        storage = PostgresStorage(
            host="db.example.com",
            port=5433,
            dbname="mydb",
            user="myuser",
            password="mypass",
            sslmode="require",
            ttl_days=7,
        )
        assert storage.host == "db.example.com"
        assert storage.port == 5433
        assert storage.dbname == "mydb"
        assert storage.user == "myuser"
        assert storage.password == "mypass"
        assert storage.sslmode == "require"
        assert storage.ttl.days == 7

    def test_env_var_override(self):
        """Test environment variable configuration."""
        env = {
            "POSTGRES_HOST": "env-host",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DB": "env-db",
            "POSTGRES_USER": "env-user",
            "POSTGRES_PASSWORD": "env-pass",
            "POSTGRES_SSLMODE": "require",
        }
        with patch.dict("os.environ", env, clear=True):
            storage = PostgresStorage()
            assert storage.host == "env-host"
            assert storage.port == 5433
            assert storage.dbname == "env-db"
            assert storage.user == "env-user"
            assert storage.password == "env-pass"
            assert storage.sslmode == "require"

    def test_sslmode_passed_to_engine(self):
        """Test that sslmode is included in connect_args when set."""
        storage = PostgresStorage(sslmode="require")
        with patch("rossum_agent.postgres_storage.sa.create_engine") as mock_create:
            mock_create.return_value = MagicMock(spec=sa.engine.Engine)
            _ = storage.engine
            call_kwargs = mock_create.call_args
            assert call_kwargs.kwargs["connect_args"]["sslmode"] == "require"

    def test_sslmode_omitted_when_not_set(self):
        """Test that sslmode is not in connect_args when unset."""
        with patch.dict("os.environ", {}, clear=True):
            storage = PostgresStorage()
        with patch("rossum_agent.postgres_storage.sa.create_engine") as mock_create:
            mock_create.return_value = MagicMock(spec=sa.engine.Engine)
            _ = storage.engine
            call_kwargs = mock_create.call_args
            assert "sslmode" not in call_kwargs.kwargs["connect_args"]


class TestPostgresStorageInitialize:
    """Test initialize() runs Alembic migrations."""

    def test_initialize_calls_alembic_upgrade(self):
        """Test that initialize() invokes alembic upgrade to head."""
        storage = _make_storage_with_mock_engine()

        with patch("rossum_agent.postgres_storage.command") as mock_command:
            storage.initialize()

            mock_command.upgrade.assert_called_once()
            cfg = mock_command.upgrade.call_args[0][0]
            assert cfg.get_main_option("script_location").endswith("alembic")
            assert cfg.attributes["engine"] is storage._engine
            assert mock_command.upgrade.call_args[0][1] == "head"


class TestPostgresStorageChat:
    """Test chat CRUD operations."""

    def test_save_chat_basic(self, pg_storage):
        """Test saving a chat."""
        storage, mock_conn = pg_storage
        # First query (feedback preservation) returns None
        mock_conn.execute.return_value.first.return_value = None

        messages = [{"role": "user", "content": "Hello"}]
        metadata = ChatMetadata(total_input_tokens=100)

        result = storage.save_chat("user1", "chat_123", messages, metadata=metadata)
        assert result is True

    def test_save_chat_preserves_feedback(self, pg_storage):
        """Test that existing feedback is preserved on save."""
        storage, mock_conn = pg_storage
        # First call returns existing messages with feedback, second is the upsert
        existing_row = MagicMock()
        existing_row.messages = [{"role": "user", "content": "Hello", "feedback": True}]
        mock_conn.execute.return_value.first.return_value = existing_row

        messages = [{"role": "user", "content": "Hello"}]
        result = storage.save_chat("user1", "chat_123", messages)
        assert result is True

    def test_save_chat_failure(self, pg_storage):
        """Test save_chat handles exceptions."""
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")

        result = storage.save_chat("user1", "chat_123", [])
        assert result is False

    def test_load_chat_found(self, pg_storage):
        """Test loading an existing chat."""
        storage, mock_conn = pg_storage
        mock_row = MagicMock()
        mock_row.messages = [{"role": "user", "content": "Hello"}]
        mock_row.output_dir = "/mock/output"
        mock_row.metadata_ = {"total_input_tokens": 100, "total_output_tokens": 50}
        mock_conn.execute.return_value.first.return_value = mock_row

        result = storage.load_chat("user1", "chat_123")

        assert result is not None
        assert len(result.messages) == 1
        assert result.output_dir == "/mock/output"
        assert result.metadata.total_input_tokens == 100

    def test_load_chat_not_found(self, pg_storage):
        """Test loading a non-existent chat."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.first.return_value = None

        result = storage.load_chat("user1", "chat_123")
        assert result is None

    def test_load_chat_failure(self, pg_storage):
        """Test load_chat handles exceptions."""
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")

        result = storage.load_chat("user1", "chat_123")
        assert result is None

    def test_delete_chat(self, pg_storage):
        """Test deleting a chat."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.rowcount = 1

        result = storage.delete_chat("user1", "chat_123")
        assert result is True

    def test_delete_chat_not_found(self, pg_storage):
        """Test deleting a non-existent chat."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.rowcount = 0

        result = storage.delete_chat("user1", "chat_123")
        assert result is False

    def test_chat_exists_true(self, pg_storage):
        """Test chat_exists returns True when chat exists."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.first.return_value = (1,)

        assert storage.chat_exists("user1", "chat_123") is True

    def test_chat_exists_false(self, pg_storage):
        """Test chat_exists returns False when chat doesn't exist."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.first.return_value = None

        assert storage.chat_exists("user1", "chat_123") is False

    def test_list_all_chats(self, pg_storage):
        """Test listing all chats."""
        storage, mock_conn = pg_storage
        mock_row = MagicMock()
        mock_row.chat_id = "chat_20250101120000_abc123"
        mock_row.message_count = 1
        mock_row.first_msg = {"role": "user", "content": "Hello"}
        mock_row.metadata_ = {"total_input_tokens": 100, "total_output_tokens": 50}
        mock_conn.execute.return_value.all.return_value = [mock_row]

        result = storage.list_all_chats("user1")

        assert len(result) == 1
        assert result[0]["chat_id"] == "chat_20250101120000_abc123"
        assert result[0]["message_count"] == 1
        assert result[0]["first_message"] == "Hello"

    def test_list_all_chats_shared(self, pg_storage):
        """Test listing shared chats (no user_id)."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.all.return_value = []

        result = storage.list_all_chats(None)
        assert result == []


class TestPostgresStorageFile:
    """Test file operations."""

    def test_save_file_with_content(self, pg_storage):
        """Test saving a file with explicit content."""
        storage, _mock_conn = pg_storage

        result = storage.save_file("chat_123", Path("/mock/test.txt"), content=b"hello world")
        assert result is True

    def test_save_file_from_disk(self, pg_storage):
        """Test saving a file read from disk."""
        storage, _mock_conn = pg_storage

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"file content")
            f.flush()
            result = storage.save_file("chat_123", Path(f.name))

        assert result is True

    def test_save_file_not_found(self, pg_storage):
        """Test saving a non-existent file."""
        storage, _mock_conn = pg_storage

        result = storage.save_file("chat_123", Path("/nonexistent/file.txt"))
        assert result is False

    def test_load_file_found(self, pg_storage):
        """Test loading an existing file."""
        storage, mock_conn = pg_storage
        mock_row = MagicMock()
        mock_row.content = b"hello world"
        mock_conn.execute.return_value.first.return_value = mock_row

        result = storage.load_file("chat_123", "test.txt")
        assert result == b"hello world"

    def test_load_file_not_found(self, pg_storage):
        """Test loading a non-existent file."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.first.return_value = None

        result = storage.load_file("chat_123", "test.txt")
        assert result is None

    def test_list_files(self, pg_storage):
        """Test listing files."""
        storage, mock_conn = pg_storage
        import datetime as dt

        mock_row = MagicMock()
        mock_row.filename = "test.txt"
        mock_row.size = 11
        mock_row.created_at = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
        mock_conn.execute.return_value.all.return_value = [mock_row]

        result = storage.list_files("chat_123")
        assert len(result) == 1
        assert result[0]["filename"] == "test.txt"
        assert result[0]["size"] == 11

    def test_delete_file(self, pg_storage):
        """Test deleting a file."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.rowcount = 1

        result = storage.delete_file("chat_123", "test.txt")
        assert result is True

    def test_delete_all_files(self, pg_storage):
        """Test deleting all files."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.rowcount = 3

        result = storage.delete_all_files("chat_123")
        assert result == 3

    def test_save_all_files(self, pg_storage):
        """Test saving all files from a directory."""
        storage, _mock_conn = pg_storage

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "file1.txt").write_bytes(b"content1")
            Path(tmpdir, "file2.txt").write_bytes(b"content2")

            result = storage.save_all_files("chat_123", Path(tmpdir))
            assert result == 2

    def test_load_all_files(self, pg_storage):
        """Test loading all files to a directory with streaming."""
        storage, _mock_conn = pg_storage

        mock_row = MagicMock()
        mock_row.filename = "test.txt"
        mock_row.content = b"hello"

        # load_all_files uses: engine.connect().execution_options(...) -> conn -> execute -> yield_per
        mock_streaming_conn = MagicMock()
        mock_streaming_conn.execute.return_value.yield_per.return_value = [mock_row]
        storage._engine.connect.return_value.execution_options.return_value.__enter__ = MagicMock(
            return_value=mock_streaming_conn
        )
        storage._engine.connect.return_value.execution_options.return_value.__exit__ = MagicMock(return_value=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = storage.load_all_files("chat_123", Path(tmpdir))
            assert result == 1
            assert (Path(tmpdir) / "test.txt").read_bytes() == b"hello"


class TestPostgresStorageFeedback:
    """Test feedback operations."""

    def test_save_feedback(self, pg_storage):
        """Test saving feedback."""
        storage, mock_conn = pg_storage
        # First call returns message count, second is the update
        mock_conn.execute.return_value.scalar.return_value = 2

        result = storage.save_feedback("user1", "chat_123", 1, True)
        assert result is True

    def test_save_feedback_invalid_index(self, pg_storage):
        """Test saving feedback with invalid turn index."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.scalar.return_value = 1

        result = storage.save_feedback("user1", "chat_123", 5, True)
        assert result is False

    def test_save_feedback_chat_not_found(self, pg_storage):
        """Test saving feedback when chat doesn't exist."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.scalar.return_value = None

        result = storage.save_feedback("user1", "chat_123", 0, True)
        assert result is False

    def test_get_feedback(self, pg_storage):
        """Test getting feedback."""
        storage, mock_conn = pg_storage
        mock_row = MagicMock()
        mock_row.messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi", "feedback": True},
        ]
        mock_conn.execute.return_value.first.return_value = mock_row

        result = storage.get_feedback("user1", "chat_123")
        assert result == {1: True}

    def test_get_feedback_empty(self, pg_storage):
        """Test getting feedback when none exists."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.first.return_value = None

        result = storage.get_feedback("user1", "chat_123")
        assert result == {}

    def test_delete_feedback(self, pg_storage):
        """Test deleting feedback for a specific turn."""
        storage, mock_conn = pg_storage
        mock_row = MagicMock()
        mock_row.msg_len = 1
        mock_row.has_feedback = True
        mock_conn.execute.return_value.first.return_value = mock_row

        result = storage.delete_feedback("user1", "chat_123", 0)
        assert result is True

    def test_delete_feedback_not_found(self, pg_storage):
        """Test deleting non-existent feedback."""
        storage, mock_conn = pg_storage
        mock_row = MagicMock()
        mock_row.msg_len = 1
        mock_row.has_feedback = False
        mock_conn.execute.return_value.first.return_value = mock_row

        result = storage.delete_feedback("user1", "chat_123", 0)
        assert result is False

    def test_delete_all_feedback(self, pg_storage):
        """Test deleting all feedback."""
        storage, mock_conn = pg_storage
        mock_row = MagicMock()
        mock_row.messages = [
            {"role": "user", "content": "Hello", "feedback": False},
            {"role": "assistant", "content": "Hi", "feedback": True},
        ]
        mock_conn.execute.return_value.first.return_value = mock_row

        result = storage.delete_all_feedback("user1", "chat_123")
        assert result is True

    def test_delete_all_feedback_chat_not_found(self, pg_storage):
        """Test deleting feedback when chat doesn't exist."""
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.first.return_value = None

        result = storage.delete_all_feedback("user1", "chat_123")
        assert result is False


class TestPostgresStorageConnection:
    """Test connection management."""

    def test_is_connected_true(self, pg_storage):
        """Test is_connected when DB is reachable."""
        storage, _mock_conn = pg_storage
        assert storage.is_connected() is True

    def test_is_connected_false(self, pg_storage):
        """Test is_connected when DB is unreachable."""
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("Connection refused")

        assert storage.is_connected() is False

    def test_close(self, pg_storage):
        """Test closing the connection pool."""
        storage, _ = pg_storage
        mock_engine = storage._engine
        storage.close()
        mock_engine.dispose.assert_called_once()
        assert storage._engine is None

    def test_close_already_closed(self):
        """Test closing when already closed."""
        storage = PostgresStorage.__new__(PostgresStorage)
        storage._engine = None
        storage.close()  # should not raise

    def test_user_id_db_with_user(self, pg_storage):
        """Test _user_id_db with a user_id."""
        storage, _ = pg_storage
        assert storage._user_id_db("user1") == "user1"

    def test_user_id_db_without_user(self, pg_storage):
        """Test _user_id_db without a user_id."""
        storage, _ = pg_storage
        assert storage._user_id_db(None) == ""


class TestPreviewFromFirstMsg:
    """Test extract_preview_from_first_msg standalone function."""

    def test_none_msg(self):
        assert extract_preview_from_first_msg(None) == ""

    def test_empty_dict(self):
        assert extract_preview_from_first_msg({}) == ""

    def test_task_step_msg(self):
        msg = {"type": "task_step", "task": "Analyze schema"}
        assert extract_preview_from_first_msg(msg) == "Analyze schema"

    def test_task_step_no_task(self):
        msg = {"type": "task_step"}
        assert extract_preview_from_first_msg(msg) == ""

    def test_user_role_msg(self):
        msg = {"role": "user", "content": "Hello world"}
        assert extract_preview_from_first_msg(msg) == "Hello world"

    def test_assistant_role_returns_empty(self):
        msg = {"role": "assistant", "content": "Hi there"}
        assert extract_preview_from_first_msg(msg) == ""


class TestSaveChatWithOutputDir:
    """Test save_chat output_dir branch."""

    def test_save_chat_with_str_output_dir(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.first.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "out.txt").write_bytes(b"data")
            with patch.object(storage, "save_all_files", return_value=1) as mock_save:
                result = storage.save_chat("user1", "chat_1", [{"role": "user", "content": "hi"}], output_dir=tmpdir)
                assert result is True
                mock_save.assert_called_once_with("chat_1", Path(tmpdir))

    def test_save_chat_with_path_output_dir(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.first.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "out.txt").write_bytes(b"data")
            with patch.object(storage, "save_all_files", return_value=1) as mock_save:
                result = storage.save_chat("user1", "chat_1", [{"role": "user", "content": "hi"}], output_dir=p)
                assert result is True
                mock_save.assert_called_once_with("chat_1", p)


class TestLoadChatWithOutputDir:
    """Test load_chat output_dir branch."""

    def test_load_chat_with_output_dir(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_row = MagicMock()
        mock_row.messages = [{"role": "user", "content": "Hello"}]
        mock_row.output_dir = "/mock/output"
        mock_row.metadata_ = {}
        mock_conn.execute.return_value.first.return_value = mock_row

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(storage, "load_all_files", return_value=2) as mock_load,
        ):
            result = storage.load_chat("user1", "chat_1", output_dir=Path(tmpdir))
            assert result is not None
            mock_load.assert_called_once_with("chat_1", Path(tmpdir))


class TestSaveAllFilesEdgeCases:
    """Test save_all_files edge cases."""

    def test_nonexistent_directory(self, pg_storage):
        storage, _ = pg_storage
        result = storage.save_all_files("chat_1", Path("/nonexistent/dir"))
        assert result == 0

    def test_empty_directory(self, pg_storage):
        storage, _ = pg_storage
        with tempfile.TemporaryDirectory() as tmpdir:
            result = storage.save_all_files("chat_1", Path(tmpdir))
            assert result == 0

    def test_save_all_files_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "f.txt").write_bytes(b"data")
            result = storage.save_all_files("chat_1", Path(tmpdir))
            assert result == 0


class TestSaveFileStrPath:
    """Test save_file with string path."""

    def test_save_file_str_path(self, pg_storage):
        storage, _mock_conn = pg_storage
        result = storage.save_file("chat_1", "/mock/test.txt", content=b"hello")
        assert result is True

    def test_save_file_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")
        result = storage.save_file("chat_1", Path("/mock/test.txt"), content=b"hello")
        assert result is False


class TestSaveFeedbackNegative:
    """Test save_feedback with is_positive=False."""

    def test_save_negative_feedback(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.scalar.return_value = 2
        result = storage.save_feedback("user1", "chat_1", 0, False)
        assert result is True

    def test_save_feedback_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")
        result = storage.save_feedback("user1", "chat_1", 0, True)
        assert result is False


class TestErrorPaths:
    """Test exception handling returns safe defaults."""

    def test_delete_chat_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")
        assert storage.delete_chat("user1", "chat_1") is False

    def test_chat_exists_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")
        assert storage.chat_exists("user1", "chat_1") is False

    def test_list_all_chats_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")
        assert storage.list_all_chats("user1") == []

    def test_load_file_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")
        assert storage.load_file("chat_1", "f.txt") is None

    def test_list_files_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")
        assert storage.list_files("chat_1") == []

    def test_delete_file_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")
        assert storage.delete_file("chat_1", "f.txt") is False

    def test_delete_file_not_found(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.rowcount = 0
        assert storage.delete_file("chat_1", "f.txt") is False

    def test_delete_all_files_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")
        assert storage.delete_all_files("chat_1") == 0

    def test_load_all_files_failure(self, pg_storage):
        storage, _ = pg_storage
        storage._engine.connect.side_effect = SQLAlchemyError("DB error")

        with tempfile.TemporaryDirectory() as tmpdir:
            assert storage.load_all_files("chat_1", Path(tmpdir)) == 0

    def test_get_feedback_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")
        assert storage.get_feedback("user1", "chat_1") == {}

    def test_delete_feedback_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")
        assert storage.delete_feedback("user1", "chat_1", 0) is False

    def test_delete_feedback_chat_not_found(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.return_value.first.return_value = None
        assert storage.delete_feedback("user1", "chat_1", 0) is False

    def test_delete_all_feedback_failure(self, pg_storage):
        storage, mock_conn = pg_storage
        mock_conn.execute.side_effect = SQLAlchemyError("DB error")
        assert storage.delete_all_feedback("user1", "chat_1") is False
