"""Service for creating config commits from tracked changes."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from rossum_agent.bedrock_client import create_bedrock_client, get_small_model_id
from rossum_agent.change_tracking.models import ConfigCommit, compute_commit_hash

if TYPE_CHECKING:
    from rossum_agent.change_tracking.models import EntityChange
    from rossum_agent.change_tracking.store import CommitStore, SnapshotStore
    from rossum_agent.rossum_mcp_integration.connection import MCPConnection

_EPOCH = datetime.min.replace(tzinfo=UTC)

logger = logging.getLogger(__name__)


def _format_changes_for_message(changes: list[EntityChange]) -> str:
    """Format changes into a concise summary for the LLM."""
    lines: list[str] = []
    for c in changes:
        name_part = f" ({c.entity_name})" if c.entity_name else ""
        lines.append(f"- {c.operation} {c.entity_type} {c.entity_id}{name_part}")
    return "\n".join(lines)


def _fallback_commit_message(changes: list[EntityChange]) -> str:
    """Build a simple commit message without LLM."""
    entity_types = {c.entity_type for c in changes}
    ops = {c.operation for c in changes}
    op_str = "/".join(sorted(ops))
    return f"{op_str} {', '.join(sorted(entity_types))}"


def generate_commit_message(changes: list[EntityChange], user_request: str) -> str:
    """Generate a commit message using a lightweight LLM call.

    Falls back to a simple auto-generated message if the LLM call fails.
    """
    try:
        client = create_bedrock_client()
        changes_summary = _format_changes_for_message(changes)

        response = client.messages.create(
            model=get_small_model_id(),
            max_tokens=150,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Write a one-line git commit message (max 72 chars) for this config change.\n\n"
                        f"User request: {user_request}\n\n"
                        f"Changes:\n{changes_summary}\n\n"
                        f"Reply with ONLY the commit message, no quotes or prefix."
                    ),
                }
            ],
        )

        first_block = response.content[0]
        message = first_block.text.strip()  # ty:ignore[unresolved-attribute] - first block is always TextBlock for this prompt
        if len(message) > 72:
            message = message[:69] + "..."
        return message
    except Exception:
        logger.warning("LLM commit message generation failed, using fallback", exc_info=True)
        return _fallback_commit_message(changes)


class CommitService:
    """Orchestrates creating config commits from tracked changes."""

    def __init__(self, store: CommitStore, snapshot_store: SnapshotStore) -> None:
        self.store = store
        self.snapshot_store = snapshot_store

    def create_commit(
        self, tracking_connection: MCPConnection, chat_id: str, user_request: str, environment: str
    ) -> ConfigCommit | None:
        """Create a commit from accumulated changes. Returns None if no writes occurred."""
        if not (changes := tracking_connection.get_changes()):
            return None

        message = generate_commit_message(changes, user_request)
        timestamp = datetime.now(UTC)

        commit = ConfigCommit(
            hash=compute_commit_hash(changes, timestamp),
            parent=self.store.get_latest_hash(environment),
            chat_id=chat_id,
            timestamp=timestamp,
            message=message,
            user_request=user_request,
            environment=environment,
            changes=changes,
        )
        self.store.save_commit(commit)
        self._save_snapshots(commit)
        tracking_connection.clear_changes()

        logger.info(f"Config commit {commit.hash}: {commit.message}")
        return commit

    def _resolve_parent(self, commit: ConfigCommit) -> tuple[str, datetime]:
        """Return (hash, timestamp) for the parent commit, or a sentinel if none."""
        if commit.parent:
            parent = self.store.get_commit(commit.environment, commit.parent)
            if parent:
                return parent.hash, parent.timestamp
        return "initial", _EPOCH

    def _save_snapshots(self, commit: ConfigCommit) -> None:
        for change in commit.changes:
            # For the first tracked update of an entity, also save the pre-change state
            # so show_entity_history exposes the full history including before agent touched it.
            if (
                change.operation == "update"
                and change.before is not None
                and self.snapshot_store.get_earliest_version(commit.environment, change.entity_type, change.entity_id)
                is None
            ):
                parent_hash, parent_ts = self._resolve_parent(commit)
                self.snapshot_store.save_snapshot(
                    commit.environment,
                    change.entity_type,
                    change.entity_id,
                    parent_hash,
                    parent_ts,
                    change.before,
                )

            if change.after is not None:
                self.snapshot_store.save_snapshot(
                    commit.environment,
                    change.entity_type,
                    change.entity_id,
                    commit.hash,
                    commit.timestamp,
                    change.after,
                )
