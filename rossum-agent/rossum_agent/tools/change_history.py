"""Agent tools for querying and managing configuration change history."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from anthropic import beta_tool
from rossum_api import APIClientError, AsyncRossumAPIClient
from rossum_api.domain_logic.resources import Resource
from rossum_api.dtos import Token
from rossum_mcp.tools.validation import sanitize_schema_content

from rossum_agent.change_tracking.models import EntityChange
from rossum_agent.rossum_mcp_integration import unwrap
from rossum_agent.tools.core import get_context
from rossum_agent.utils import compute_json_diff

if TYPE_CHECKING:
    from typing import Literal

    from rossum_agent.change_tracking.store import CommitStore, SnapshotStore

logger = logging.getLogger(__name__)

# Entity types that can be reverted programmatically via rossum_api
_ENTITY_TYPE_TO_RESOURCE: dict[str, Resource] = {
    "schema": Resource.Schema,
    "queue": Resource.Queue,
    "hook": Resource.Hook,
    "rule": Resource.Rule,
    "inbox": Resource.Inbox,
    "workspace": Resource.Workspace,
    "connector": Resource.Connector,
    "email_template": Resource.EmailTemplate,
}

# SDK method names for recreating deleted entities
_ENTITY_TYPE_TO_CREATE_METHOD: dict[str, str] = {
    "schema": "create_new_schema",
    "queue": "create_new_queue",
    "hook": "create_new_hook",
    "rule": "create_new_rule",
    "inbox": "create_new_inbox",
    "workspace": "create_new_workspace",
    "connector": "create_new_connector",
    "email_template": "create_new_email_template",
}

# SDK method names for deleting created entities
_ENTITY_TYPE_TO_DELETE_METHOD: dict[str, str] = {
    "schema": "delete_schema",
    "queue": "delete_queue",
    "hook": "delete_hook",
    "rule": "delete_rule",
    "workspace": "delete_workspace",
}

# Fields that are read-only and should never be included in a revert PATCH
_READ_ONLY_FIELDS = frozenset(
    {
        "url",
        "id",
        "organization",
        "created_at",
        "modified_at",
        "modified_by",
        "created_by",
    }
)


def _flush_pending_changes() -> None:
    """Commit any pending tracked changes to the store.

    Called before reading history or reverting so the agent can see
    changes made earlier in the same run.
    """
    ctx = get_context()
    if not ctx.mcp_connection or not ctx.mcp_connection.has_changes():
        return

    ctx.mcp_connection.flush_and_commit("auto-flush before history query")


def _unwrap_snapshot(data: dict) -> dict:
    """Unwrap FastMCP and unified-get response wrappers from a snapshot.

    Handles two layers:
    1. FastMCP's {"result": ...} wrapper
    2. Unified get tool's {"entity": ..., "id": ..., "data": {...}} wrapper

    Defense-in-depth for snapshots stored in Valkey before the _call_mcp fix.
    """
    inner = unwrap(data)
    if "data" in inner and "entity" in inner and isinstance(inner["data"], dict):
        return inner["data"]
    return inner


def _compute_revert_patch(before: dict, after: dict) -> dict:
    """Compute the minimal PATCH payload to revert after→before.

    Returns only fields that differ between before and after,
    excluding read-only fields.
    """
    before_inner = unwrap(before)
    after_inner = unwrap(after)
    patch: dict = {}
    for key, before_val in before_inner.items():
        if key in _READ_ONLY_FIELDS:
            continue
        if after_inner.get(key) != before_val:
            patch[key] = before_val
    return patch


_SCHEMA_REVERT_RETRIES = 5


async def _revert_schema_with_retry(client: AsyncRossumAPIClient, schema_id: int, patch: dict) -> None:
    """Apply a schema revert PATCH with fetch-then-patch and retry on 412.

    A GET before PATCH registers the current state with the server, preventing
    412 Precondition Failed from rapid successive updates. Retries with backoff
    if concurrent modification is detected.
    """
    for attempt in range(_SCHEMA_REVERT_RETRIES):
        await client._http_client.request_json("GET", f"schemas/{schema_id}")
        try:
            await client._http_client.update(Resource.Schema, schema_id, patch)
            return
        except APIClientError as e:
            if e.status_code == 412 and attempt < _SCHEMA_REVERT_RETRIES - 1:
                logger.warning(
                    f"Schema {schema_id} revert got 412 (concurrent modification), "
                    f"retrying ({attempt + 1}/{_SCHEMA_REVERT_RETRIES})..."
                )
                await asyncio.sleep(0.5 * (attempt + 1) + random.uniform(0, 0.5))
                continue
            raise


async def _revert_entity_update(api_base_url: str, token: str, change: EntityChange) -> dict:
    """Revert an entity update by patching changed fields back to the before state."""
    entity_id = int(change.entity_id)
    resource = _ENTITY_TYPE_TO_RESOURCE[change.entity_type]

    if not isinstance(change.before, dict) or not isinstance(change.after, dict):
        msg = f"Cannot revert {change.entity_type} {entity_id}: missing before/after snapshot"
        raise ValueError(msg)

    client = AsyncRossumAPIClient(base_url=api_base_url, credentials=Token(token=token))

    if change.entity_type == "schema":
        before_inner = _unwrap_snapshot(change.before)
        content = before_inner.get("content")
        if not isinstance(content, list):
            msg = f"Cannot revert schema {entity_id}: 'before' snapshot has no content"
            raise ValueError(msg)
        await _revert_schema_with_retry(client, entity_id, {"content": sanitize_schema_content(content)})
        return {"status": "reverted", "entity_type": change.entity_type, "entity_id": change.entity_id}

    patch = _compute_revert_patch(change.before, change.after)
    if not patch:
        return {"status": "no_changes", "entity_type": change.entity_type, "entity_id": change.entity_id}

    await client._http_client.update(resource, entity_id, patch)
    return {"status": "reverted", "entity_type": change.entity_type, "entity_id": change.entity_id}


async def _revert_entity_delete(api_base_url: str, token: str, change: EntityChange) -> dict:
    """Revert an entity deletion by recreating it from the before snapshot."""
    create_method = _ENTITY_TYPE_TO_CREATE_METHOD[change.entity_type]

    if not isinstance(change.before, dict):
        msg = f"Cannot recreate {change.entity_type} {change.entity_id}: missing before snapshot"
        raise ValueError(msg)

    data = unwrap(change.before)
    cleaned = {k: v for k, v in data.items() if k not in _READ_ONLY_FIELDS}

    client = AsyncRossumAPIClient(base_url=api_base_url, credentials=Token(token=token))
    result = await getattr(client, create_method)(cleaned)
    new_id = getattr(result, "id", None)
    return {
        "status": "recreated",
        "entity_type": change.entity_type,
        "entity_id": change.entity_id,
        "new_entity_id": str(new_id) if new_id is not None else None,
    }


async def _revert_entity_create(api_base_url: str, token: str, change: EntityChange) -> dict:
    """Revert an entity creation by deleting it."""
    delete_method = _ENTITY_TYPE_TO_DELETE_METHOD[change.entity_type]
    entity_id = int(change.entity_id)

    client = AsyncRossumAPIClient(base_url=api_base_url, credentials=Token(token=token))
    await getattr(client, delete_method)(entity_id)
    return {"status": "deleted", "entity_type": change.entity_type, "entity_id": change.entity_id}


@beta_tool
def show_change_history(limit: int = 10) -> str:
    """Show recent configuration changes made by the agent.

    Args:
        limit: Maximum number of commits to show (default 10).

    Returns:
        JSON list of recent commits with hash, message, timestamp, and change count.
    """
    ctx = get_context()
    if ctx.commit_store is None or ctx.rossum_environment is None:
        return json.dumps({"error": "Change tracking not available"})

    _flush_pending_changes()

    commits = ctx.commit_store.list_commits(ctx.rossum_environment, limit=limit)
    if not commits:
        return json.dumps({"message": "No configuration changes recorded"})

    return json.dumps(
        [
            {
                "hash": c.hash,
                "message": c.message,
                "timestamp": c.timestamp.isoformat(),
                "changes": len(c.changes),
                "user_request": c.user_request[:100],
                "reverted": c.reverted,
            }
            for c in commits
        ]
    )


@beta_tool
def show_commit_details(commit_hash: str) -> str:
    """Show full details and diffs for a specific configuration commit.

    Args:
        commit_hash: The hash of the commit to inspect.

    Returns:
        JSON with commit metadata and before/after snapshots for each change.
    """
    ctx = get_context()
    if ctx.commit_store is None or ctx.rossum_environment is None:
        return json.dumps({"error": "Change tracking not available"})

    commit = ctx.commit_store.get_commit(ctx.rossum_environment, commit_hash)
    if commit is None:
        return json.dumps({"error": f"Commit {commit_hash} not found"})

    return json.dumps(
        {
            "hash": commit.hash,
            "message": commit.message,
            "timestamp": commit.timestamp.isoformat(),
            "user_request": commit.user_request,
            "parent": commit.parent,
            "changes": [c.model_dump() for c in commit.changes],
        }
    )


def _can_direct_revert(change: EntityChange) -> bool:
    """Check if a change can be reverted programmatically."""
    if change.operation == "update":
        return change.entity_type in _ENTITY_TYPE_TO_RESOURCE and change.before is not None
    if change.operation == "delete":
        return change.entity_type in _ENTITY_TYPE_TO_CREATE_METHOD and change.before is not None
    if change.operation == "create":
        return change.entity_type in _ENTITY_TYPE_TO_DELETE_METHOD
    return False


def _build_plan_action(change: EntityChange) -> dict | None:
    """Build a plan-based revert action for changes that can't be reverted programmatically."""
    if change.operation == "create":
        return {
            "action": "delete",
            "entity_type": change.entity_type,
            "entity_id": change.entity_id,
            "entity_name": change.entity_name,
            "tool": f"delete_{change.entity_type}",
            "args": {f"{change.entity_type}_id": change.entity_id},
        }
    if change.operation == "delete" and change.before:
        return {
            "action": "recreate",
            "entity_type": change.entity_type,
            "entity_id": change.entity_id,
            "entity_name": change.entity_name,
            "tool": f"create_{change.entity_type}",
            "original_data": change.before,
        }
    if change.operation == "update" and change.before:
        return {
            "action": "restore",
            "entity_type": change.entity_type,
            "entity_id": change.entity_id,
            "entity_name": change.entity_name,
            "tool": f"update_{change.entity_type}",
            "restore_to": change.before,
        }
    return None


