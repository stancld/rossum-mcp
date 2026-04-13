"""Tests for rossum_agent.change_tracking.store module."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

from rossum_agent.change_tracking.models import ConfigCommit, EntityChange
from rossum_agent.change_tracking.store import (
    DEFAULT_COMMIT_TTL_SECONDS,
    DEFAULT_SNAPSHOT_TTL_SECONDS,
    CommitStore,
    SnapshotStore,
)


def _make_change(**overrides) -> EntityChange:
    defaults = {
        "entity_type": "schema",
        "entity_id": "100",
        "entity_name": "Invoice",
        "operation": "update",
        "before": {"fields": []},
        "after": {"fields": [{"name": "total"}]},
    }
    defaults.update(overrides)
    return EntityChange(**defaults)


def _make_commit(**overrides) -> ConfigCommit:
    defaults = {
        "hash": "abc123def456",
        "parent": None,
        "chat_id": "chat_20250213",
        "timestamp": datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC),
        "message": "Updated schema fields",
        "user_request": "Add a new field",
        "environment": "https://example.rossum.app/api/v1",
        "changes": [_make_change()],
    }
    defaults.update(overrides)
    return ConfigCommit(**defaults)


def _make_mock_client() -> MagicMock:
    client = MagicMock()
    client.pipeline.return_value = MagicMock()
    return client


class TestCommitStoreSaveAndGet:
    """Test save_commit and get_commit roundtrip."""

    def test_save_commit(self):
        client = _make_mock_client()
        store = CommitStore(client)
        commit = _make_commit()

        store.save_commit(commit)

        pipe = client.pipeline.return_value
        pipe.setex.assert_any_call(
            f"config_commit:{commit.environment}:{commit.hash}",
            DEFAULT_COMMIT_TTL_SECONDS,
            commit.model_dump_json(),
        )
        pipe.zadd.assert_called_once_with(
            f"config_commits:{commit.environment}",
            {commit.hash: commit.timestamp.timestamp()},
        )
        pipe.expire.assert_called_once_with(
            f"config_commits:{commit.environment}",
            DEFAULT_COMMIT_TTL_SECONDS,
        )
        pipe.setex.assert_any_call(
            f"config_commit_latest:{commit.environment}",
            DEFAULT_COMMIT_TTL_SECONDS,
            commit.hash,
        )
        pipe.execute.assert_called_once()

    def test_get_commit_roundtrip(self):
        client = _make_mock_client()
        store = CommitStore(client)
        commit = _make_commit()
        env = commit.environment

        client.get.return_value = commit.model_dump_json().encode()

        result = store.get_commit(env, commit.hash)

        assert result is not None
        assert result.hash == commit.hash
        assert result.parent == commit.parent
        assert result.chat_id == commit.chat_id
        assert result.timestamp == commit.timestamp
        assert result.message == commit.message
        assert result.environment == commit.environment
        assert len(result.changes) == 1
        assert result.changes[0].entity_type == "schema"

    def test_get_commit_not_found(self):
        client = _make_mock_client()
        store = CommitStore(client)

        client.get.return_value = None

        result = store.get_commit("https://example.rossum.app/api/v1", "nonexistent")
        assert result is None


class TestCommitStoreGetLatestHash:
    """Test get_latest_hash."""

    def test_get_latest_hash(self):
        client = _make_mock_client()
        store = CommitStore(client)

        client.get.return_value = b"abc123def456"

        result = store.get_latest_hash("https://example.rossum.app/api/v1")
        assert result == "abc123def456"
        client.get.assert_called_once_with("config_commit_latest:https://example.rossum.app/api/v1")

    def test_get_latest_hash_none(self):
        client = _make_mock_client()
        store = CommitStore(client)

        client.get.return_value = None

        result = store.get_latest_hash("https://example.rossum.app/api/v1")
        assert result is None

    def test_get_latest_hash_string_response(self):
        client = _make_mock_client()
        store = CommitStore(client)

        client.get.return_value = "abc123def456"

        result = store.get_latest_hash("https://example.rossum.app/api/v1")
        assert result == "abc123def456"


class TestCommitStoreListCommits:
    """Test list_commits."""

    def test_list_commits_reverse_chronological(self):
        client = _make_mock_client()
        store = CommitStore(client)
        env = "https://example.rossum.app/api/v1"

        commit_old = _make_commit(
            hash="old_hash",
            timestamp=datetime(2025, 2, 12, 10, 0, 0, tzinfo=UTC),
            message="Old commit",
        )
        commit_new = _make_commit(
            hash="new_hash",
            timestamp=datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC),
            message="New commit",
        )

        # zrevrange returns newest first
        client.zrevrange.return_value = [b"new_hash", b"old_hash"]

        def get_side_effect(key):
            if key == f"config_commit:{env}:new_hash":
                return commit_new.model_dump_json().encode()
            if key == f"config_commit:{env}:old_hash":
                return commit_old.model_dump_json().encode()
            return None

        client.get.side_effect = get_side_effect

        result = store.list_commits(env)

        assert len(result) == 2
        assert result[0].hash == "new_hash"
        assert result[1].hash == "old_hash"
        client.zrevrange.assert_called_once_with(f"config_commits:{env}", 0, 9)

    def test_list_commits_with_limit(self):
        client = _make_mock_client()
        store = CommitStore(client)
        env = "https://example.rossum.app/api/v1"

        commit = _make_commit(hash="only_hash")
        client.zrevrange.return_value = [b"only_hash"]
        client.get.return_value = commit.model_dump_json().encode()

        result = store.list_commits(env, limit=1)

        assert len(result) == 1
        client.zrevrange.assert_called_once_with(f"config_commits:{env}", 0, 0)

    def test_list_commits_empty(self):
        client = _make_mock_client()
        store = CommitStore(client)

        client.zrevrange.return_value = []

        result = store.list_commits("https://example.rossum.app/api/v1")
        assert result == []

    def test_list_commits_skips_missing(self):
        client = _make_mock_client()
        store = CommitStore(client)
        env = "https://example.rossum.app/api/v1"

        commit = _make_commit(hash="existing")
        client.zrevrange.return_value = [b"existing", b"expired"]

        def get_side_effect(key):
            if key == f"config_commit:{env}:existing":
                return commit.model_dump_json().encode()
            return None

        client.get.side_effect = get_side_effect

        result = store.list_commits(env)

        assert len(result) == 1
        assert result[0].hash == "existing"

    def test_list_commits_string_hashes(self):
        client = _make_mock_client()
        store = CommitStore(client)
        env = "https://example.rossum.app/api/v1"

        commit = _make_commit(hash="str_hash")
        # Some Valkey clients may return strings instead of bytes
        client.zrevrange.return_value = ["str_hash"]
        client.get.return_value = commit.model_dump_json().encode()

        result = store.list_commits(env)

        assert len(result) == 1
        assert result[0].hash == "str_hash"


class TestCommitStoreMarkReverted:
    """Test mark_reverted."""

    def test_mark_reverted_sets_flag_and_persists(self):
        client = _make_mock_client()
        store = CommitStore(client)
        commit = _make_commit()
        env = commit.environment

        client.get.return_value = commit.model_dump_json().encode()

        store.mark_reverted(env, commit.hash)

        # Verify setex was called with reverted=True in the serialized data
        client.setex.assert_called_once()
        key, ttl, data = client.setex.call_args.args
        assert key == f"config_commit:{env}:{commit.hash}"
        assert ttl == DEFAULT_COMMIT_TTL_SECONDS
        saved = ConfigCommit.model_validate_json(data)
        assert saved.reverted is True

    def test_mark_reverted_noop_when_commit_not_found(self):
        client = _make_mock_client()
        store = CommitStore(client)

        client.get.return_value = None

        store.mark_reverted("https://example.rossum.app/api/v1", "nonexistent")

        client.setex.assert_not_called()


class TestCommitStoreCustomTTL:
    """Test custom TTL configuration."""

    def test_custom_ttl(self):
        client = _make_mock_client()
        custom_ttl = 7 * 24 * 3600  # 7 days
        store = CommitStore(client, ttl_seconds=custom_ttl)
        commit = _make_commit()

        store.save_commit(commit)

        pipe = client.pipeline.return_value
        pipe.setex.assert_any_call(
            f"config_commit:{commit.environment}:{commit.hash}",
            custom_ttl,
            commit.model_dump_json(),
        )


class TestSnapshotStoreSaveAndGet:
    """Test SnapshotStore save/get roundtrip."""

    def test_save_snapshot(self):
        client = _make_mock_client()
        store = SnapshotStore(client)
        env = "https://example.rossum.app/api/v1"
        ts = datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC)

        store.save_snapshot(env, "schema", "100", "abc123", ts, {"content": [{"id": "f1"}]})

        pipe = client.pipeline.return_value
        pipe.setex.assert_called_once()
        key = pipe.setex.call_args.args[0]
        assert key == "snapshot:https://example.rossum.app/api/v1:schema:100:abc123"
        assert pipe.setex.call_args.args[1] == DEFAULT_SNAPSHOT_TTL_SECONDS
        pipe.zadd.assert_called_once_with(
            "snapshot_versions:https://example.rossum.app/api/v1:schema:100",
            {"abc123": ts.timestamp()},
        )
        pipe.expire.assert_called_once_with(
            "snapshot_versions:https://example.rossum.app/api/v1:schema:100",
            DEFAULT_SNAPSHOT_TTL_SECONDS,
        )
        pipe.execute.assert_called_once()

    def test_get_snapshot_roundtrip(self):
        client = _make_mock_client()
        store = SnapshotStore(client)
        env = "https://example.rossum.app/api/v1"
        data = {"content": [{"id": "f1"}]}

        client.get.return_value = json.dumps(data).encode()

        result = store.get_snapshot(env, "schema", "100", "abc123")

        assert result == data
        client.get.assert_called_once_with("snapshot:https://example.rossum.app/api/v1:schema:100:abc123")

    def test_get_snapshot_not_found(self):
        client = _make_mock_client()
        store = SnapshotStore(client)

        client.get.return_value = None

        result = store.get_snapshot("https://example.rossum.app/api/v1", "schema", "100", "nonexistent")
        assert result is None


class TestSnapshotStoreGetSnapshotAt:
    """Test get_snapshot_at."""

    def test_finds_snapshot_at_timestamp(self):
        client = _make_mock_client()
        store = SnapshotStore(client)
        env = "https://example.rossum.app/api/v1"
        data = {"content": [{"id": "f1"}]}

        client.zrevrangebyscore.return_value = [b"abc123"]
        client.get.return_value = json.dumps(data).encode()

        result = store.get_snapshot_at(env, "schema", "100", 1000.0)

        assert result == data
        client.zrevrangebyscore.assert_called_once_with(
            f"snapshot_versions:{env}:schema:100", 1000.0, "-inf", start=0, num=1
        )
        client.get.assert_called_once_with(f"snapshot:{env}:schema:100:abc123")

    def test_returns_none_when_no_snapshot_before_timestamp(self):
        client = _make_mock_client()
        store = SnapshotStore(client)

        client.zrevrangebyscore.return_value = []

        result = store.get_snapshot_at("env", "schema", "100", 0.0)
        assert result is None

    def test_returns_none_when_snapshot_data_expired(self):
        client = _make_mock_client()
        store = SnapshotStore(client)

        client.zrevrangebyscore.return_value = [b"abc123"]
        client.get.return_value = None

        result = store.get_snapshot_at("env", "schema", "100", 1000.0)
        assert result is None


class TestSnapshotStoreGetEarliestVersion:
    """Test get_earliest_version."""

    def test_returns_oldest_entry(self):
        client = _make_mock_client()
        store = SnapshotStore(client)
        env = "https://example.rossum.app/api/v1"

        client.zrange.return_value = [(b"old_hash", 500.0)]

        result = store.get_earliest_version(env, "schema", "100")

        assert result == ("old_hash", 500.0)
        client.zrange.assert_called_once_with(f"snapshot_versions:{env}:schema:100", 0, 0, withscores=True)

    def test_returns_none_when_empty(self):
        client = _make_mock_client()
        store = SnapshotStore(client)

        client.zrange.return_value = []

        result = store.get_earliest_version("env", "schema", "100")
        assert result is None

    def test_handles_string_hash(self):
        client = _make_mock_client()
        store = SnapshotStore(client)

        client.zrange.return_value = [("str_hash", 100.0)]

        result = store.get_earliest_version("env", "schema", "100")
        assert result == ("str_hash", 100.0)


class TestSnapshotStoreListVersions:
    """Test list_versions."""

    def test_list_versions(self):
        client = _make_mock_client()
        store = SnapshotStore(client)
        env = "https://example.rossum.app/api/v1"

        ts1 = datetime(2025, 2, 12, 10, 0, 0, tzinfo=UTC).timestamp()
        ts2 = datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC).timestamp()
        client.zrevrange.return_value = [(b"new_hash", ts2), (b"old_hash", ts1)]

        result = store.list_versions(env, "schema", "100")

        assert len(result) == 2
        assert result[0] == ("new_hash", ts2)
        assert result[1] == ("old_hash", ts1)
        client.zrevrange.assert_called_once_with(
            "snapshot_versions:https://example.rossum.app/api/v1:schema:100", 0, 19, withscores=True
        )

    def test_list_versions_empty(self):
        client = _make_mock_client()
        store = SnapshotStore(client)

        client.zrevrange.return_value = []

        result = store.list_versions("https://example.rossum.app/api/v1", "schema", "100")
        assert result == []

    def test_list_versions_with_limit(self):
        client = _make_mock_client()
        store = SnapshotStore(client)
        env = "https://example.rossum.app/api/v1"

        client.zrevrange.return_value = [(b"hash1", 1000.0)]

        result = store.list_versions(env, "schema", "100", limit=1)

        assert len(result) == 1
        client.zrevrange.assert_called_once_with(f"snapshot_versions:{env}:schema:100", 0, 0, withscores=True)


class TestSnapshotStoreGetSnapshotAtStringHash:
    """Test get_snapshot_at handles string-typed hash from Valkey."""

    def test_string_hash_response(self):
        client = _make_mock_client()
        store = SnapshotStore(client)
        env = "https://example.rossum.app/api/v1"
        data = {"content": [{"id": "f1"}]}

        # Some Valkey clients return strings instead of bytes
        client.zrevrangebyscore.return_value = ["str_hash"]
        client.get.return_value = json.dumps(data).encode()

        result = store.get_snapshot_at(env, "schema", "100", 1000.0)

        assert result == data
        client.get.assert_called_once_with(f"snapshot:{env}:schema:100:str_hash")


class TestSnapshotStoreListVersionsStringHash:
    """Test list_versions handles string-typed hashes from Valkey."""

    def test_string_hashes(self):
        client = _make_mock_client()
        store = SnapshotStore(client)
        env = "https://example.rossum.app/api/v1"

        client.zrevrange.return_value = [("str_hash1", 2000.0), ("str_hash2", 1000.0)]

        result = store.list_versions(env, "schema", "100")

        assert len(result) == 2
        assert result[0] == ("str_hash1", 2000.0)
        assert result[1] == ("str_hash2", 1000.0)


class TestSnapshotStoreCustomTTL:
    """Test custom TTL for snapshots."""

    def test_custom_ttl(self):
        client = _make_mock_client()
        custom_ttl = 24 * 3600  # 1 day
        store = SnapshotStore(client, ttl_seconds=custom_ttl)
        ts = datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC)

        store.save_snapshot("env", "schema", "100", "abc", ts, {"data": True})

        pipe = client.pipeline.return_value
        pipe.setex.assert_called_once()
        assert pipe.setex.call_args.args[1] == custom_ttl
        pipe.expire.assert_called_once()
        assert pipe.expire.call_args.args[1] == custom_ttl
