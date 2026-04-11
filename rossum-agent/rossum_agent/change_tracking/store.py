from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

from rossum_agent.change_tracking.models import ConfigCommit

if TYPE_CHECKING:
    from datetime import datetime

    import valkey

logger = logging.getLogger(__name__)

# Default TTL for commit data (30 days, matching chat TTL)
DEFAULT_COMMIT_TTL_SECONDS = 30 * 24 * 3600

# Default TTL for entity snapshots (7 days)
DEFAULT_SNAPSHOT_TTL_SECONDS = 7 * 24 * 3600


class CommitStore:
    """Valkey-backed persistence for ConfigCommit objects."""

    def __init__(self, client: valkey.Valkey, ttl_seconds: int = DEFAULT_COMMIT_TTL_SECONDS) -> None:
        self.client = client
        self._ttl = ttl_seconds

    def save_commit(self, commit: ConfigCommit) -> None:
        key = f"config_commit:{commit.environment}:{commit.hash}"
        data = commit.model_dump_json()
        pipe = self.client.pipeline()
        pipe.setex(key, self._ttl, data)
        # Update sorted set index (score = timestamp for ordering)
        index_key = f"config_commits:{commit.environment}"
        pipe.zadd(index_key, {commit.hash: commit.timestamp.timestamp()})
        pipe.expire(index_key, self._ttl)
        # Update latest pointer
        latest_key = f"config_commit_latest:{commit.environment}"
        pipe.setex(latest_key, self._ttl, commit.hash)
        pipe.execute()
        logger.info(f"Saved config commit {commit.hash} for {commit.environment}")

    def get_commit(self, environment: str, commit_hash: str) -> ConfigCommit | None:
        key = f"config_commit:{environment}:{commit_hash}"
        if (data := self.client.get(key)) is None:
            return None
        return ConfigCommit.model_validate_json(cast("bytes", data))

    def get_latest_hash(self, environment: str) -> str | None:
        """Get the hash of the latest commit for an environment."""
        latest_key = f"config_commit_latest:{environment}"
        if (result := self.client.get(latest_key)) is None:
            return None
        return result.decode() if isinstance(result, bytes) else str(result)

    def mark_reverted(self, environment: str, commit_hash: str) -> None:
        commit = self.get_commit(environment, commit_hash)
        if commit is None:
            return  # expired or not found, nothing to do
        commit.reverted = True
        key = f"config_commit:{environment}:{commit_hash}"
        self.client.setex(key, self._ttl, commit.model_dump_json())

    def list_commits(self, environment: str, limit: int = 10) -> list[ConfigCommit]:
        """List recent commits for an environment, newest first."""
        index_key = f"config_commits:{environment}"
        # Get hashes from sorted set, newest first
        hashes = cast("list[bytes]", self.client.zrevrange(index_key, 0, limit - 1))
        if not hashes:
            return []

        commits: list[ConfigCommit] = []
        for h in hashes:
            hash_str = h.decode() if isinstance(h, bytes) else h
            commit = self.get_commit(environment, hash_str)
            if commit is not None:
                commits.append(commit)
        return commits


class SnapshotStore:
    """Valkey-backed entity snapshot store for point-in-time restore.

    Stores full entity snapshots indexed by (entity_type, entity_id, commit_hash),
    enabling restore to any historical version within the TTL window.
    """

    def __init__(self, client: valkey.Valkey, ttl_seconds: int = DEFAULT_SNAPSHOT_TTL_SECONDS) -> None:
        self.client = client
        self._ttl = ttl_seconds

    def save_snapshot(
        self,
        environment: str,
        entity_type: str,
        entity_id: str,
        commit_hash: str,
        timestamp: datetime,
        data: dict,
    ) -> None:
        key = f"snapshot:{environment}:{entity_type}:{entity_id}:{commit_hash}"
        index_key = f"snapshot_versions:{environment}:{entity_type}:{entity_id}"
        pipe = self.client.pipeline()
        pipe.setex(key, self._ttl, json.dumps(data, default=str))
        pipe.zadd(index_key, {commit_hash: timestamp.timestamp()})
        pipe.expire(index_key, self._ttl)
        pipe.execute()

    def get_snapshot(self, environment: str, entity_type: str, entity_id: str, commit_hash: str) -> dict | None:
        key = f"snapshot:{environment}:{entity_type}:{entity_id}:{commit_hash}"
        if (data := self.client.get(key)) is None:
            return None
        return json.loads(cast("bytes", data))

    def get_snapshot_at(self, environment: str, entity_type: str, entity_id: str, at_timestamp: float) -> dict | None:
        """Get the most recent snapshot of an entity at or before the given Unix timestamp."""
        index_key = f"snapshot_versions:{environment}:{entity_type}:{entity_id}"
        results = self.client.zrevrangebyscore(index_key, at_timestamp, "-inf", start=0, num=1)
        if not results:
            return None
        commit_hash = results[0].decode() if isinstance(results[0], bytes) else str(results[0])
        return self.get_snapshot(environment, entity_type, entity_id, commit_hash)

    def get_earliest_version(self, environment: str, entity_type: str, entity_id: str) -> tuple[str, float] | None:
        """Get the (commit_hash, timestamp) of the oldest recorded snapshot for an entity."""
        index_key = f"snapshot_versions:{environment}:{entity_type}:{entity_id}"
        results = cast("list[tuple[bytes, float]]", self.client.zrange(index_key, 0, 0, withscores=True))
        if not results:
            return None
        h, score = results[0]
        return (h.decode() if isinstance(h, bytes) else str(h), score)

    def list_versions(
        self, environment: str, entity_type: str, entity_id: str, limit: int = 20
    ) -> list[tuple[str, float]]:
        """List recent versions of an entity, newest first.

        Returns (commit_hash, timestamp) pairs.
        """
        index_key = f"snapshot_versions:{environment}:{entity_type}:{entity_id}"
        results = self.client.zrevrange(index_key, 0, limit - 1, withscores=True)
        return [
            (h.decode() if isinstance(h, bytes) else str(h), score)
            for h, score in cast("list[tuple[bytes, float]]", results)
        ]