def _collapsed_operation(
    first: Literal["create", "update", "delete"],
    last: Literal["create", "update", "delete"],
) -> Literal["create", "update", "delete"]:
    """Derive the net operation from a sequence of operations on the same entity."""
    if first == last:
        return first
    if first == "create":
        # create → update = still a create; create → delete = no-op (handled later)
        return "create" if last == "update" else "delete"
    if first == "update" and last == "delete":
        return "delete"
    # update → create or delete → * are unusual but default to last
    return last


def _deduplicate_changes(changes: list[EntityChange]) -> list[EntityChange]:
    """Collapse multiple changes to the same entity into one.

    When an entity is modified multiple times in a single commit (e.g. prune
    then patch), only the first "before" snapshot represents the pre-commit
    state. We keep first-seen before + last-seen after, and derive the net
    operation from the sequence.

    Safety net: if an entity was created then deleted in the same commit
    (before=None, after=None), it's a no-op and is dropped entirely.
    """
    seen: dict[tuple[str, str], int] = {}
    result: list[EntityChange] = []
    for change in changes:
        key = (change.entity_type, change.entity_id)
        if key in seen:
            idx = seen[key]
            existing = result[idx]
            result[idx] = EntityChange(
                entity_type=change.entity_type,
                entity_id=change.entity_id,
                entity_name=change.entity_name or existing.entity_name,
                operation=_collapsed_operation(existing.operation, change.operation),
                before=existing.before,
                after=change.after,
            )
        else:
            seen[key] = len(result)
            result.append(change)

    # Drop no-ops: entity created and then deleted → net effect is nothing
    return [c for c in result if c.before is not None or c.after is not None]


