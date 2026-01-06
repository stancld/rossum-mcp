from __future__ import annotations

import dataclasses
import json
import logging
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rossum_api import SyncRossumAPIClient
from rossum_api.domain_logic.resources import Resource
from rossum_api.dtos import Token

from rossum_deploy.constants import (
    DIFFABLE_TYPES,
    IGNORED_FIELDS,
    OBJECT_FOLDERS,
    OBJECT_TYPE_TO_RESOURCE,
    PUSHABLE_TYPES,
    TYPE_SPECIFIC_IGNORED_FIELDS,
)
from rossum_deploy.models import (
    CompareResult,
    CopyResult,
    DeployResult,
    DiffResult,
    DiffStatus,
    FieldDiff,
    IdMapping,
    LocalObject,
    ObjectCompare,
    ObjectDiff,
    ObjectMeta,
    ObjectType,
    PullResult,
    PushResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from rossum_api.models import Connector, EmailTemplate, Engine, Hook, Queue, Rule
    from rossum_api.models import Workspace as RossumWorkspace

logger = logging.getLogger(__name__)


class WorkspaceConfig:
    """Configuration for a local workspace."""

    def __init__(self, api_base: str, org_id: int | None = None) -> None:
        self.api_base = api_base
        self.org_id = org_id

    def to_dict(self) -> dict[str, Any]:
        return {"api_base": self.api_base, "org_id": self.org_id}

    def __repr__(self) -> str:
        return f"WorkspaceConfig(api_base={self.api_base!r}, org_id={self.org_id!r})"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkspaceConfig:
        return cls(api_base=data["api_base"], org_id=data.get("org_id"))


class Workspace:
    """Local workspace for Rossum configuration management.

    Provides pull/diff/push operations for safe configuration deployment.

    Example:
        >>> ws = Workspace("./my-project", api_base="https://api.elis.rossum.ai/v1", token="...")
        >>> ws.pull(org_id=123456)
        >>> print(ws.diff().summary())
        >>> ws.push()
    """

    def __init__(self, path: str | Path, api_base: str, token: str) -> None:
        self.path = Path(path)

        api_base = api_base.rstrip("/")
        self._api_base = api_base
        self._token = token
        self._config = WorkspaceConfig(api_base=api_base)
        self._client = SyncRossumAPIClient(api_base, Token(token))

    @property
    def client(self) -> SyncRossumAPIClient:
        return self._client

    def _object_folder(self, obj_type: ObjectType) -> Path:
        folder = self.path / OBJECT_FOLDERS[obj_type]
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _object_path(self, obj_type: ObjectType, obj_id: int, name: str) -> Path:
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in name)
        return self._object_folder(obj_type) / f"{safe_name}_{obj_id}.json"

    def _save_object(
        self,
        obj_type: ObjectType,
        obj_id: int,
        name: str,
        data: dict[str, Any],
        remote_modified_at: datetime | None = None,
    ) -> Path:
        local_obj = LocalObject(
            _meta=ObjectMeta(
                pulled_at=datetime.now(UTC),
                remote_modified_at=remote_modified_at,
                object_type=obj_type,
                object_id=obj_id,
            ),
            data=data,
        )
        path = self._object_path(obj_type, obj_id, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(local_obj.model_dump(by_alias=True, mode="json"), f, indent=2)
        return path

    def _load_object(self, path: Path) -> LocalObject:
        with open(path, encoding="utf-8") as f:
            result: LocalObject = LocalObject.model_validate(json.load(f))
            return result

    def _list_local_objects(self, obj_type: ObjectType) -> list[Path]:
        folder = self.path / OBJECT_FOLDERS[obj_type]
        if not folder.exists():
            return []
        return list(folder.glob("*.json"))

    def _get_workspace_ids(self) -> set[int]:
        """Get IDs of all local workspaces."""
        ws_paths = self._list_local_objects(ObjectType.WORKSPACE)
        return {self._load_object(p).meta.object_id for p in ws_paths}

    def _get_queue_urls(self) -> set[str]:
        """Get URLs of all local queues."""
        queue_paths = self._list_local_objects(ObjectType.QUEUE)
        return {data["url"] for qp in queue_paths if "url" in (data := self._load_object(qp).data)}

    def _get_schema_ids_from_queues(self) -> set[int]:
        """Get schema IDs referenced by local queues."""
        queue_paths = self._list_local_objects(ObjectType.QUEUE)
        return {
            int(data["schema"].split("/")[-1])
            for qp in queue_paths
            if (data := self._load_object(qp).data).get("schema")
        }

    def _get_schema_urls_from_queues(self) -> set[str]:
        """Get schema URLs referenced by local queues."""
        queue_paths = self._list_local_objects(ObjectType.QUEUE)
        return {data["schema"] for qp in queue_paths if (data := self._load_object(qp).data).get("schema")}

    def pull(self, org_id: int) -> PullResult:
        """Pull objects from Rossum to local workspace.

        Args:
            org_id: Organization ID to pull from
        """
        result = PullResult()

        logger.info("Pulling from API: %s", self._api_base)

        self._config.org_id = org_id

        self._pull_workspaces(self.client, org_id, result)
        self._pull_queues(self.client, result)
        self._pull_schemas(self.client, result)
        self._pull_inboxes(self.client, result)
        self._pull_hooks(self.client, result)
        self._pull_connectors(self.client, result)
        self._pull_engines(self.client, result)
        self._pull_email_templates(self.client, result)
        self._pull_rules(self.client, result)

        return result

    def pull_workspace(self, workspace_id: int) -> PullResult:
        """Pull a specific workspace and its related objects from Rossum.

        Args:
            workspace_id: Workspace ID to pull
        """
        result = PullResult()

        logger.info("Pulling workspace %d from API: %s", workspace_id, self._api_base)

        ws = self.client.retrieve_workspace(workspace_id)
        org_id = int(ws.organization.split("/")[-1]) if ws.organization else None
        self._config.org_id = org_id
        data = dataclasses.asdict(ws)
        modified_at = getattr(ws, "modified_at", None)
        self._save_object(ObjectType.WORKSPACE, ws.id, ws.name, data, modified_at)
        result.pulled.append((ObjectType.WORKSPACE, ws.id, ws.name))

        self._pull_queues(self.client, result)
        self._pull_schemas(self.client, result)
        self._pull_inboxes(self.client, result)
        self._pull_hooks(self.client, result)
        self._pull_connectors(self.client, result)
        self._pull_engines(self.client, result)
        self._pull_email_templates(self.client, result)
        self._pull_rules(self.client, result)

        return result

    def _normalize_id_mapping(self, id_mapping: IdMapping, local_ws_id: int, target_ws_id: int) -> IdMapping:
        """Ensure id_mapping is in the correct direction (local_ws_id -> target_ws_id).

        If local_ws_id is a key in the mapping, it's already correct direction.
        If local_ws_id is a value in the mapping (i.e., we're on the target side),
        we need to reverse the mapping.
        """
        # Check if local_ws_id is a source (key) in the mapping - already correct
        if id_mapping.get(ObjectType.WORKSPACE, local_ws_id) is not None:
            return id_mapping

        # Check if local_ws_id is a target (value) in the mapping - need to reverse
        ws_mappings = id_mapping.get_all(ObjectType.WORKSPACE)
        if local_ws_id in ws_mappings.values():
            return id_mapping.reverse()

        return id_mapping

    def compare_workspaces(self, target_workspace: Workspace, id_mapping: IdMapping | None = None) -> CompareResult:
        """Compare this workspace (source) with a target workspace.

        Two use cases:
        1. Compare prod vs sandbox: Pass id_mapping from copy_workspace to map IDs
        2. Compare before vs after: Pass id_mapping=None to compare same workspace
           at different times (objects matched by same ID)

        Args:
            target_workspace: The target Workspace instance to compare against
            id_mapping: ID mapping from copy_workspace. If None, objects are
                matched by their original IDs (for comparing same workspace
                before and after changes).
        """
        source_ws_paths = self._list_local_objects(ObjectType.WORKSPACE)
        target_ws_paths = target_workspace._list_local_objects(ObjectType.WORKSPACE)

        if not source_ws_paths or not target_ws_paths:
            raise ValueError("Both source and target must have workspace objects pulled")

        source_ws_id = self._load_object(source_ws_paths[0]).meta.object_id
        target_ws_id = target_workspace._load_object(target_ws_paths[0]).meta.object_id

        result = CompareResult(source_workspace_id=source_ws_id, target_workspace_id=target_ws_id)

        effective_mapping = self._normalize_id_mapping(id_mapping, source_ws_id, target_ws_id) if id_mapping else None

        for obj_type in DIFFABLE_TYPES:
            self._compare_object_type(target_workspace, obj_type, effective_mapping, result)

        return result

    def _compare_object_type(
        self, target_workspace: Workspace, obj_type: ObjectType, id_mapping: IdMapping | None, result: CompareResult
    ) -> None:
        """Compare all objects of a given type between source and target."""
        source_objects: dict[int, LocalObject] = {}
        for path in self._list_local_objects(obj_type):
            obj = self._load_object(path)
            source_objects[obj.meta.object_id] = obj

        target_objects: dict[int, LocalObject] = {}
        for path in target_workspace._list_local_objects(obj_type):
            obj = target_workspace._load_object(path)
            target_objects[obj.meta.object_id] = obj

        matched_target_ids: set[int] = set()

        for source_id, source_obj in source_objects.items():
            # If no id_mapping, assume same IDs (comparing same workspace at different times)
            target_id = id_mapping.get(obj_type, source_id) if id_mapping else source_id
            name = source_obj.data.get("name", f"Object {source_id}")

            if target_id and target_id in target_objects:
                matched_target_ids.add(target_id)
                target_obj = target_objects[target_id]
                field_diffs = self._compare_object_data(source_obj.data, target_obj.data, id_mapping, obj_type)

                obj_compare = ObjectCompare(
                    object_type=obj_type,
                    source_id=source_id,
                    target_id=target_id,
                    name=name,
                    is_identical=len(field_diffs) == 0,
                    field_diffs=field_diffs,
                )
                result.objects.append(obj_compare)
                if obj_compare.is_identical:
                    result.total_identical += 1
                else:
                    result.total_different += 1
            else:
                result.source_only.append((obj_type, source_id, name))

        for target_id, target_obj in target_objects.items():
            if target_id not in matched_target_ids:
                name = target_obj.data.get("name", f"Object {target_id}")
                result.target_only.append((obj_type, target_id, name))

    def _compare_object_data(
        self,
        source_data: dict[str, Any],
        target_data: dict[str, Any],
        id_mapping: IdMapping | None,
        obj_type: ObjectType | None = None,
    ) -> list[FieldDiff]:
        """Compare two object data dicts, returning field-level diffs."""
        diffs: list[FieldDiff] = []

        all_keys = set(source_data.keys()) | set(target_data.keys())
        type_ignored = TYPE_SPECIFIC_IGNORED_FIELDS.get(obj_type, set()) if obj_type else set()
        skip_keys = IGNORED_FIELDS | type_ignored | {"_meta", "id"}

        for key in all_keys:
            if key in skip_keys or key.startswith("_"):
                continue

            source_val = source_data.get(key)
            target_val = target_data.get(key)

            normalized_source = self._normalize_value(source_val, id_mapping, key)
            normalized_target = self._normalize_value(target_val, None, key)

            if normalized_source != normalized_target:
                diffs.append(FieldDiff(field=key, source_value=source_val, target_value=target_val))

        return diffs

    def _normalize_value(self, value: Any, id_mapping: IdMapping | None, field_name: str | None = None) -> Any:
        """Normalize a value for comparison, remapping IDs if needed."""
        if value is None:
            return value

        if isinstance(value, str):
            # Normalize message field: strip trailing whitespace (API may add/remove \n)
            if field_name == "message":
                value = value.rstrip()

            if id_mapping:
                for obj_type in ObjectType:
                    mappings = id_mapping.get_all(obj_type)
                    for source_id, target_id in mappings.items():
                        value = value.replace(f"/{source_id}", f"/{target_id}")
            return value

        if isinstance(value, list):
            return [self._normalize_value(v, id_mapping) for v in value]

        if isinstance(value, dict):
            return {k: self._normalize_value(v, id_mapping, k) for k, v in value.items()}

        return value

    def _pull_workspaces(self, client: SyncRossumAPIClient, org_id: int, result: PullResult) -> PullResult:
        for ws in client.list_workspaces():
            if ws.organization and str(org_id) in ws.organization:
                data = dataclasses.asdict(ws)
                modified_at = getattr(ws, "modified_at", None)
                self._save_object(ObjectType.WORKSPACE, ws.id, ws.name, data, modified_at)
                result.pulled.append((ObjectType.WORKSPACE, ws.id, ws.name))
        return result

    def _pull_queues(self, client: SyncRossumAPIClient, result: PullResult) -> PullResult:
        ws_ids = self._get_workspace_ids()
        for queue in client.list_queues():
            if queue.workspace:
                ws_id = int(queue.workspace.split("/")[-1])
                if ws_id in ws_ids:
                    data = dataclasses.asdict(queue)
                    self._save_object(
                        ObjectType.QUEUE,
                        queue.id,
                        queue.name,
                        data,
                        None,
                    )
                    result.pulled.append((ObjectType.QUEUE, queue.id, queue.name))
        return result

    def _pull_inboxes(self, client: SyncRossumAPIClient, result: PullResult) -> PullResult:
        queue_urls = self._get_queue_urls()
        for inbox in client.request_paginated("inboxes"):
            inbox_queues = set(inbox.get("queues", []))
            if inbox_queues & queue_urls:
                name = inbox.get("name", f"Inbox {inbox['id']}")
                modified_at = None
                if inbox.get("modified_at"):
                    modified_at = datetime.fromisoformat(inbox["modified_at"].replace("Z", "+00:00"))
                self._save_object(ObjectType.INBOX, inbox["id"], name, inbox, modified_at)
                result.pulled.append((ObjectType.INBOX, inbox["id"], name))
        return result

    def _pull_schemas(self, client: SyncRossumAPIClient, result: PullResult) -> PullResult:
        schema_ids = self._get_schema_ids_from_queues()
        for schema_id in schema_ids:
            schema = client.retrieve_schema(schema_id)
            data = dataclasses.asdict(schema)
            modified_at = getattr(schema, "modified_at", None)
            self._save_object(ObjectType.SCHEMA, schema.id, schema.name, data, modified_at)
            result.pulled.append((ObjectType.SCHEMA, schema.id, schema.name))
        return result

    def _pull_queue_linked_objects[T](
        self,
        items: list[T],
        obj_type: ObjectType,
        queue_urls: set[str],
        result: PullResult,
        get_queues: Callable[[T], set[str]],
    ) -> PullResult:
        """Pull objects linked to queues via a queues field."""
        for item in items:
            if get_queues(item) & queue_urls:
                data = dataclasses.asdict(item)  # type: ignore[call-overload]
                modified_at = getattr(item, "modified_at", None)
                self._save_object(obj_type, item.id, item.name, data, modified_at)  # type: ignore[attr-defined]
                result.pulled.append((obj_type, item.id, item.name))  # type: ignore[attr-defined]
        return result

    def _pull_hooks(self, client: SyncRossumAPIClient, result: PullResult) -> PullResult:
        return self._pull_queue_linked_objects(
            list(client.list_hooks()), ObjectType.HOOK, self._get_queue_urls(), result, lambda h: set(h.queues or [])
        )

    def _pull_connectors(self, client: SyncRossumAPIClient, result: PullResult) -> PullResult:
        return self._pull_queue_linked_objects(
            list(client.list_connectors()),
            ObjectType.CONNECTOR,
            self._get_queue_urls(),
            result,
            lambda c: set(c.queues or []),
        )

    def _collect_engine_urls_from_queues(self, client: SyncRossumAPIClient, queue_urls: set[str]) -> set[str]:
        """Collect engine URLs referenced by queues in the given queue_urls set."""
        engine_urls: set[str] = set()
        for queue in client.list_queues():
            if queue.url not in queue_urls:
                continue
            if queue.dedicated_engine:
                engine_url = (
                    queue.dedicated_engine
                    if isinstance(queue.dedicated_engine, str)
                    else queue.dedicated_engine.get("url")
                )
                if engine_url:
                    engine_urls.add(engine_url)
            if queue.generic_engine:
                engine_url = (
                    queue.generic_engine if isinstance(queue.generic_engine, str) else queue.generic_engine.get("url")
                )
                if engine_url:
                    engine_urls.add(engine_url)
        return engine_urls

    def _pull_engines(self, client: SyncRossumAPIClient, result: PullResult) -> PullResult:
        queue_urls = self._get_queue_urls()
        engine_urls_to_pull = self._collect_engine_urls_from_queues(client, queue_urls)

        for engine in client.list_engines():
            if engine.url not in engine_urls_to_pull:
                continue
            data = dataclasses.asdict(engine)
            modified_at = getattr(engine, "modified_at", None)
            self._save_object(ObjectType.ENGINE, engine.id, engine.name, data, modified_at)
            result.pulled.append((ObjectType.ENGINE, engine.id, engine.name))
        return result

    def _pull_email_templates(self, client: SyncRossumAPIClient, result: PullResult) -> PullResult:
        queue_urls = self._get_queue_urls()
        for template in client.list_email_templates():
            # EmailTemplate has singular 'queue' field, not 'queues'
            if template.queue in queue_urls:
                data = dataclasses.asdict(template)
                # Normalize message field to avoid trailing whitespace diffs
                if data.get("message"):
                    data["message"] = data["message"].rstrip()
                modified_at = getattr(template, "modified_at", None)
                self._save_object(ObjectType.EMAIL_TEMPLATE, template.id, template.name, data, modified_at)
                result.pulled.append((ObjectType.EMAIL_TEMPLATE, template.id, template.name))
        return result

    def _pull_rules(self, client: SyncRossumAPIClient, result: PullResult) -> PullResult:
        """Pull rules linked to schemas of local queues."""
        schema_urls = self._get_schema_urls_from_queues()
        for rule in client.list_rules():
            if rule.schema in schema_urls:
                data = dataclasses.asdict(rule)
                modified_at = getattr(rule, "modified_at", None)
                self._save_object(ObjectType.RULE, rule.id, rule.name, data, modified_at)
                result.pulled.append((ObjectType.RULE, rule.id, rule.name))
        return result

    def diff(self) -> DiffResult:
        """Compare local workspace with remote Rossum.

        Uses Git to detect local modifications. If a file has uncommitted changes
        (staged or unstaged) compared to HEAD, it's considered locally modified.
        Remote modifications are detected by comparing timestamps.

        Status determination:
        - UNCHANGED: No differences between local and remote
        - LOCAL_MODIFIED: File has uncommitted Git changes, remote unchanged
        - REMOTE_MODIFIED: Remote changed since last pull, no local Git changes
        - CONFLICT: Both local Git changes and remote changes exist
        - LOCAL_ONLY: Object exists locally but not on remote
        """
        result = DiffResult()

        for obj_type in DIFFABLE_TYPES:
            for file_path in self._list_local_objects(obj_type):
                local_obj = self._load_object(file_path)
                obj_id = local_obj.meta.object_id
                name = local_obj.data.get("name", f"Object {obj_id}")

                try:
                    remote_data, remote_modified = self._fetch_remote_object(self.client, obj_type, obj_id)
                except Exception:
                    result.objects.append(
                        ObjectDiff(object_type=obj_type, object_id=obj_id, name=name, status=DiffStatus.LOCAL_ONLY)
                    )
                    continue

                stored_remote_modified = local_obj.meta.remote_modified_at
                changed_fields = self._compare_objects(local_obj.data, remote_data, obj_type)

                field_diffs = [
                    FieldDiff(
                        field=field,
                        source_value=remote_data.get(field),
                        target_value=local_obj.data.get(field),
                    )
                    for field in changed_fields
                ]

                is_local_modified = self._is_git_modified(file_path)
                is_remote_modified = stored_remote_modified != remote_modified

                if not changed_fields:
                    status = DiffStatus.UNCHANGED
                    result.total_unchanged += 1
                elif is_local_modified and is_remote_modified:
                    status = DiffStatus.CONFLICT
                    result.total_conflicts += 1
                elif is_local_modified:
                    status = DiffStatus.LOCAL_MODIFIED
                    result.total_local_modified += 1
                elif is_remote_modified:
                    status = DiffStatus.REMOTE_MODIFIED
                    result.total_remote_modified += 1
                else:
                    status = DiffStatus.LOCAL_MODIFIED
                    result.total_local_modified += 1

                result.objects.append(
                    ObjectDiff(
                        object_type=obj_type,
                        object_id=obj_id,
                        name=name,
                        status=status,
                        local_modified_at=stored_remote_modified,
                        remote_modified_at=remote_modified,
                        changed_fields=changed_fields,
                        field_diffs=field_diffs,
                    )
                )

        return result

    def _retrieve_remote_object(self, client: SyncRossumAPIClient, obj_type: ObjectType, obj_id: int) -> Any:
        """Retrieve raw remote object by type."""
        retrievers = {
            ObjectType.WORKSPACE: client.retrieve_workspace,
            ObjectType.QUEUE: client.retrieve_queue,
            ObjectType.SCHEMA: client.retrieve_schema,
            ObjectType.HOOK: client.retrieve_hook,
            ObjectType.CONNECTOR: client.retrieve_connector,
            ObjectType.ENGINE: client.retrieve_engine,
            ObjectType.EMAIL_TEMPLATE: client.retrieve_email_template,
            ObjectType.RULE: client.retrieve_rule,
        }
        if obj_type in retrievers:
            return retrievers[obj_type](obj_id)
        if obj_type == ObjectType.INBOX:
            return None
        raise ValueError(f"Unsupported object type for diff: {obj_type}")

    def _fetch_remote_object(
        self, client: SyncRossumAPIClient, obj_type: ObjectType, obj_id: int
    ) -> tuple[dict[str, Any], datetime | None]:
        """Fetch remote object data and modified_at timestamp."""
        if obj_type == ObjectType.INBOX:
            data = client.request_json("GET", f"inboxes/{obj_id}")
            modified_at = None
            if data.get("modified_at"):
                modified_at = datetime.fromisoformat(data["modified_at"].replace("Z", "+00:00"))
            return data, modified_at

        remote = self._retrieve_remote_object(client, obj_type, obj_id)
        remote_data = dataclasses.asdict(remote)
        # Normalize email template message field to avoid trailing whitespace diffs
        if obj_type == ObjectType.EMAIL_TEMPLATE and remote_data.get("message"):
            remote_data["message"] = remote_data["message"].rstrip()
        remote_modified = getattr(remote, "modified_at", None)
        if isinstance(remote_modified, str):
            remote_modified = datetime.fromisoformat(remote_modified.replace("Z", "+00:00"))
        return remote_data, remote_modified

    def _compare_objects(
        self, local: dict[str, Any], remote: dict[str, Any], obj_type: ObjectType | None = None
    ) -> list[str]:
        changed = []
        all_keys = set(local.keys()) | set(remote.keys())
        type_ignored = TYPE_SPECIFIC_IGNORED_FIELDS.get(obj_type, set()) if obj_type else set()
        for key in all_keys:
            if key in IGNORED_FIELDS or key in type_ignored or key.startswith("_"):
                continue
            if local.get(key) != remote.get(key):
                changed.append(key)
        return changed

    def _is_git_modified(self, file_path: Path) -> bool:
        """Check if a file has uncommitted modifications using Git.

        Only returns True for actual modifications to tracked files.
        Untracked files (??) and newly staged files (A) are not considered
        "modified" since they represent a fresh pull, not user edits.

        Git status codes:
        - "M " = staged modified
        - " M" = unstaged modified
        - "MM" = both staged and unstaged modifications
        - "A " = staged new file (excluded)
        - "??" = untracked file (excluded)
        """
        try:
            git_executable = shutil.which("git")
            if not git_executable:
                return False
            result = subprocess.run(
                [git_executable, "status", "-s", "--", str(file_path.resolve())],
                cwd=file_path.parent,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return False
            status = result.stdout.strip()
            if not status:
                return False
            status_code = status[:2]
            return "M" in status_code
        except FileNotFoundError:
            return False

    def push(self, dry_run: bool = False, force: bool = False) -> PushResult:
        """Push local changes to Rossum.

        Args:
            dry_run: If True, only show what would be pushed
            force: If True, push even if there are conflicts
        """
        diff_result = self.diff()
        result = PushResult()

        for obj_diff in diff_result.objects:
            if obj_diff.status == DiffStatus.UNCHANGED:
                continue

            if obj_diff.object_type not in PUSHABLE_TYPES:
                result.skipped.append(
                    (
                        obj_diff.object_type,
                        obj_diff.object_id,
                        obj_diff.name,
                        f"push not supported for {obj_diff.object_type.value}",
                    )
                )
                continue

            if obj_diff.status == DiffStatus.CONFLICT and not force:
                result.skipped.append(
                    (obj_diff.object_type, obj_diff.object_id, obj_diff.name, "conflict - use force=True to override")
                )
                continue

            if obj_diff.status == DiffStatus.REMOTE_MODIFIED and not force:
                result.skipped.append(
                    (obj_diff.object_type, obj_diff.object_id, obj_diff.name, "remote modified - pull first")
                )
                continue

            # Push if locally modified, or if force=True for conflicts/remote modified
            pushable_statuses = {DiffStatus.LOCAL_MODIFIED}
            if force:
                pushable_statuses.update({DiffStatus.CONFLICT, DiffStatus.REMOTE_MODIFIED})

            if obj_diff.status not in pushable_statuses:
                continue

            if dry_run:
                result.pushed.append((obj_diff.object_type, obj_diff.object_id, obj_diff.name))
                continue

            try:
                local_path = self._find_object_path(obj_diff.object_type, obj_diff.object_id)
                if not local_path:
                    continue

                local_obj = self._load_object(local_path)
                type_ignored = TYPE_SPECIFIC_IGNORED_FIELDS.get(obj_diff.object_type, set())
                skip_keys = IGNORED_FIELDS | type_ignored
                data = {k: v for k, v in local_obj.data.items() if k not in skip_keys and not k.startswith("_")}

                self._push_object(self.client, obj_diff.object_type, obj_diff.object_id, data)

                result.pushed.append((obj_diff.object_type, obj_diff.object_id, obj_diff.name))
            except Exception as e:
                result.failed.append((obj_diff.object_type, obj_diff.object_id, obj_diff.name, str(e)))

        return result

    def _push_object(
        self, client: SyncRossumAPIClient, obj_type: ObjectType, obj_id: int, data: dict[str, Any]
    ) -> None:
        if obj_type not in OBJECT_TYPE_TO_RESOURCE:
            raise ValueError(f"Unsupported object type for push: {obj_type}")

        # Clean schema content before pushing to remove invalid null fields
        if obj_type == ObjectType.SCHEMA and "content" in data:
            data = data.copy()
            data["content"] = self._clean_schema_content(data["content"])

        resource = OBJECT_TYPE_TO_RESOURCE[obj_type]
        client.internal_client.update(resource, obj_id, data)

    def _clean_schema_content(self, content: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Clean schema content by removing null values that API rejects.

        The Rossum API rejects null values for many schema fields. This method
        recursively removes fields with null values and fields that are only
        valid for multivalue-tuple children when not in that context.
        """
        return [self._clean_schema_node(node, parent_is_multivalue_tuple=False) for node in content]

    def _clean_schema_node(self, node: dict[str, Any], parent_is_multivalue_tuple: bool = False) -> dict[str, Any]:
        """Recursively clean a schema node.

        The multivalue-tuple context works like this:
        - A multivalue can have a tuple as its direct child
        - Only the children OF that tuple (grandchildren of the multivalue) can have
          stretch, can_collapse, width, width_chars attributes
        - We pass parent_is_multivalue_tuple=True when the parent is a tuple
          that is the direct child of a multivalue
        """
        cleaned: dict[str, Any] = {}
        multivalue_tuple_only_fields = {"width", "stretch", "can_collapse", "width_chars"}
        is_multivalue = node.get("category") == "multivalue"
        is_tuple = node.get("category") == "tuple"

        for key, value in node.items():
            if value is None:
                continue
            if key in multivalue_tuple_only_fields and not parent_is_multivalue_tuple:
                continue

            if key == "children":
                cleaned[key] = self._clean_children(value, is_multivalue, is_tuple, parent_is_multivalue_tuple)
            else:
                cleaned[key] = value

        return cleaned

    def _clean_children(
        self, value: Any, is_multivalue: bool, is_tuple: bool, parent_is_multivalue_tuple: bool
    ) -> Any:
        """Clean children field which can be a dict, list, or other value."""
        if isinstance(value, dict):
            return self._clean_single_child(value, is_multivalue)
        if isinstance(value, list):
            return self._clean_child_list(value, is_multivalue, is_tuple, parent_is_multivalue_tuple)
        return value

    def _clean_single_child(self, child: dict[str, Any], is_multivalue: bool) -> dict[str, Any]:
        """Clean a single child dict (e.g., tuple inside multivalue)."""
        child_is_tuple = child.get("category") == "tuple"
        next_parent_is_mv_tuple = is_multivalue and child_is_tuple
        return self._clean_schema_node(child, next_parent_is_mv_tuple)

    def _clean_child_list(
        self, children: list[Any], is_multivalue: bool, is_tuple: bool, parent_is_multivalue_tuple: bool
    ) -> list[Any]:
        """Clean a list of children."""
        cleaned_children = []
        for child in children:
            if isinstance(child, dict):
                next_context = self._determine_child_context(
                    child, is_multivalue, is_tuple, parent_is_multivalue_tuple
                )
                cleaned_children.append(self._clean_schema_node(child, next_context))
            else:
                cleaned_children.append(child)
        return cleaned_children

    def _determine_child_context(
        self, child: dict[str, Any], is_multivalue: bool, is_tuple: bool, parent_is_multivalue_tuple: bool
    ) -> bool:
        """Determine if child should have multivalue-tuple context."""
        if is_tuple and parent_is_multivalue_tuple:
            return True
        child_is_tuple = child.get("category") == "tuple"
        if is_multivalue and child_is_tuple:
            return True
        return False

    def _find_object_path(self, obj_type: ObjectType, obj_id: int) -> Path | None:
        for path in self._list_local_objects(obj_type):
            if f"_{obj_id}.json" in path.name:
                return path
        return None

    def copy_workspace(
        self,
        source_workspace_id: int,
        target_org_id: int,
        target_api_base: str | None = None,
        target_token: str | None = None,
    ) -> CopyResult:
        """Copy a single workspace and all its objects to a target org.

        Copies the workspace, all queues within it, schemas, engines, hooks,
        connectors, inboxes, email templates, and rules associated with those queues.

        Args:
            source_workspace_id: Source workspace ID to copy
            target_org_id: Target organization ID to copy to
            target_api_base: API base for target org (if different from source)
            target_token: API token for target org (if different from source)
        """
        source_client = self.client
        target_client = self._get_target_client(target_api_base, target_token)

        result = CopyResult()

        source_ws = source_client.retrieve_workspace(source_workspace_id)
        source_org_id = int(source_ws.organization.split("/")[-1]) if source_ws.organization else 0

        id_mapping = IdMapping(source_org_id=source_org_id, target_org_id=target_org_id)

        self._copy_workspaces([source_ws], target_client, target_org_id, id_mapping, result)

        source_queues = self._get_workspace_queues(source_client, source_workspace_id)
        self._copy_queues(source_queues, source_client, target_client, id_mapping, result)

        source_queue_urls = {f"{source_client.internal_client.base_url}/queues/{q.id}" for q, _ in source_queues}
        source_schema_urls = {q.schema for q, _ in source_queues if q.schema}

        self._copy_engines(source_client, target_client, source_queue_urls, id_mapping, result)
        self._copy_hooks(source_client, target_client, source_queue_urls, id_mapping, result)
        self._copy_connectors(source_client, target_client, source_queue_urls, id_mapping, result)
        self._copy_inboxes(source_client, target_client, source_queue_urls, id_mapping, result)
        self._copy_email_templates(source_client, target_client, source_queue_urls, id_mapping, result)
        self._copy_rules(source_client, target_client, source_schema_urls, id_mapping, result)

        result.id_mapping = id_mapping
        self._save_id_mapping(id_mapping)
        return result

    def _get_workspace_queues(self, source_client: SyncRossumAPIClient, workspace_id: int) -> list[tuple[Queue, int]]:
        return [
            (queue, workspace_id)
            for queue in source_client.list_queues()
            if queue.workspace and int(queue.workspace.split("/")[-1]) == workspace_id
        ]

    def _copy_engines(
        self,
        source_client: SyncRossumAPIClient,
        target_client: SyncRossumAPIClient,
        source_queue_urls: set[str],
        id_mapping: IdMapping,
        result: CopyResult,
    ) -> None:
        engine_urls_to_copy = self._collect_engine_urls_from_queues(source_client, source_queue_urls)

        for engine in source_client.list_engines():
            if engine.url not in engine_urls_to_copy:
                continue

            self._copy_single_engine(engine, target_client, id_mapping, result)

    def _copy_single_engine(
        self, engine: Engine, target_client: SyncRossumAPIClient, id_mapping: IdMapping, result: CopyResult
    ) -> None:
        try:
            target_queue_urls = []
            for q_url in engine.training_queues or []:
                source_q_id = int(q_url.split("/")[-1])
                target_q_id = id_mapping.get(ObjectType.QUEUE, source_q_id)
                if target_q_id:
                    target_queue_urls.append(f"{target_client.internal_client.base_url}/queues/{target_q_id}")

            target_org_url = f"{target_client.internal_client.base_url}/organizations/{id_mapping.target_org_id}"
            engine_data = {
                "name": engine.name,
                "type": engine.type,
                "organization": target_org_url,
                "training_queues": target_queue_urls,
            }
            new_engine_response = target_client.internal_client.create(Resource.Engine, engine_data)
            new_engine: Engine = target_client._deserializer(Resource.Engine, new_engine_response)
            id_mapping.add(ObjectType.ENGINE, engine.id, new_engine.id)
            result.created.append((ObjectType.ENGINE, engine.id, new_engine.id, engine.name))
        except Exception as e:
            result.failed.append((ObjectType.ENGINE, engine.id, engine.name, str(e)))

    def _copy_connectors(
        self,
        source_client: SyncRossumAPIClient,
        target_client: SyncRossumAPIClient,
        source_queue_urls: set[str],
        id_mapping: IdMapping,
        result: CopyResult,
    ) -> None:
        try:
            connectors = list(source_client.list_connectors())
        except Exception as e:
            logger.warning(f"Failed to list connectors (SDK deserialization issue): {e}")
            return

        for connector in connectors:
            connector_queues = set(connector.queues or [])
            if not (connector_queues & source_queue_urls):
                continue

            self._copy_single_connector(connector, target_client, id_mapping, result)

    def _copy_single_connector(
        self, connector: Connector, target_client: SyncRossumAPIClient, id_mapping: IdMapping, result: CopyResult
    ) -> None:
        try:
            target_queue_urls = []
            for q_url in connector.queues or []:
                source_q_id = int(q_url.split("/")[-1])
                target_q_id = id_mapping.get(ObjectType.QUEUE, source_q_id)
                if target_q_id:
                    target_queue_urls.append(f"{target_client.internal_client.base_url}/queues/{target_q_id}")

            if not target_queue_urls:
                result.skipped.append((ObjectType.CONNECTOR, connector.id, connector.name, "no target queues"))
                return

            new_connector = target_client.create_new_connector(
                {
                    "name": connector.name,
                    "queues": target_queue_urls,
                    "service_url": connector.service_url,
                    "authorization_token": connector.authorization_token or "",
                    "params": connector.params or "",
                    "asynchronous": connector.asynchronous if connector.asynchronous is not None else False,
                }
            )
            id_mapping.add(ObjectType.CONNECTOR, connector.id, new_connector.id)
            result.created.append((ObjectType.CONNECTOR, connector.id, new_connector.id, connector.name))
        except Exception as e:
            result.failed.append((ObjectType.CONNECTOR, connector.id, connector.name, str(e)))

    def _copy_inboxes(
        self,
        source_client: SyncRossumAPIClient,
        target_client: SyncRossumAPIClient,
        source_queue_urls: set[str],
        id_mapping: IdMapping,
        result: CopyResult,
    ) -> None:
        for inbox in source_client.request_paginated("inboxes"):
            inbox_queues = set(inbox.get("queues", []))
            if not (inbox_queues & source_queue_urls):
                continue

            self._copy_single_inbox(inbox, target_client, id_mapping, result)

    def _copy_single_inbox(
        self, inbox: dict[str, Any], target_client: SyncRossumAPIClient, id_mapping: IdMapping, result: CopyResult
    ) -> None:
        try:
            target_queue_urls = []
            for q_url in inbox.get("queues", []):
                source_q_id = int(q_url.split("/")[-1])
                target_q_id = id_mapping.get(ObjectType.QUEUE, source_q_id)
                if target_q_id:
                    target_queue_urls.append(f"{target_client.internal_client.base_url}/queues/{target_q_id}")

            if not target_queue_urls:
                inbox_name = inbox.get("name", f"Inbox {inbox['id']}")
                result.skipped.append((ObjectType.INBOX, inbox["id"], inbox_name, "no target queues"))
                return

            new_inbox = target_client.create_new_inbox(
                {
                    "name": inbox.get("name", ""),
                    "queues": target_queue_urls,
                    "email_prefix": inbox.get("email_prefix"),
                    "bounce_email_to": inbox.get("bounce_email_to"),
                    "bounce_unprocessable_attachments": inbox.get("bounce_unprocessable_attachments", False),
                    "bounce_deleted_annotations": inbox.get("bounce_deleted_annotations", False),
                    "bounce_postponed_annotations": inbox.get("bounce_postponed_annotations", False),
                    "filters": inbox.get("filters"),
                }
            )
            inbox_name = inbox.get("name", f"Inbox {inbox['id']}")
            id_mapping.add(ObjectType.INBOX, inbox["id"], new_inbox.id)
            result.created.append((ObjectType.INBOX, inbox["id"], new_inbox.id, inbox_name))
        except Exception as e:
            inbox_name = inbox.get("name", f"Inbox {inbox['id']}")
            result.failed.append((ObjectType.INBOX, inbox["id"], inbox_name, str(e)))

    def _copy_email_templates(
        self,
        source_client: SyncRossumAPIClient,
        target_client: SyncRossumAPIClient,
        source_queue_urls: set[str],
        id_mapping: IdMapping,
        result: CopyResult,
    ) -> None:
        for template in source_client.list_email_templates():
            if not template.queue or template.queue not in source_queue_urls:
                continue

            self._copy_single_email_template(template, target_client, id_mapping, result)

    def _copy_single_email_template(
        self, template: EmailTemplate, target_client: SyncRossumAPIClient, id_mapping: IdMapping, result: CopyResult
    ) -> None:
        try:
            # These types are auto-created by API and can't be duplicated
            unique_types = {"rejection_default", "email_with_no_processable_attachments"}
            if template.type in unique_types:
                result.skipped.append(
                    (ObjectType.EMAIL_TEMPLATE, template.id, template.name, f"auto-created type: {template.type}")
                )
                return

            if not template.queue:
                result.skipped.append((ObjectType.EMAIL_TEMPLATE, template.id, template.name, "no source queue"))
                return

            source_q_id = int(template.queue.split("/")[-1])
            target_q_id = id_mapping.get(ObjectType.QUEUE, source_q_id)
            if not target_q_id:
                result.skipped.append((ObjectType.EMAIL_TEMPLATE, template.id, template.name, "no target queue"))
                return

            target_queue_url = f"{target_client.internal_client.base_url}/queues/{target_q_id}"

            new_template = target_client.create_new_email_template(
                {
                    "name": template.name,
                    "queue": target_queue_url,
                    "type": template.type,
                    "subject": template.subject or "",
                    "message": template.message or "",
                    "enabled": template.enabled,
                    "automate": template.automate,
                    "to": template.to or [],
                    "cc": template.cc or [],
                    "bcc": template.bcc or [],
                }
            )
            id_mapping.add(ObjectType.EMAIL_TEMPLATE, template.id, new_template.id)
            result.created.append((ObjectType.EMAIL_TEMPLATE, template.id, new_template.id, template.name))
        except Exception as e:
            result.failed.append((ObjectType.EMAIL_TEMPLATE, template.id, template.name, str(e)))

    def _copy_rules(
        self,
        source_client: SyncRossumAPIClient,
        target_client: SyncRossumAPIClient,
        source_schema_urls: set[str],
        id_mapping: IdMapping,
        result: CopyResult,
    ) -> None:
        for rule in source_client.list_rules():
            if rule.schema is None or rule.schema not in source_schema_urls:
                continue

            self._copy_single_rule(rule, target_client, id_mapping, result)

    def _copy_single_rule(
        self, rule: Rule, target_client: SyncRossumAPIClient, id_mapping: IdMapping, result: CopyResult
    ) -> None:
        if rule.schema is None:
            result.skipped.append((ObjectType.RULE, rule.id, rule.name, "no schema"))
            return

        try:
            source_schema_id = int(rule.schema.split("/")[-1])
            target_schema_id = id_mapping.get(ObjectType.SCHEMA, source_schema_id)
            if not target_schema_id:
                result.skipped.append((ObjectType.RULE, rule.id, rule.name, "no target schema"))
                return

            target_schema_url = f"{target_client.internal_client.base_url}/schemas/{target_schema_id}"

            actions_data = [
                {
                    "id": action.id,
                    "type": action.type,
                    "payload": action.payload,
                    "event": action.event,
                    "enabled": action.enabled,
                }
                for action in (rule.actions or [])
            ]

            new_rule = target_client.create_new_rule(
                {
                    "name": rule.name,
                    "schema": target_schema_url,
                    "trigger_condition": rule.trigger_condition,
                    "actions": actions_data,
                    "enabled": rule.enabled,
                }
            )
            id_mapping.add(ObjectType.RULE, rule.id, new_rule.id)
            result.created.append((ObjectType.RULE, rule.id, new_rule.id, rule.name))
        except Exception as e:
            result.failed.append((ObjectType.RULE, rule.id, rule.name, str(e)))

    def copy_org(
        self,
        source_org_id: int,
        target_org_id: int,
        target_api_base: str | None = None,
        target_token: str | None = None,
    ) -> CopyResult:
        """Copy all objects from source org to target org.

        Creates new objects in target org, mapping IDs for references.
        Use this to set up a sandbox that mirrors production.

        Args:
            source_org_id: Source organization ID (e.g., production)
            target_org_id: Target organization ID (e.g., sandbox)
            target_api_base: API base for target org (if different from source)
            target_token: API token for target org (if different from source)
        """
        source_client = self.client
        target_client = self._get_target_client(target_api_base, target_token)

        result = CopyResult()
        id_mapping = IdMapping(source_org_id=source_org_id, target_org_id=target_org_id)

        source_workspaces = [
            ws for ws in source_client.list_workspaces() if ws.organization and str(source_org_id) in ws.organization
        ]

        self._copy_workspaces(source_workspaces, target_client, target_org_id, id_mapping, result)

        source_queues = self._get_source_queues(source_client, id_mapping)
        self._copy_queues(source_queues, source_client, target_client, id_mapping, result)

        source_queue_urls = {f"{source_client.internal_client.base_url}/queues/{q.id}" for q, _ in source_queues}
        self._copy_hooks(source_client, target_client, source_queue_urls, id_mapping, result)

        result.id_mapping = id_mapping
        self._save_id_mapping(id_mapping)
        return result

    def _get_target_client(self, target_api_base: str | None, target_token: str | None) -> SyncRossumAPIClient:
        """Get the target client for copy operations.

        If target credentials are not provided, uses the same credentials as the source client.
        """
        if target_api_base and target_token:
            return SyncRossumAPIClient(target_api_base, Token(target_token))
        return self.client

    def _copy_workspaces(
        self,
        source_workspaces: list[RossumWorkspace],
        target_client: SyncRossumAPIClient,
        target_org_id: int,
        id_mapping: IdMapping,
        result: CopyResult,
    ) -> None:
        target_org_url = f"{target_client.internal_client.base_url}/organizations/{target_org_id}"

        for ws in source_workspaces:
            try:
                new_ws = target_client.create_new_workspace(
                    {"name": ws.name, "organization": target_org_url, "metadata": ws.metadata or {}}
                )
                id_mapping.add(ObjectType.WORKSPACE, ws.id, new_ws.id)
                result.created.append((ObjectType.WORKSPACE, ws.id, new_ws.id, ws.name))
            except Exception as e:
                result.failed.append((ObjectType.WORKSPACE, ws.id, ws.name, str(e)))

    def _get_source_queues(self, source_client: SyncRossumAPIClient, id_mapping: IdMapping) -> list[tuple[Queue, int]]:
        source_ws_ids = set(id_mapping.get_all(ObjectType.WORKSPACE).keys())
        source_queues = []
        for queue in source_client.list_queues():
            if queue.workspace:
                ws_id = int(queue.workspace.split("/")[-1])
                if ws_id in source_ws_ids:
                    source_queues.append((queue, ws_id))
        return source_queues

    def _copy_queues(
        self,
        source_queues: list[tuple[Queue, int]],
        source_client: SyncRossumAPIClient,
        target_client: SyncRossumAPIClient,
        id_mapping: IdMapping,
        result: CopyResult,
    ) -> None:
        """Copy queues and their schemas to target org."""
        for queue, source_ws_id in source_queues:
            target_ws_id = id_mapping.get(ObjectType.WORKSPACE, source_ws_id)
            if not target_ws_id:
                result.skipped.append((ObjectType.QUEUE, queue.id, queue.name, "workspace not copied"))
                continue

            try:
                source_schema = source_client.retrieve_schema(int(queue.schema.split("/")[-1]))
                schema_content = self._serialize_schema_content(source_schema.content or [])
                new_schema = target_client.create_new_schema(
                    {
                        "name": source_schema.name,
                        "content": schema_content,
                    }
                )
                id_mapping.add(ObjectType.SCHEMA, source_schema.id, new_schema.id)
                result.created.append((ObjectType.SCHEMA, source_schema.id, new_schema.id, source_schema.name))

                target_ws_url = f"{target_client.internal_client.base_url}/workspaces/{target_ws_id}"
                target_schema_url = f"{target_client.internal_client.base_url}/schemas/{new_schema.id}"

                new_queue = target_client.create_new_queue(
                    {
                        "name": queue.name,
                        "workspace": target_ws_url,
                        "schema": target_schema_url,
                        "session_timeout": queue.session_timeout,
                        # rir_url is internal cluster URL, not valid for copying
                        "automation_enabled": queue.automation_enabled,
                        "automation_level": queue.automation_level,
                        "default_score_threshold": queue.default_score_threshold,
                        "locale": queue.locale,
                        "metadata": queue.metadata or {},
                        "settings": queue.settings or {},
                        "use_confirmed_state": queue.use_confirmed_state,
                        "document_lifetime": queue.document_lifetime,
                        "delete_after": queue.delete_after,
                        "training_enabled": queue.training_enabled,
                    }
                )
                id_mapping.add(ObjectType.QUEUE, queue.id, new_queue.id)
                result.created.append((ObjectType.QUEUE, queue.id, new_queue.id, queue.name))
            except Exception as e:
                result.failed.append((ObjectType.QUEUE, queue.id, queue.name, str(e)))

    def _copy_hooks(
        self,
        source_client: SyncRossumAPIClient,
        target_client: SyncRossumAPIClient,
        source_queue_urls: set[str],
        id_mapping: IdMapping,
        result: CopyResult,
    ) -> None:
        for hook in source_client.list_hooks():
            hook_queues = set(hook.queues or [])
            if not (hook_queues & source_queue_urls):
                continue

            self._copy_single_hook(hook, target_client, id_mapping, result)

    def _copy_single_hook(
        self, hook: Hook, target_client: SyncRossumAPIClient, id_mapping: IdMapping, result: CopyResult
    ) -> None:
        try:
            # Rossum Store extensions can't be copied directly - they need to be installed from the store
            if hook.extension_source == "rossum_store":
                result.skipped.append(
                    (ObjectType.HOOK, hook.id, hook.name, "Rossum Store extension - install from store manually")
                )
                return

            target_queue_urls = []
            for q_url in hook.queues or []:
                source_q_id = int(q_url.split("/")[-1])
                target_q_id = id_mapping.get(ObjectType.QUEUE, source_q_id)
                if target_q_id:
                    target_queue_urls.append(f"{target_client.internal_client.base_url}/queues/{target_q_id}")

            if not target_queue_urls:
                result.skipped.append((ObjectType.HOOK, hook.id, hook.name, "no target queues"))
                return

            hook_config = self._remap_hook_config(hook.config or {}, id_mapping)

            new_hook = target_client.create_new_hook(
                {
                    "name": hook.name,
                    "type": hook.type,
                    "queues": target_queue_urls,
                    "events": hook.events or [],
                    "config": hook_config,
                    "sideload": hook.sideload or [],
                    "active": hook.active if hook.active is not None else True,
                    "metadata": hook.metadata or {},
                    "settings": hook.settings or {},
                }
            )
            id_mapping.add(ObjectType.HOOK, hook.id, new_hook.id)
            result.created.append((ObjectType.HOOK, hook.id, new_hook.id, hook.name))
        except Exception as e:
            result.failed.append((ObjectType.HOOK, hook.id, hook.name, str(e)))

    def _remap_hook_config(self, hook_config: dict[str, Any], id_mapping: IdMapping) -> dict[str, Any]:
        """Remap queue IDs in hook config code."""
        if "code" in hook_config:
            code = hook_config["code"]
            for src_id, tgt_id in id_mapping.get_all(ObjectType.QUEUE).items():
                code = code.replace(str(src_id), str(tgt_id))
            hook_config["code"] = code
        return hook_config

    def _serialize_schema_content(self, content: list[Any]) -> list[dict[str, Any]]:
        """Recursively serialize schema content (Section/Datapoint dataclasses) to dicts."""
        result = []
        for item in content:
            if dataclasses.is_dataclass(item) and not isinstance(item, type):
                item_dict = dataclasses.asdict(item)
                cleaned = self._clean_schema_dict(item_dict)
                result.append(cleaned)
            elif isinstance(item, dict):
                cleaned = self._clean_schema_dict(item)
                result.append(cleaned)
            else:
                result.append(item)
        return result

    def _clean_schema_dict(
        self, d: dict[str, Any], in_multivalue_tuple: bool = False, parent_is_multivalue: bool = False
    ) -> dict[str, Any]:
        """Recursively clean schema dict by removing None values and inapplicable fields.

        The `width`, `stretch`, `can_collapse`, `width_chars` fields are only valid for
        datapoints that are children of a multivalue's tuple. The structure is:
        - multivalue node has children: dict (the tuple container)
        - tuple container has children: list (the actual datapoints that can have width etc.)
        """
        fields_to_remove_if_none = {
            "score_threshold",
            "description",
            "formula",
            "prompt",
            "context",
            "grid",
            "ui_configuration",
        }
        fields_for_multivalue_tuple_only = {"width", "stretch", "can_collapse", "width_chars"}

        cleaned: dict[str, Any] = {}
        is_multivalue = d.get("category") == "multivalue"

        for key, value in d.items():
            if value is None and key in fields_to_remove_if_none:
                continue
            if key in fields_for_multivalue_tuple_only and not in_multivalue_tuple:
                continue

            if key == "children":
                if isinstance(value, dict):
                    # Multivalue's children is a dict (tuple container)
                    # Pass parent_is_multivalue so the tuple knows its list children get width
                    cleaned[key] = self._clean_schema_dict(
                        value, in_multivalue_tuple=False, parent_is_multivalue=is_multivalue
                    )
                elif isinstance(value, list):
                    # If parent was multivalue (we're in the tuple), list items can have width
                    child_in_tuple = parent_is_multivalue or in_multivalue_tuple
                    cleaned[key] = [
                        self._clean_schema_dict(item, child_in_tuple, parent_is_multivalue=False)
                        if isinstance(item, dict)
                        else item
                        for item in value
                    ]
                else:
                    cleaned[key] = value
            elif isinstance(value, dict):
                cleaned[key] = self._clean_schema_dict(value, in_multivalue_tuple, parent_is_multivalue=False)
            elif isinstance(value, list):
                cleaned[key] = [
                    self._clean_schema_dict(item, in_multivalue_tuple, parent_is_multivalue=False)
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                cleaned[key] = value

        return cleaned

    def _save_id_mapping(self, id_mapping: IdMapping) -> Path:
        self.path.mkdir(parents=True, exist_ok=True)
        mapping_path = self.path / f".id_mapping_{id_mapping.source_org_id}_to_{id_mapping.target_org_id}.json"
        with open(mapping_path, "w") as f:
            json.dump(id_mapping.model_dump(mode="json"), f, indent=2)
        return mapping_path

    def _load_id_mapping(self, source_org_id: int, target_org_id: int) -> IdMapping | None:
        mapping_path = self.path / f".id_mapping_{source_org_id}_to_{target_org_id}.json"
        if not mapping_path.exists():
            return None
        with open(mapping_path) as f:
            result: IdMapping = IdMapping.model_validate(json.load(f))
            return result

    def deploy(
        self,
        target_org_id: int,
        target_api_base: str | None = None,
        target_token: str | None = None,
        id_mapping: IdMapping | None = None,
        dry_run: bool = False,
    ) -> DeployResult:
        """Deploy local changes to a target organization.

        Uses ID mapping to update corresponding objects in target org.
        Objects without a mapping are skipped (not created). Use copy_org first
        to create the target objects and generate the ID mapping.

        Args:
            target_org_id: Target organization ID to deploy to
            target_api_base: API base for target org (if different)
            target_token: API token for target org (if different)
            id_mapping: ID mapping from copy_org (auto-loaded if not provided)
            dry_run: If True, only show what would be deployed

        Raises:
            ValueError: If no source org_id is configured (run pull first)
            ValueError: If no ID mapping found (run copy_org first)
        """

        source_client = self.client

        if target_api_base and target_token:
            target_client = SyncRossumAPIClient(target_api_base, Token(target_token))
        else:
            target_client = source_client

        source_org_id = self._config.org_id if self._config else None
        if not source_org_id:
            raise ValueError("No source org_id configured. Run pull first.")

        if id_mapping is None:
            id_mapping = self._load_id_mapping(source_org_id, target_org_id)

        if id_mapping is None:
            raise ValueError(
                f"No ID mapping found for {source_org_id} → {target_org_id}. Run copy_org first to create the sandbox."
            )

        source_ws_paths = self._list_local_objects(ObjectType.WORKSPACE)
        if source_ws_paths:
            source_ws_id = self._load_object(source_ws_paths[0]).meta.object_id
            target_ws_id = id_mapping.get(ObjectType.WORKSPACE, source_ws_id) or 0
            id_mapping = self._normalize_id_mapping(id_mapping, source_ws_id, target_ws_id)

        result = DeployResult()

        for obj_type in PUSHABLE_TYPES:
            for path in self._list_local_objects(obj_type):
                local_obj = self._load_object(path)
                source_id = local_obj.meta.object_id
                name = local_obj.data.get("name", f"Object {source_id}")

                target_id = id_mapping.get(obj_type, source_id)
                if not target_id:
                    result.skipped.append((obj_type, source_id, name, "no target mapping"))
                    continue

                if dry_run:
                    result.updated.append((obj_type, target_id, name))
                    continue

                try:
                    data = self._prepare_deploy_data(local_obj.data, obj_type, id_mapping, target_client)
                    self._push_object(target_client, obj_type, target_id, data)
                    result.updated.append((obj_type, target_id, name))
                except Exception as e:
                    result.failed.append((obj_type, source_id, name, str(e)))

        return result

    def _prepare_deploy_data(
        self, data: dict[str, Any], obj_type: ObjectType, id_mapping: IdMapping, target_client: SyncRossumAPIClient
    ) -> dict[str, Any]:
        """Prepare object data for deployment by replacing IDs."""
        prepared = {k: v for k, v in data.items() if k not in IGNORED_FIELDS and not k.startswith("_")}
        target_base = target_client.internal_client.base_url

        if obj_type == ObjectType.QUEUE:
            self._prepare_queue_deploy_data(prepared, id_mapping, target_base)
        elif obj_type == ObjectType.HOOK:
            self._prepare_hook_deploy_data(prepared, id_mapping, target_base)
        elif obj_type == ObjectType.INBOX:
            # Inbox-queue relationship is immutable after creation
            # email and email_hash are auto-generated and cannot be updated
            prepared.pop("queue", None)
            prepared.pop("queues", None)
            prepared.pop("email", None)
            prepared.pop("email_hash", None)
        elif obj_type == ObjectType.EMAIL_TEMPLATE:
            self._prepare_email_template_deploy_data(prepared, id_mapping, target_base)
        elif obj_type == ObjectType.SCHEMA and "content" in prepared:
            prepared["content"] = self._clean_schema_content(prepared["content"])

        return prepared

    def _prepare_queue_deploy_data(self, prepared: dict[str, Any], id_mapping: IdMapping, target_base: str) -> None:
        """Remap queue references for deployment."""
        if "schema" in prepared:
            source_schema_id = int(prepared["schema"].split("/")[-1])
            target_schema_id = id_mapping.get(ObjectType.SCHEMA, source_schema_id)
            if target_schema_id:
                prepared["schema"] = f"{target_base}/schemas/{target_schema_id}"

        if "workspace" in prepared:
            source_ws_id = int(prepared["workspace"].split("/")[-1])
            target_ws_id = id_mapping.get(ObjectType.WORKSPACE, source_ws_id)
            if target_ws_id:
                prepared["workspace"] = f"{target_base}/workspaces/{target_ws_id}"

        # Always remove inbox - it's immutable after queue creation
        # Trying to update it (even with a remapped value) causes API errors
        prepared.pop("inbox", None)

    def _prepare_hook_deploy_data(self, prepared: dict[str, Any], id_mapping: IdMapping, target_base: str) -> None:
        """Remap hook references for deployment."""
        if "queues" in prepared:
            target_queues = []
            for q_url in prepared["queues"]:
                source_q_id = int(q_url.split("/")[-1])
                target_q_id = id_mapping.get(ObjectType.QUEUE, source_q_id)
                if target_q_id:
                    target_queues.append(f"{target_base}/queues/{target_q_id}")
            prepared["queues"] = target_queues

        if "config" in prepared and isinstance(prepared["config"], dict):
            prepared["config"] = self._remap_hook_config(prepared["config"], id_mapping)

    def _prepare_email_template_deploy_data(
        self, prepared: dict[str, Any], id_mapping: IdMapping, target_base: str
    ) -> None:
        """Remap email template references for deployment."""
        if prepared.get("queue"):
            source_q_id = int(prepared["queue"].split("/")[-1])
            target_q_id = id_mapping.get(ObjectType.QUEUE, source_q_id)
            if target_q_id:
                prepared["queue"] = f"{target_base}/queues/{target_q_id}"
            else:
                del prepared["queue"]