@beta_tool
def revert_commit(commit_hash: str) -> str:
    """Revert a configuration commit by applying inverse operations.

    Updates, creates, and deletes of known entity types are reverted programmatically
    when SDK methods are available. Unsupported operations produce a revert plan for
    the agent to execute.

    Args:
        commit_hash: Hash of the commit to revert.

    Returns:
        JSON with revert results (executed reverts and remaining plan actions).
    """
    ctx = get_context()
    if ctx.commit_store is None or ctx.rossum_environment is None:
        return json.dumps({"error": "Change tracking not available"})

    _flush_pending_changes()

    if (commit := ctx.commit_store.get_commit(ctx.rossum_environment, commit_hash)) is None:
        return json.dumps({"error": f"Commit {commit_hash} not found"})

    credentials = ctx.get_rossum_credentials()
    loop = ctx.mcp_event_loop

    # Deduplicate: for each entity, keep only the earliest "before" and latest operation
    deduped = _deduplicate_changes(commit.changes)

    executed: list[dict] = []
    plan_actions: list[dict] = []
    errors: list[dict] = []

    for i, change in enumerate(deduped):
        if i > 0:
            # Stagger reverts to avoid 412 from rapid successive updates to the same entity
            time.sleep(0.5)

        if _can_direct_revert(change) and credentials and loop:
            api_base_url, token = credentials
            try:
                if change.operation == "update":
                    coro = _revert_entity_update(api_base_url, token, change)
                elif change.operation == "delete":
                    coro = _revert_entity_delete(api_base_url, token, change)
                else:
                    coro = _revert_entity_create(api_base_url, token, change)
                result = asyncio.run_coroutine_threadsafe(coro, loop).result()
                executed.append(result)
            except Exception as e:
                logger.exception(f"Failed to revert {change.entity_type}:{change.entity_id}")
                errors.append(
                    {
                        "entity_type": change.entity_type,
                        "entity_id": change.entity_id,
                        "error": str(e),
                    }
                )
        else:
            if action := _build_plan_action(change):
                plan_actions.append(action)

    ctx.commit_store.mark_reverted(ctx.rossum_environment, commit_hash)

    response: dict = {
        "status": "completed" if not plan_actions and not errors else "partial",
        "commit_hash": commit_hash,
        "message": f"Reverting: {commit.message}",
        "executed": executed,
    }
    if errors:
        response["errors"] = errors
    if plan_actions:
        response["remaining_actions"] = plan_actions
        response["instructions"] = "Execute each remaining action above using the specified MCP tools."

    return json.dumps(response)


@beta_tool
def show_entity_history(entity_type: str, entity_id: str, limit: int = 10) -> str:
    """Show version history for a specific entity.

    Lists all recorded snapshots within the retention window, enabling
    restore to any historical version via restore_entity_version.

    Args:
        entity_type: Entity type (e.g. "schema", "queue", "hook").
        entity_id: Entity ID.
        limit: Maximum number of versions to return (default 10).

    Returns:
        JSON list of versions with commit_hash, timestamp, and commit message.
    """
    ctx = get_context()
    if ctx.snapshot_store is None or ctx.commit_store is None or ctx.rossum_environment is None:
        return json.dumps({"error": "Snapshot tracking not available"})

    _flush_pending_changes()

    versions = ctx.snapshot_store.list_versions(ctx.rossum_environment, entity_type, entity_id, limit=limit)
    if not versions:
        return json.dumps({"message": f"No snapshots found for {entity_type} {entity_id}"})

    result: list[dict] = []
    for commit_hash, ts in versions:
        commit = ctx.commit_store.get_commit(ctx.rossum_environment, commit_hash)
        available = (
            ctx.snapshot_store.get_snapshot(ctx.rossum_environment, entity_type, entity_id, commit_hash) is not None
        )
        result.append(
            {
                "commit_hash": commit_hash,
                "timestamp": datetime.fromtimestamp(ts, tz=UTC).isoformat(),
                "commit_message": commit.message if commit else None,
                "available": available,
            }
        )

    return json.dumps(result)


async def _restore_entity(api_base_url: str, token: str, entity_type: str, entity_id: str, snapshot: dict) -> dict:
    """Restore an entity to a snapshot state by PATCHing changed fields."""
    resource = _ENTITY_TYPE_TO_RESOURCE.get(entity_type)
    if resource is None:
        msg = f"Unsupported entity type for restore: {entity_type}"
        raise ValueError(msg)

    int_id = int(entity_id)
    client = AsyncRossumAPIClient(base_url=api_base_url, credentials=Token(token=token))

    if entity_type == "schema":
        inner = _unwrap_snapshot(snapshot)
        content = inner.get("content")
        if not isinstance(content, list):
            msg = f"Cannot restore schema {entity_id}: snapshot has no content"
            raise ValueError(msg)
        patch = {"content": sanitize_schema_content(content)}
    else:
        # Fetch current state and compute minimal diff
        current = await client._http_client.fetch_one(resource, int_id)
        current_dict = current if isinstance(current, dict) else {}
        patch = _compute_revert_patch(snapshot, current_dict)

    if not patch:
        return {"status": "no_changes", "entity_type": entity_type, "entity_id": entity_id}

    if entity_type == "schema":
        await _revert_schema_with_retry(client, int_id, patch)
    else:
        await client._http_client.update(resource, int_id, patch)
    return {"status": "restored", "entity_type": entity_type, "entity_id": entity_id}


def _resolve_snapshot(
    snapshot_store: SnapshotStore,
    commit_store: CommitStore,
    environment: str,
    entity_type: str,
    entity_id: str,
    commit_hash: str,
) -> tuple[dict | None, str | None]:
    """Resolve a snapshot for an entity at a given commit. Returns (snapshot, error_message)."""
    # 1. Exact snapshot at this commit
    snapshot = snapshot_store.get_snapshot(environment, entity_type, entity_id, commit_hash)

    # 2. Most recent snapshot at or before the commit's timestamp
    if snapshot is None:
        target_commit = commit_store.get_commit(environment, commit_hash)
        if target_commit is None:
            return None, f"Commit {commit_hash} not found"
        snapshot = snapshot_store.get_snapshot_at(
            environment, entity_type, entity_id, target_commit.timestamp.timestamp()
        )

    # 3. Pre-change state from the earliest recorded change for this entity
    if snapshot is None:
        earliest = snapshot_store.get_earliest_version(environment, entity_type, entity_id)
        if earliest:
            earliest_commit = commit_store.get_commit(environment, earliest[0])
            if earliest_commit:
                for change in earliest_commit.changes:
                    if change.entity_type == entity_type and change.entity_id == entity_id:
                        snapshot = change.before
                        break

    if snapshot is None:
        versions = snapshot_store.list_versions(environment, entity_type, entity_id, limit=1)
        if versions:
            return None, (
                f"Snapshot data for {entity_type} {entity_id} has expired. "
                f"The version index still lists entries but the underlying data is no longer available."
            )
        return None, f"No snapshot found for {entity_type} {entity_id} at commit {commit_hash}"

    return snapshot, None


@beta_tool
def restore_entity_version(entity_type: str, entity_id: str, commit_hash: str) -> str:
    """Restore an entity to the state it was in at a given commit.

    The commit hash identifies a point in time — the entity does not need to
    have been modified in that commit. Any commit hash from show_change_history
    works as a time reference. Resolution order:
    1. Exact snapshot at that commit.
    2. Most recent snapshot at or before the commit's timestamp.
    3. Pre-change state before the entity's first tracked modification.

    Args:
        entity_type: Entity type (e.g. "schema", "queue", "hook").
        entity_id: Entity ID.
        commit_hash: Commit hash identifying the target point in time.

    Returns:
        JSON with restore status.
    """
    ctx = get_context()
    if ctx.snapshot_store is None or ctx.commit_store is None or ctx.rossum_environment is None:
        return json.dumps({"error": "Snapshot tracking not available"})

    _flush_pending_changes()

    snapshot, error = _resolve_snapshot(
        ctx.snapshot_store, ctx.commit_store, ctx.rossum_environment, entity_type, entity_id, commit_hash
    )
    if error:
        return json.dumps({"error": error})
    assert snapshot is not None  # _resolve_snapshot returns None snapshot iff error is set

    credentials = ctx.get_rossum_credentials()
    loop = ctx.mcp_event_loop
    if not credentials or not loop:
        return json.dumps({"error": "API credentials or event loop not available"})

    api_base_url, token = credentials
    try:
        coro = _restore_entity(api_base_url, token, entity_type, entity_id, snapshot)
        result = asyncio.run_coroutine_threadsafe(coro, loop).result()
        return json.dumps(result)
    except Exception as e:
        logger.exception(f"Failed to restore {entity_type}:{entity_id}")
        return json.dumps({"error": str(e), "entity_type": entity_type, "entity_id": entity_id})


def _parse_json_arg(value: str | object) -> object:
    """Parse a JSON argument, tolerating dicts passed directly or double-encoded strings."""
    if not isinstance(value, str):
        # Agent passed a dict/list object directly instead of a JSON string
        return value
    parsed = json.loads(value)
    if isinstance(parsed, str):
        # Agent double-encoded: the JSON string contained another JSON string
        try:
            return json.loads(parsed)
        except json.JSONDecodeError:
            return parsed
    return parsed


@beta_tool
def diff_objects(before: str, after: str) -> str:
    """Compute a unified diff between two JSON objects.

    Use only when the user explicitly asks to compare or diff two objects.
    Both inputs are pretty-printed with sorted keys before diffing so structural
    changes are stable and readable.

    Args:
        before: JSON string of the first object.
        after: JSON string of the second object.

    Returns:
        Unified diff text, or "No differences found." if identical.
    """
    try:
        before_obj = _parse_json_arg(before)
        after_obj = _parse_json_arg(after)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})

    diff_text = compute_json_diff(before_obj, after_obj, sort_keys=True)
    return diff_text or "No differences found."
