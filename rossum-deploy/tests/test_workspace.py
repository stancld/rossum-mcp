from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, patch

import pytest
from rossum_deploy.constants import DIFFABLE_TYPES, OBJECT_TYPE_TO_RESOURCE, PUSHABLE_TYPES
from rossum_deploy.models import CopyResult, IdMapping, ObjectType
from rossum_deploy.workspace import Workspace, WorkspaceConfig

if TYPE_CHECKING:
    from pathlib import Path


class TestWorkspaceConfig:
    def test_to_dict(self):
        config = WorkspaceConfig(api_base="https://api.example.com/v1", org_id=123)
        assert config.to_dict() == {"api_base": "https://api.example.com/v1", "org_id": 123}

    def test_from_dict(self):
        config = WorkspaceConfig.from_dict({"api_base": "https://api.example.com/v1", "org_id": 456})
        assert config.api_base == "https://api.example.com/v1"
        assert config.org_id == 456


class TestWorkspace:
    def test_init_creates_path(self, workspace: Workspace, tmp_workspace: Path):
        assert workspace.path == tmp_workspace

    def test_object_path_sanitizes_name(self, workspace: Workspace):
        path = workspace._object_path(ObjectType.QUEUE, 123, "Test/Queue:Special")
        assert path.name == "Test_Queue_Special_123.json"

    def test_save_and_load_object(self, workspace: Workspace):
        data = {"id": 123, "name": "Test Queue", "settings": {"key": "value"}}
        path = workspace._save_object(ObjectType.QUEUE, 123, "Test Queue", data)

        assert path.exists()

        loaded = workspace._load_object(path)
        assert loaded.meta.object_id == 123
        assert loaded.meta.object_type == ObjectType.QUEUE
        assert loaded.data["name"] == "Test Queue"

    def test_list_local_objects_empty(self, workspace: Workspace):
        objects = workspace._list_local_objects(ObjectType.QUEUE)
        assert objects == []

    def test_list_local_objects(self, workspace: Workspace):
        workspace._save_object(ObjectType.QUEUE, 1, "Queue 1", {"id": 1})
        workspace._save_object(ObjectType.QUEUE, 2, "Queue 2", {"id": 2})

        objects = workspace._list_local_objects(ObjectType.QUEUE)
        assert len(objects) == 2

    def test_compare_objects(self, workspace: Workspace):
        local = {"name": "Old Name", "settings": {"a": 1}}
        remote = {"name": "New Name", "settings": {"a": 1}}

        changed = workspace._compare_objects(local, remote)
        assert changed == ["name"]

    def test_compare_objects_ignores_meta_fields(self, workspace: Workspace):
        local = {"name": "Same", "modified_at": "2024-01-01"}
        remote = {"name": "Same", "modified_at": "2024-01-02"}

        changed = workspace._compare_objects(local, remote)
        assert changed == []

    def test_client_property_returns_client(self, workspace: Workspace):
        assert workspace.client is not None


class TestPullMethods:
    """Tests for pull_* methods."""

    def test_get_workspace_ids(self, workspace: Workspace):
        workspace._save_object(
            ObjectType.WORKSPACE, 111, "Workspace 1", {"id": 111, "url": "https://api.example.com/v1/workspaces/111"}
        )
        workspace._save_object(
            ObjectType.WORKSPACE, 222, "Workspace 2", {"id": 222, "url": "https://api.example.com/v1/workspaces/222"}
        )

        ws_ids = workspace._get_workspace_ids()
        assert ws_ids == {111, 222}

    def test_get_queue_urls(self, workspace: Workspace):
        workspace._save_object(ObjectType.QUEUE, 1, "Queue 1", {"id": 1, "url": "https://api.example.com/v1/queues/1"})
        workspace._save_object(ObjectType.QUEUE, 2, "Queue 2", {"id": 2, "url": "https://api.example.com/v1/queues/2"})

        queue_urls = workspace._get_queue_urls()
        assert queue_urls == {"https://api.example.com/v1/queues/1", "https://api.example.com/v1/queues/2"}

    def test_get_schema_ids_from_queues(self, workspace: Workspace):
        workspace._save_object(
            ObjectType.QUEUE, 1, "Queue 1", {"id": 1, "schema": "https://api.example.com/v1/schemas/100"}
        )
        workspace._save_object(
            ObjectType.QUEUE, 2, "Queue 2", {"id": 2, "schema": "https://api.example.com/v1/schemas/200"}
        )

        schema_ids = workspace._get_schema_ids_from_queues()
        assert schema_ids == {100, 200}


class TestDiffMethod:
    """Tests for diff method."""

    def test_diff_unchanged(self, workspace: Workspace):
        local_data = {"id": 1, "name": "Test Queue", "settings": {"key": "value"}}
        modified_at = datetime(2024, 1, 1, tzinfo=UTC)
        workspace._save_object(ObjectType.QUEUE, 1, "Test Queue", local_data, remote_modified_at=modified_at)

        with patch.object(workspace, "_fetch_remote_object") as mock_fetch:
            mock_fetch.return_value = (local_data, modified_at)
            result = workspace.diff()

        assert result.total_unchanged == 1
        assert result.total_local_modified == 0

    def test_diff_local_modified(self, workspace: Workspace):
        local_data = {"id": 1, "name": "Modified Name", "settings": {"key": "value"}}
        remote_data = {"id": 1, "name": "Original Name", "settings": {"key": "value"}}
        modified_at = datetime(2024, 1, 1, tzinfo=UTC)
        workspace._save_object(
            ObjectType.QUEUE,
            1,
            "Modified Name",
            local_data,
            remote_modified_at=modified_at,
        )

        with (
            patch.object(workspace, "_fetch_remote_object") as mock_fetch,
            patch.object(workspace, "_is_git_modified", return_value=True),
        ):
            mock_fetch.return_value = (remote_data, modified_at)
            result = workspace.diff()

        assert result.total_local_modified == 1
        assert result.objects[0].changed_fields == ["name"]


class TestPushMethod:
    """Tests for push method."""

    def test_push_dry_run(self, workspace: Workspace):
        local_data = {"id": 1, "name": "Modified Name"}
        remote_data = {"id": 1, "name": "Original Name"}
        modified_at = datetime(2024, 1, 1, tzinfo=UTC)
        workspace._save_object(ObjectType.QUEUE, 1, "Modified Name", local_data, remote_modified_at=modified_at)

        with patch.object(workspace, "_fetch_remote_object") as mock_fetch:
            mock_fetch.return_value = (remote_data, modified_at)
            result = workspace.push(dry_run=True)

        assert len(result.pushed) == 1
        assert result.pushed[0] == (ObjectType.QUEUE, 1, "Modified Name")

    def test_push_uses_internal_client_update(self, workspace: Workspace):
        local_data = {"id": 1, "name": "Modified Name"}
        remote_data = {"id": 1, "name": "Original Name"}
        modified_at = datetime(2024, 1, 1, tzinfo=UTC)
        workspace._save_object(ObjectType.QUEUE, 1, "Modified Name", local_data, remote_modified_at=modified_at)

        with (
            patch.object(workspace, "_fetch_remote_object") as mock_fetch,
            patch.object(workspace, "_client") as mock_client,
        ):
            mock_fetch.return_value = (remote_data, modified_at)
            result = workspace.push()

        assert len(result.pushed) == 1
        mock_client.internal_client.update.assert_called_once()


class TestSupportedTypes:
    """Tests for supported object types."""

    def test_diffable_types_include_new_types(self):
        expected_types = {
            ObjectType.WORKSPACE,
            ObjectType.QUEUE,
            ObjectType.SCHEMA,
            ObjectType.INBOX,
            ObjectType.HOOK,
            ObjectType.CONNECTOR,
            ObjectType.ENGINE,
            ObjectType.EMAIL_TEMPLATE,
            ObjectType.RULE,
        }
        assert set(DIFFABLE_TYPES) == expected_types

    def test_pushable_types_include_new_types(self):
        expected_types = {
            ObjectType.WORKSPACE,
            ObjectType.QUEUE,
            ObjectType.SCHEMA,
            ObjectType.INBOX,
            ObjectType.HOOK,
            ObjectType.CONNECTOR,
            ObjectType.ENGINE,
            ObjectType.EMAIL_TEMPLATE,
            ObjectType.RULE,
        }
        assert set(PUSHABLE_TYPES) == expected_types

    def test_object_type_to_resource_mapping(self):
        from rossum_api.domain_logic.resources import Resource

        assert OBJECT_TYPE_TO_RESOURCE[ObjectType.QUEUE] == Resource.Queue
        assert OBJECT_TYPE_TO_RESOURCE[ObjectType.SCHEMA] == Resource.Schema
        assert OBJECT_TYPE_TO_RESOURCE[ObjectType.HOOK] == Resource.Hook
        assert OBJECT_TYPE_TO_RESOURCE[ObjectType.CONNECTOR] == Resource.Connector
        assert OBJECT_TYPE_TO_RESOURCE[ObjectType.ENGINE] == Resource.Engine
        assert OBJECT_TYPE_TO_RESOURCE[ObjectType.RULE] == Resource.Rule
        assert OBJECT_TYPE_TO_RESOURCE[ObjectType.EMAIL_TEMPLATE] == Resource.EmailTemplate


class TestCopyOrg:
    """Tests for copy_org method."""

    def test_save_and_load_id_mapping(self, workspace: Workspace):
        mapping = IdMapping(source_org_id=123, target_org_id=456)
        mapping.add(ObjectType.QUEUE, 100, 200)
        mapping.add(ObjectType.HOOK, 500, 600)

        workspace._save_id_mapping(mapping)

        loaded = workspace._load_id_mapping(123, 456)
        assert loaded is not None
        assert loaded.get(ObjectType.QUEUE, 100) == 200
        assert loaded.get(ObjectType.HOOK, 500) == 600

    def test_load_id_mapping_returns_none_if_not_exists(self, workspace: Workspace):
        loaded = workspace._load_id_mapping(999, 888)
        assert loaded is None


class TestCopyWorkspace:
    """Tests for copy_workspace method."""

    def test_copy_workspace_creates_objects(self, workspace: Workspace):
        mock_workspace = Mock()
        mock_workspace.id = 100
        mock_workspace.name = "Test Workspace"
        mock_workspace.organization = "https://api.example.com/v1/organizations/123"
        mock_workspace.metadata = {}

        mock_queue = Mock()
        mock_queue.id = 200
        mock_queue.name = "Test Queue"
        mock_queue.workspace = "https://api.example.com/v1/workspaces/100"
        mock_queue.schema = "https://api.example.com/v1/schemas/300"

        mock_schema = Mock()
        mock_schema.id = 300
        mock_schema.name = "Test Schema"
        mock_schema.content = []

        mock_new_workspace = Mock()
        mock_new_workspace.id = 101

        mock_new_schema = Mock()
        mock_new_schema.id = 301

        mock_new_queue = Mock()
        mock_new_queue.id = 201

        with patch.object(workspace, "_client") as mock_client:
            mock_client.internal_client.base_url = "https://api.example.com/v1"
            mock_client.retrieve_workspace.return_value = mock_workspace
            mock_client.list_queues.return_value = [mock_queue]
            mock_client.retrieve_schema.return_value = mock_schema
            mock_client.list_engines.return_value = []
            mock_client.list_hooks.return_value = []
            mock_client.list_connectors.return_value = []
            mock_client.request_paginated.return_value = []
            mock_client.list_email_templates.return_value = []
            mock_client.list_rules.return_value = []
            mock_client.create_new_workspace.return_value = mock_new_workspace
            mock_client.create_new_schema.return_value = mock_new_schema
            mock_client.create_new_queue.return_value = mock_new_queue

            result = workspace.copy_workspace(source_workspace_id=100, target_org_id=456)

        workspace_created = [c for c in result.created if c[0] == ObjectType.WORKSPACE]
        assert len(workspace_created) == 1
        assert workspace_created[0][1] == 100
        assert workspace_created[0][2] == 101
        assert workspace_created[0][3] == "Test Workspace"

    def test_get_workspace_queues(self, workspace: Workspace):
        mock_queue1 = Mock()
        mock_queue1.id = 100
        mock_queue1.workspace = "https://api.example.com/v1/workspaces/10"

        mock_queue2 = Mock()
        mock_queue2.id = 200
        mock_queue2.workspace = "https://api.example.com/v1/workspaces/20"

        mock_queue3 = Mock()
        mock_queue3.id = 300
        mock_queue3.workspace = "https://api.example.com/v1/workspaces/10"

        with patch.object(workspace, "_client") as mock_client:
            mock_client.list_queues.return_value = [mock_queue1, mock_queue2, mock_queue3]

            queues = workspace._get_workspace_queues(mock_client, 10)

        assert len(queues) == 2
        queue_ids = {q.id for q, _ in queues}
        assert queue_ids == {100, 300}


class TestDeploy:
    """Tests for deploy method."""

    def test_deploy_requires_id_mapping(self, workspace: Workspace):
        workspace._config = WorkspaceConfig(api_base="https://api.example.com/v1", org_id=123)

        with pytest.raises(ValueError, match="No ID mapping found"):
            workspace.deploy(target_org_id=456, dry_run=True)

    def test_deploy_dry_run(self, workspace: Workspace):
        workspace._config = WorkspaceConfig(api_base="https://api.example.com/v1", org_id=123)

        mapping = IdMapping(source_org_id=123, target_org_id=456)
        mapping.add(ObjectType.QUEUE, 100, 200)
        workspace._save_id_mapping(mapping)

        workspace._save_object(ObjectType.QUEUE, 100, "Test Queue", {"id": 100, "name": "Test Queue"})

        with patch.object(workspace, "_client") as mock_client:
            mock_client.internal_client.base_url = "https://api.example.com/v1"
            result = workspace.deploy(target_org_id=456, dry_run=True)

        assert len(result.updated) == 1
        assert result.updated[0] == (ObjectType.QUEUE, 200, "Test Queue")

    def test_prepare_deploy_data_replaces_queue_urls(self, workspace: Workspace):
        mapping = IdMapping(source_org_id=123, target_org_id=456)
        mapping.add(ObjectType.QUEUE, 100, 200)
        mapping.add(ObjectType.SCHEMA, 50, 60)
        mapping.add(ObjectType.WORKSPACE, 10, 20)

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.target.com/v1"

        data = {
            "id": 100,
            "name": "Test Queue",
            "schema": "https://api.source.com/v1/schemas/50",
            "workspace": "https://api.source.com/v1/workspaces/10",
        }

        prepared = workspace._prepare_deploy_data(data, ObjectType.QUEUE, mapping, mock_client)

        assert prepared["schema"] == "https://api.target.com/v1/schemas/60"
        assert prepared["workspace"] == "https://api.target.com/v1/workspaces/20"

    def test_prepare_deploy_data_replaces_hook_queues(self, workspace: Workspace):
        mapping = IdMapping(source_org_id=123, target_org_id=456)
        mapping.add(ObjectType.QUEUE, 100, 200)
        mapping.add(ObjectType.QUEUE, 101, 201)

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.target.com/v1"

        data = {
            "id": 500,
            "name": "Test Hook",
            "queues": ["https://api.source.com/v1/queues/100", "https://api.source.com/v1/queues/101"],
        }

        prepared = workspace._prepare_deploy_data(data, ObjectType.HOOK, mapping, mock_client)

        assert prepared["queues"] == ["https://api.target.com/v1/queues/200", "https://api.target.com/v1/queues/201"]

    def test_prepare_deploy_data_replaces_ids_in_hook_code(self, workspace: Workspace):
        mapping = IdMapping(source_org_id=123, target_org_id=456)
        mapping.add(ObjectType.QUEUE, 100, 200)

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.target.com/v1"

        data = {
            "id": 500,
            "name": "Test Hook",
            "queues": [],
            "config": {"code": "queue_id = 100  # hardcoded queue ID", "runtime": "python3.12"},
        }

        prepared = workspace._prepare_deploy_data(data, ObjectType.HOOK, mapping, mock_client)

        assert "200" in prepared["config"]["code"]
        assert "100" not in prepared["config"]["code"]


class TestPullWorkspace:
    """Tests for pull_workspace method."""

    def test_pull_workspace_saves_workspace(self, workspace: Workspace):
        mock_workspace = Mock()
        mock_workspace.id = 100
        mock_workspace.name = "Test Workspace"
        mock_workspace.organization = "https://api.example.com/v1/organizations/123"
        mock_workspace.url = "https://api.example.com/v1/workspaces/100"
        mock_workspace.metadata = {}
        mock_workspace.modified_at = None

        with (
            patch.object(workspace, "_client") as mock_client,
            patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict,
        ):
            mock_asdict.return_value = {
                "id": 100,
                "name": "Test Workspace",
                "organization": "https://api.example.com/v1/organizations/123",
                "url": "https://api.example.com/v1/workspaces/100",
            }
            mock_client.retrieve_workspace.return_value = mock_workspace
            mock_client.list_queues.return_value = []
            mock_client.list_hooks.return_value = []
            mock_client.list_connectors.return_value = []
            mock_client.list_engines.return_value = []
            mock_client.list_email_templates.return_value = []
            mock_client.list_rules.return_value = []
            mock_client.request_paginated.return_value = []

            result = workspace.pull_workspace(workspace_id=100)

        assert len(result.pulled) >= 1
        workspace_pulled = [p for p in result.pulled if p[0] == ObjectType.WORKSPACE]
        assert len(workspace_pulled) == 1
        assert workspace_pulled[0][1] == 100

    def test_pull_workspace_filters_types(self, workspace: Workspace):
        mock_workspace = Mock()
        mock_workspace.id = 100
        mock_workspace.name = "Test Workspace"
        mock_workspace.organization = "https://api.example.com/v1/organizations/123"
        mock_workspace.url = "https://api.example.com/v1/workspaces/100"
        mock_workspace.metadata = {}
        mock_workspace.modified_at = None

        with (
            patch.object(workspace, "_client") as mock_client,
            patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict,
        ):
            mock_asdict.return_value = {
                "id": 100,
                "name": "Test Workspace",
                "organization": "https://api.example.com/v1/organizations/123",
                "url": "https://api.example.com/v1/workspaces/100",
            }
            mock_client.retrieve_workspace.return_value = mock_workspace

            result = workspace.pull_workspace(workspace_id=100)

        assert len(result.pulled) == 1
        assert result.pulled[0][0] == ObjectType.WORKSPACE


class TestCompareWorkspaces:
    """Tests for compare_workspaces method."""

    def test_compare_workspaces_identical(self, tmp_workspace: Path):
        source_path = tmp_workspace / "source"
        target_path = tmp_workspace / "target"

        source_ws = Workspace(source_path, api_base="https://api.example.com/v1", token="test-token")
        target_ws = Workspace(target_path, api_base="https://api.example.com/v1", token="test-token")

        source_ws._save_object(ObjectType.WORKSPACE, 100, "Test Workspace", {"id": 100, "name": "Test Workspace"})
        source_ws._save_object(
            ObjectType.QUEUE, 200, "Test Queue", {"id": 200, "name": "Test Queue", "settings": {"key": "value"}}
        )

        target_ws._save_object(ObjectType.WORKSPACE, 101, "Test Workspace", {"id": 101, "name": "Test Workspace"})
        target_ws._save_object(
            ObjectType.QUEUE, 201, "Test Queue", {"id": 201, "name": "Test Queue", "settings": {"key": "value"}}
        )

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.WORKSPACE, 100, 101)
        mapping.add(ObjectType.QUEUE, 200, 201)

        result = source_ws.compare_workspaces(target_ws, id_mapping=mapping)

        assert result.source_workspace_id == 100
        assert result.target_workspace_id == 101
        assert result.total_identical == 2
        assert result.total_different == 0

    def test_compare_workspaces_with_differences(self, tmp_workspace: Path):
        source_path = tmp_workspace / "source"
        target_path = tmp_workspace / "target"

        source_ws = Workspace(source_path, api_base="https://api.example.com/v1", token="test-token")
        target_ws = Workspace(target_path, api_base="https://api.example.com/v1", token="test-token")

        source_ws._save_object(ObjectType.WORKSPACE, 100, "Test Workspace", {"id": 100, "name": "Test Workspace"})
        source_ws._save_object(
            ObjectType.QUEUE, 200, "Test Queue", {"id": 200, "name": "Original Name", "settings": {"key": "value1"}}
        )

        target_ws._save_object(ObjectType.WORKSPACE, 101, "Test Workspace", {"id": 101, "name": "Test Workspace"})
        target_ws._save_object(
            ObjectType.QUEUE,
            201,
            "Modified Queue",
            {"id": 201, "name": "Modified Name", "settings": {"key": "value2"}},
        )

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.WORKSPACE, 100, 101)
        mapping.add(ObjectType.QUEUE, 200, 201)

        result = target_ws.compare_workspaces(source_ws, id_mapping=mapping)

        assert result.total_identical == 1
        assert result.total_different == 1

        different_objs = [o for o in result.objects if not o.is_identical]
        assert len(different_objs) == 1
        assert different_objs[0].object_type == ObjectType.QUEUE
        changed_fields = {d.field for d in different_objs[0].field_diffs}
        assert "name" in changed_fields
        assert "settings" in changed_fields

    def test_compare_workspaces_source_only(self, tmp_workspace: Path):
        source_path = tmp_workspace / "source"
        target_path = tmp_workspace / "target"

        source_ws = Workspace(source_path, api_base="https://api.example.com/v1", token="test-token")
        target_ws = Workspace(target_path, api_base="https://api.example.com/v1", token="test-token")

        source_ws._save_object(ObjectType.WORKSPACE, 100, "Test Workspace", {"id": 100, "name": "Test Workspace"})
        source_ws._save_object(ObjectType.HOOK, 300, "Source Only Hook", {"id": 300, "name": "Source Only Hook"})

        target_ws._save_object(ObjectType.WORKSPACE, 101, "Test Workspace", {"id": 101, "name": "Test Workspace"})

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.WORKSPACE, 100, 101)

        result = source_ws.compare_workspaces(target_ws, id_mapping=mapping)

        assert len(result.source_only) == 1
        assert result.source_only[0] == (ObjectType.HOOK, 300, "Source Only Hook")

    def test_compare_workspaces_target_only(self, tmp_workspace: Path):
        source_path = tmp_workspace / "source"
        target_path = tmp_workspace / "target"

        source_ws = Workspace(source_path, api_base="https://api.example.com/v1", token="test-token")
        target_ws = Workspace(target_path, api_base="https://api.example.com/v1", token="test-token")

        source_ws._save_object(ObjectType.WORKSPACE, 100, "Test Workspace", {"id": 100, "name": "Test Workspace"})

        target_ws._save_object(ObjectType.WORKSPACE, 101, "Test Workspace", {"id": 101, "name": "Test Workspace"})
        target_ws._save_object(ObjectType.RULE, 400, "New Rule", {"id": 400, "name": "New Rule"})

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.WORKSPACE, 100, 101)

        result = source_ws.compare_workspaces(target_ws, id_mapping=mapping)

        assert len(result.target_only) == 1
        assert result.target_only[0] == (ObjectType.RULE, 400, "New Rule")

    def test_compare_workspaces_summary(self, tmp_workspace: Path):
        source_path = tmp_workspace / "source"
        target_path = tmp_workspace / "target"

        source_ws = Workspace(source_path, api_base="https://api.example.com/v1", token="test-token")
        target_ws = Workspace(target_path, api_base="https://api.example.com/v1", token="test-token")

        source_ws._save_object(ObjectType.WORKSPACE, 100, "Test Workspace", {"id": 100, "name": "Test Workspace"})

        target_ws._save_object(
            ObjectType.WORKSPACE, 101, "Modified Workspace", {"id": 101, "name": "Modified Workspace"}
        )

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.WORKSPACE, 100, 101)

        result = source_ws.compare_workspaces(target_ws, id_mapping=mapping)
        summary = result.summary()

        assert "Workspace Comparison" in summary
        assert "Source workspace: 100" in summary
        assert "Target workspace: 101" in summary
        assert "Differences" in summary

    def test_normalize_value_remaps_ids(self, workspace: Workspace):
        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        value = "https://api.example.com/v1/queues/100"
        normalized = workspace._normalize_value(value, mapping)

        assert normalized == "https://api.example.com/v1/queues/200"

    def test_normalize_value_handles_lists(self, workspace: Workspace):
        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)
        mapping.add(ObjectType.QUEUE, 101, 201)

        value = ["https://api.example.com/v1/queues/100", "https://api.example.com/v1/queues/101"]
        normalized = workspace._normalize_value(value, mapping)

        assert normalized == ["https://api.example.com/v1/queues/200", "https://api.example.com/v1/queues/201"]

    def test_normalize_value_handles_dicts(self, workspace: Workspace):
        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        value = {"queue": "https://api.example.com/v1/queues/100", "nested": {"id": 999}}
        normalized = workspace._normalize_value(value, mapping)

        assert normalized["queue"] == "https://api.example.com/v1/queues/200"
        assert normalized["nested"]["id"] == 999

    def test_normalize_value_handles_none(self, workspace: Workspace):
        mapping = IdMapping(source_org_id=1, target_org_id=2)
        assert workspace._normalize_value(None, mapping) is None

    def test_normalize_value_without_mapping(self, workspace: Workspace):
        value = "https://api.example.com/v1/queues/100"
        normalized = workspace._normalize_value(value, None)
        assert normalized == value


class TestDiffMethodEdgeCases:
    """Tests for diff method edge cases."""

    def test_diff_local_only(self, workspace: Workspace):
        local_data = {"id": 1, "name": "Test Queue"}
        workspace._save_object(ObjectType.QUEUE, 1, "Test Queue", local_data, remote_modified_at=None)

        with patch.object(workspace, "_fetch_remote_object") as mock_fetch:
            mock_fetch.side_effect = Exception("Not found")
            result = workspace.diff()

        local_only = [o for o in result.objects if o.status.value == "local_only"]
        assert len(local_only) == 1

    def test_diff_remote_modified(self, workspace: Workspace):
        local_data = {"id": 1, "name": "Test Queue"}
        local_modified = datetime(2024, 1, 1, tzinfo=UTC)
        remote_modified = datetime(2024, 1, 2, tzinfo=UTC)
        remote_data = {"id": 1, "name": "Modified Name"}

        workspace._save_object(
            ObjectType.QUEUE,
            1,
            "Test Queue",
            local_data,
            remote_modified_at=local_modified,
        )

        with patch.object(workspace, "_fetch_remote_object") as mock_fetch:
            mock_fetch.return_value = (remote_data, remote_modified)
            result = workspace.diff()

        assert result.total_remote_modified == 1

    def test_diff_conflict(self, workspace: Workspace):
        """Conflict occurs when both local (Git) and remote changes exist."""
        local_data = {"id": 1, "name": "Local Name"}
        remote_data = {"id": 1, "name": "Remote Name"}
        local_modified = datetime(2024, 1, 1, tzinfo=UTC)
        remote_modified = datetime(2024, 1, 2, tzinfo=UTC)

        workspace._save_object(ObjectType.QUEUE, 1, "Test Queue", local_data, remote_modified_at=local_modified)

        with (
            patch.object(workspace, "_fetch_remote_object") as mock_fetch,
            patch.object(workspace, "_is_git_modified", return_value=True),
        ):
            mock_fetch.return_value = (remote_data, remote_modified)
            result = workspace.diff()

        assert result.total_conflicts == 1


class TestCopyMethods:
    """Tests for copy-related methods."""

    def test_remap_hook_config(self, workspace: Workspace):
        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)
        mapping.add(ObjectType.QUEUE, 101, 201)

        config = {"code": "queue_ids = [100, 101]", "runtime": "python3.12"}
        result = workspace._remap_hook_config(config, mapping)

        assert "200" in result["code"]
        assert "201" in result["code"]
        assert "100" not in result["code"]
        assert "101" not in result["code"]

    def test_remap_hook_config_no_code(self, workspace: Workspace):
        mapping = IdMapping(source_org_id=1, target_org_id=2)
        config = {"runtime": "python3.12"}
        result = workspace._remap_hook_config(config, mapping)
        assert result == {"runtime": "python3.12"}

    def test_serialize_schema_content_with_dataclass(self, workspace: Workspace):
        import dataclasses

        @dataclasses.dataclass
        class MockDatapoint:
            id: str
            label: str
            score_threshold: float | None = None

        content = [MockDatapoint(id="field1", label="Field 1")]
        result = workspace._serialize_schema_content(content)

        assert len(result) == 1
        assert result[0]["id"] == "field1"
        assert result[0]["label"] == "Field 1"
        assert "score_threshold" not in result[0]

    def test_serialize_schema_content_with_dict(self, workspace: Workspace):
        content = [{"id": "field1", "label": "Field 1", "score_threshold": None}]
        result = workspace._serialize_schema_content(content)

        assert len(result) == 1
        assert result[0]["id"] == "field1"
        assert "score_threshold" not in result[0]

    def test_serialize_schema_content_with_plain_value(self, workspace: Workspace):
        content = ["string_value", 123]
        result = workspace._serialize_schema_content(content)
        assert result == ["string_value", 123]

    def test_clean_schema_dict_tuple_child(self, workspace: Workspace):
        data = {"id": "field1", "category": "tuple", "width": 100, "stretch": True, "can_collapse": False}
        result = workspace._clean_schema_dict(data, in_multivalue_tuple=True)

        assert result["width"] == 100
        assert result["stretch"] is True
        assert result["can_collapse"] is False

    def test_clean_schema_dict_non_tuple(self, workspace: Workspace):
        data = {"id": "field1", "category": "datapoint", "width": 100}
        result = workspace._clean_schema_dict(data)

        assert "width" not in result

    def test_clean_schema_dict_nested(self, workspace: Workspace):
        data = {"id": "section1", "children": [{"id": "field1", "description": None}], "nested": {"formula": None}}
        result = workspace._clean_schema_dict(data)

        assert "description" not in result["children"][0]
        assert "formula" not in result["nested"]

    def test_get_target_client_with_credentials(self, workspace: Workspace):
        client = workspace._get_target_client("https://api.target.com/v1", "target-token")
        assert client is not None
        assert client != workspace.client

    def test_get_target_client_without_credentials(self, workspace: Workspace):
        client = workspace._get_target_client(None, None)
        assert client == workspace.client


class TestCopyWorkspaceInternalMethods:
    """Tests for copy_workspace internal methods."""

    def test_copy_single_hook(self, workspace: Workspace):
        mock_hook = Mock()
        mock_hook.id = 500
        mock_hook.name = "Test Hook"
        mock_hook.type = "function"
        mock_hook.queues = ["https://api.example.com/v1/queues/100"]
        mock_hook.events = ["annotation_content.initialize"]
        mock_hook.config = {"code": "pass"}
        mock_hook.sideload = []
        mock_hook.active = True
        mock_hook.metadata = {}

        mock_new_hook = Mock()
        mock_new_hook.id = 501

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.create_new_hook.return_value = mock_new_hook

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        result = CopyResult()
        workspace._copy_single_hook(mock_hook, mock_client, mapping, result)

        assert len(result.created) == 1
        assert result.created[0][0] == ObjectType.HOOK
        assert mapping.get(ObjectType.HOOK, 500) == 501

    def test_copy_single_hook_no_target_queues(self, workspace: Workspace):
        mock_hook = Mock()
        mock_hook.id = 500
        mock_hook.name = "Test Hook"
        mock_hook.queues = ["https://api.example.com/v1/queues/999"]

        mock_client = MagicMock()
        mapping = IdMapping(source_org_id=1, target_org_id=2)

        result = CopyResult()
        workspace._copy_single_hook(mock_hook, mock_client, mapping, result)

        assert len(result.skipped) == 1
        assert "no target queues" in result.skipped[0][3]

    def test_copy_single_hook_exception(self, workspace: Workspace):
        mock_hook = Mock()
        mock_hook.id = 500
        mock_hook.name = "Test Hook"
        mock_hook.queues = ["https://api.example.com/v1/queues/100"]
        mock_hook.type = "function"
        mock_hook.events = ["annotation_content.initialize"]
        mock_hook.config = {"code": "pass"}
        mock_hook.sideload = []
        mock_hook.active = True
        mock_hook.metadata = {}

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.create_new_hook.side_effect = Exception("API error")

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        result = CopyResult()
        workspace._copy_single_hook(mock_hook, mock_client, mapping, result)

        assert len(result.failed) == 1
        assert "API error" in result.failed[0][3]

    def test_copy_single_connector(self, workspace: Workspace):
        mock_connector = Mock()
        mock_connector.id = 600
        mock_connector.name = "Test Connector"
        mock_connector.queues = ["https://api.example.com/v1/queues/100"]
        mock_connector.service_url = "https://service.example.com"
        mock_connector.authorization_token = "token123"
        mock_connector.params = ""
        mock_connector.asynchronous = False

        mock_new_connector = Mock()
        mock_new_connector.id = 601

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.create_new_connector.return_value = mock_new_connector

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        result = CopyResult()
        workspace._copy_single_connector(mock_connector, mock_client, mapping, result)

        assert len(result.created) == 1
        assert mapping.get(ObjectType.CONNECTOR, 600) == 601

    def test_copy_single_connector_no_target_queues(self, workspace: Workspace):
        mock_connector = Mock()
        mock_connector.id = 600
        mock_connector.name = "Test Connector"
        mock_connector.queues = ["https://api.example.com/v1/queues/999"]

        mock_client = MagicMock()
        mapping = IdMapping(source_org_id=1, target_org_id=2)

        result = CopyResult()
        workspace._copy_single_connector(mock_connector, mock_client, mapping, result)

        assert len(result.skipped) == 1

    def test_copy_single_engine(self, workspace: Workspace):
        mock_engine = Mock()
        mock_engine.id = 700
        mock_engine.name = "Test Engine"
        mock_engine.type = "generic"
        mock_engine.training_queues = []
        mock_engine.learning_enabled = True
        mock_engine.training_enabled = False

        mock_new_engine = Mock()
        mock_new_engine.id = 701

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.internal_client.create.return_value = {"id": 701}
        mock_client._deserializer.return_value = mock_new_engine

        mapping = IdMapping(source_org_id=1, target_org_id=2)

        result = CopyResult()
        workspace._copy_single_engine(mock_engine, mock_client, mapping, result)

        assert len(result.created) == 1
        assert mapping.get(ObjectType.ENGINE, 700) == 701

    def test_copy_single_engine_exception(self, workspace: Workspace):
        mock_engine = Mock()
        mock_engine.id = 700
        mock_engine.name = "Test Engine"
        mock_engine.type = "generic"
        mock_engine.training_queues = []
        mock_engine.learning_enabled = True
        mock_engine.training_enabled = False

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.internal_client.create.side_effect = Exception("API error")

        mapping = IdMapping(source_org_id=1, target_org_id=2)

        result = CopyResult()
        workspace._copy_single_engine(mock_engine, mock_client, mapping, result)

        assert len(result.failed) == 1

    def test_copy_single_inbox(self, workspace: Workspace):
        inbox = {
            "id": 800,
            "name": "Test Inbox",
            "queues": ["https://api.example.com/v1/queues/100"],
            "email_prefix": "test",
            "bounce_email_to": "bounce@example.com",
            "bounce_unprocessable_attachments": True,
        }

        mock_new_inbox = Mock()
        mock_new_inbox.id = 801

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.create_new_inbox.return_value = mock_new_inbox

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        result = CopyResult()
        workspace._copy_single_inbox(inbox, mock_client, mapping, result)

        assert len(result.created) == 1
        assert mapping.get(ObjectType.INBOX, 800) == 801

    def test_copy_single_inbox_no_target_queues(self, workspace: Workspace):
        inbox = {"id": 800, "name": "Test Inbox", "queues": ["https://api.example.com/v1/queues/999"]}

        mock_client = MagicMock()
        mapping = IdMapping(source_org_id=1, target_org_id=2)

        result = CopyResult()
        workspace._copy_single_inbox(inbox, mock_client, mapping, result)

        assert len(result.skipped) == 1
        assert "no target queues" in result.skipped[0][3]

    def test_copy_single_email_template(self, workspace: Workspace):
        mock_template = Mock()
        mock_template.id = 900
        mock_template.name = "Test Template"
        mock_template.queue = "https://api.example.com/v1/queues/100"
        mock_template.type = "export_annotation"
        mock_template.subject = "Subject"
        mock_template.message = "Message"

        mock_new_template = Mock()
        mock_new_template.id = 901

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.create_new_email_template.return_value = mock_new_template

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        result = CopyResult()
        workspace._copy_single_email_template(mock_template, mock_client, mapping, result)

        assert len(result.created) == 1
        assert mapping.get(ObjectType.EMAIL_TEMPLATE, 900) == 901

    def test_copy_single_email_template_no_source_queue(self, workspace: Workspace):
        mock_template = Mock()
        mock_template.id = 900
        mock_template.name = "Test Template"
        mock_template.queue = None

        mock_client = MagicMock()
        mapping = IdMapping(source_org_id=1, target_org_id=2)

        result = CopyResult()
        workspace._copy_single_email_template(mock_template, mock_client, mapping, result)

        assert len(result.skipped) == 1
        assert "no source queue" in result.skipped[0][3]

    def test_copy_single_email_template_no_target_queue(self, workspace: Workspace):
        mock_template = Mock()
        mock_template.id = 900
        mock_template.name = "Test Template"
        mock_template.queue = "https://api.example.com/v1/queues/999"

        mock_client = MagicMock()
        mapping = IdMapping(source_org_id=1, target_org_id=2)

        result = CopyResult()
        workspace._copy_single_email_template(mock_template, mock_client, mapping, result)

        assert len(result.skipped) == 1
        assert "no target queue" in result.skipped[0][3]

    def test_copy_single_rule(self, workspace: Workspace):
        mock_action = Mock()
        mock_action.id = "action1"
        mock_action.type = "set_value"
        mock_action.payload = {}
        mock_action.event = "field_changed"
        mock_action.enabled = True

        mock_rule = Mock()
        mock_rule.id = 1000
        mock_rule.name = "Test Rule"
        mock_rule.schema = "https://api.example.com/v1/schemas/50"
        mock_rule.trigger_condition = "True"
        mock_rule.actions = [mock_action]
        mock_rule.enabled = True

        mock_new_rule = Mock()
        mock_new_rule.id = 1001

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.create_new_rule.return_value = mock_new_rule

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.SCHEMA, 50, 60)

        result = CopyResult()
        workspace._copy_single_rule(mock_rule, mock_client, mapping, result)

        assert len(result.created) == 1
        assert mapping.get(ObjectType.RULE, 1000) == 1001

    def test_copy_single_rule_no_target_schema(self, workspace: Workspace):
        mock_rule = Mock()
        mock_rule.id = 1000
        mock_rule.name = "Test Rule"
        mock_rule.schema = "https://api.example.com/v1/schemas/999"

        mock_client = MagicMock()
        mapping = IdMapping(source_org_id=1, target_org_id=2)

        result = CopyResult()
        workspace._copy_single_rule(mock_rule, mock_client, mapping, result)

        assert len(result.skipped) == 1
        assert "no target schema" in result.skipped[0][3]


class TestCopyOrgMethod:
    """Tests for copy_org method."""

    def test_copy_org_creates_objects(self, workspace: Workspace):
        mock_workspace = Mock()
        mock_workspace.id = 100
        mock_workspace.name = "Test Workspace"
        mock_workspace.organization = "https://api.example.com/v1/organizations/123"
        mock_workspace.metadata = {}

        mock_queue = Mock()
        mock_queue.id = 200
        mock_queue.name = "Test Queue"
        mock_queue.workspace = "https://api.example.com/v1/workspaces/100"
        mock_queue.schema = "https://api.example.com/v1/schemas/300"

        mock_schema = Mock()
        mock_schema.id = 300
        mock_schema.name = "Test Schema"
        mock_schema.content = []

        mock_new_workspace = Mock()
        mock_new_workspace.id = 101

        mock_new_schema = Mock()
        mock_new_schema.id = 301

        mock_new_queue = Mock()
        mock_new_queue.id = 201

        with patch.object(workspace, "_client") as mock_client:
            mock_client.internal_client.base_url = "https://api.example.com/v1"
            mock_client.list_workspaces.return_value = [mock_workspace]
            mock_client.list_queues.return_value = [mock_queue]
            mock_client.retrieve_schema.return_value = mock_schema
            mock_client.list_hooks.return_value = []
            mock_client.create_new_workspace.return_value = mock_new_workspace
            mock_client.create_new_schema.return_value = mock_new_schema
            mock_client.create_new_queue.return_value = mock_new_queue

            result = workspace.copy_org(source_org_id=123, target_org_id=456)

        assert len(result.created) >= 3
        assert result.id_mapping is not None

    def test_copy_workspaces(self, workspace: Workspace):
        mock_ws = Mock()
        mock_ws.id = 100
        mock_ws.name = "Test Workspace"
        mock_ws.metadata = {}

        mock_new_ws = Mock()
        mock_new_ws.id = 101

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.create_new_workspace.return_value = mock_new_ws

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        result = CopyResult()

        workspace._copy_workspaces([mock_ws], mock_client, 2, mapping, result)

        assert len(result.created) == 1
        assert mapping.get(ObjectType.WORKSPACE, 100) == 101

    def test_copy_workspaces_exception(self, workspace: Workspace):
        mock_ws = Mock()
        mock_ws.id = 100
        mock_ws.name = "Test Workspace"
        mock_ws.metadata = {}

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.create_new_workspace.side_effect = Exception("API error")

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        result = CopyResult()

        workspace._copy_workspaces([mock_ws], mock_client, 2, mapping, result)

        assert len(result.failed) == 1

    def test_copy_queues_skips_unmapped_workspace(self, workspace: Workspace):
        mock_queue = Mock()
        mock_queue.id = 200
        mock_queue.name = "Test Queue"
        mock_queue.workspace = "https://api.example.com/v1/workspaces/999"
        mock_queue.schema = "https://api.example.com/v1/schemas/300"

        mock_client = MagicMock()
        mapping = IdMapping(source_org_id=1, target_org_id=2)

        result = CopyResult()
        workspace._copy_queues([(mock_queue, 999)], mock_client, mock_client, mapping, result)

        assert len(result.skipped) == 1
        assert "workspace not copied" in result.skipped[0][3]

    def test_copy_queues_exception(self, workspace: Workspace):
        mock_queue = Mock()
        mock_queue.id = 200
        mock_queue.name = "Test Queue"
        mock_queue.workspace = "https://api.example.com/v1/workspaces/100"
        mock_queue.schema = "https://api.example.com/v1/schemas/300"

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.retrieve_schema.side_effect = Exception("API error")

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.WORKSPACE, 100, 101)

        result = CopyResult()
        workspace._copy_queues([(mock_queue, 100)], mock_client, mock_client, mapping, result)

        assert len(result.failed) == 1


class TestDeployMethod:
    """Extended tests for deploy method."""

    def test_deploy_requires_source_org_id(self, workspace: Workspace):
        workspace._config = WorkspaceConfig(api_base="https://api.example.com/v1", org_id=None)

        with pytest.raises(ValueError, match="No source org_id"):
            workspace.deploy(target_org_id=456)

    def test_deploy_actual_push(self, workspace: Workspace):
        workspace._config = WorkspaceConfig(api_base="https://api.example.com/v1", org_id=123)

        mapping = IdMapping(source_org_id=123, target_org_id=456)
        mapping.add(ObjectType.QUEUE, 100, 200)
        workspace._save_id_mapping(mapping)

        workspace._save_object(ObjectType.QUEUE, 100, "Test Queue", {"id": 100, "name": "Test Queue"})

        with patch.object(workspace, "_client") as mock_client:
            mock_client.internal_client.base_url = "https://api.example.com/v1"
            mock_client.internal_client.update = MagicMock()

            result = workspace.deploy(target_org_id=456, dry_run=False)

        assert len(result.updated) == 1

    def test_deploy_with_exception(self, workspace: Workspace):
        workspace._config = WorkspaceConfig(api_base="https://api.example.com/v1", org_id=123)

        mapping = IdMapping(source_org_id=123, target_org_id=456)
        mapping.add(ObjectType.QUEUE, 100, 200)
        workspace._save_id_mapping(mapping)

        workspace._save_object(ObjectType.QUEUE, 100, "Test Queue", {"id": 100, "name": "Test Queue"})

        with patch.object(workspace, "_client") as mock_client:
            mock_client.internal_client.base_url = "https://api.example.com/v1"

        with (
            patch.object(workspace, "_client") as mock_client,
            patch.object(workspace, "_push_object") as mock_push,
        ):
            mock_client.internal_client.base_url = "https://api.example.com/v1"
            mock_push.side_effect = Exception("Push failed")

            result = workspace.deploy(target_org_id=456, dry_run=False)

        assert len(result.failed) == 1

    def test_deploy_with_separate_target_credentials(self, workspace: Workspace):
        workspace._config = WorkspaceConfig(api_base="https://api.example.com/v1", org_id=123)

        mapping = IdMapping(source_org_id=123, target_org_id=456)
        mapping.add(ObjectType.QUEUE, 100, 200)
        workspace._save_id_mapping(mapping)

        workspace._save_object(ObjectType.QUEUE, 100, "Test Queue", {"id": 100, "name": "Test Queue"})

        with patch("rossum_deploy.workspace.SyncRossumAPIClient") as MockClient:
            mock_target_client = MagicMock()
            mock_target_client.internal_client.base_url = "https://api.target.com/v1"
            MockClient.return_value = mock_target_client

            result = workspace.deploy(
                target_org_id=456,
                target_api_base="https://api.target.com/v1",
                target_token="target-token",
                dry_run=True,
            )

        assert len(result.updated) == 1


class TestPullMethods2:
    """Additional tests for pull methods."""

    def test_collect_engine_urls_from_queues(self, workspace: Workspace):
        mock_queue1 = Mock()
        mock_queue1.url = "https://api.example.com/v1/queues/100"
        mock_queue1.dedicated_engine = "https://api.example.com/v1/engines/10"
        mock_queue1.generic_engine = None

        mock_queue2 = Mock()
        mock_queue2.url = "https://api.example.com/v1/queues/200"
        mock_queue2.dedicated_engine = None
        mock_queue2.generic_engine = {"url": "https://api.example.com/v1/engines/20"}

        mock_queue3 = Mock()
        mock_queue3.url = "https://api.example.com/v1/queues/300"
        mock_queue3.dedicated_engine = None
        mock_queue3.generic_engine = None

        with patch.object(workspace, "_client") as mock_client:
            mock_client.list_queues.return_value = [mock_queue1, mock_queue2, mock_queue3]

            queue_urls = {"https://api.example.com/v1/queues/100", "https://api.example.com/v1/queues/200"}
            engine_urls = workspace._collect_engine_urls_from_queues(mock_client, queue_urls)

        assert "https://api.example.com/v1/engines/10" in engine_urls
        assert "https://api.example.com/v1/engines/20" in engine_urls

    def test_collect_engine_urls_dedicated_engine_as_dict(self, workspace: Workspace):
        mock_queue = Mock()
        mock_queue.url = "https://api.example.com/v1/queues/100"
        mock_queue.dedicated_engine = {"url": "https://api.example.com/v1/engines/10"}
        mock_queue.generic_engine = None

        with patch.object(workspace, "_client") as mock_client:
            mock_client.list_queues.return_value = [mock_queue]

            queue_urls = {"https://api.example.com/v1/queues/100"}
            engine_urls = workspace._collect_engine_urls_from_queues(mock_client, queue_urls)

        assert "https://api.example.com/v1/engines/10" in engine_urls


class TestCompareWorkspacesError:
    """Test compare_workspaces error conditions."""

    def test_compare_workspaces_missing_workspace(self, tmp_workspace: Path):
        source_path = tmp_workspace / "source"
        target_path = tmp_workspace / "target"

        source_ws = Workspace(source_path, api_base="https://api.example.com/v1", token="test-token")
        target_ws = Workspace(target_path, api_base="https://api.example.com/v1", token="test-token")

        with pytest.raises(ValueError, match="Both source and target must have workspace objects pulled"):
            target_ws.compare_workspaces(source_ws)


class TestFetchRemoteObject:
    """Tests for _fetch_remote_object method."""

    def test_fetch_remote_object_queue(self, workspace: Workspace):
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.modified_at = None

        with patch.object(workspace, "_client") as mock_client:
            mock_client.retrieve_queue.return_value = mock_queue
            with patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict:
                mock_asdict.return_value = {"id": 100, "name": "Test Queue"}
                data, modified = workspace._fetch_remote_object(mock_client, ObjectType.QUEUE, 100)

        assert data["id"] == 100
        assert modified is None


class TestPushObject:
    """Tests for _push_object method."""

    def test_push_object(self, workspace: Workspace):
        mock_client = MagicMock()

        data = {"id": 100, "name": "Test Queue"}
        workspace._push_object(mock_client, ObjectType.QUEUE, 100, data)

        mock_client.internal_client.update.assert_called_once()


class TestCopyConnectorsAndInboxes:
    """Tests for copy connectors and inboxes iteration methods."""

    def test_copy_connectors(self, workspace: Workspace):
        mock_connector = Mock()
        mock_connector.id = 600
        mock_connector.name = "Test Connector"
        mock_connector.queues = ["https://api.example.com/v1/queues/100"]
        mock_connector.service_url = "https://service.example.com"
        mock_connector.authorization_token = "token"
        mock_connector.params = ""
        mock_connector.asynchronous = False

        mock_new_connector = Mock()
        mock_new_connector.id = 601

        source_queue_urls = {"https://api.example.com/v1/queues/100"}

        with patch.object(workspace, "_client") as mock_source_client:
            mock_source_client.list_connectors.return_value = [mock_connector]

            mock_target_client = MagicMock()
            mock_target_client.internal_client.base_url = "https://api.example.com/v1"
            mock_target_client.create_new_connector.return_value = mock_new_connector

            mapping = IdMapping(source_org_id=1, target_org_id=2)
            mapping.add(ObjectType.QUEUE, 100, 200)
            result = CopyResult()

            workspace._copy_connectors(mock_source_client, mock_target_client, source_queue_urls, mapping, result)

        assert len(result.created) == 1

    def test_copy_inboxes(self, workspace: Workspace):
        inbox = {
            "id": 800,
            "name": "Test Inbox",
            "queues": ["https://api.example.com/v1/queues/100"],
            "email_prefix": "test",
        }

        mock_new_inbox = Mock()
        mock_new_inbox.id = 801

        source_queue_urls = {"https://api.example.com/v1/queues/100"}

        with patch.object(workspace, "_client") as mock_source_client:
            mock_source_client.request_paginated.return_value = [inbox]

            mock_target_client = MagicMock()
            mock_target_client.internal_client.base_url = "https://api.example.com/v1"
            mock_target_client.create_new_inbox.return_value = mock_new_inbox

            mapping = IdMapping(source_org_id=1, target_org_id=2)
            mapping.add(ObjectType.QUEUE, 100, 200)
            result = CopyResult()

            workspace._copy_inboxes(mock_source_client, mock_target_client, source_queue_urls, mapping, result)

        assert len(result.created) == 1

    def test_copy_email_templates(self, workspace: Workspace):
        mock_template = Mock()
        mock_template.id = 900
        mock_template.name = "Test Template"
        mock_template.queue = "https://api.example.com/v1/queues/100"
        mock_template.type = "export"
        mock_template.subject = "Subject"
        mock_template.message = "Message"

        mock_new_template = Mock()
        mock_new_template.id = 901

        source_queue_urls = {"https://api.example.com/v1/queues/100"}

        with patch.object(workspace, "_client") as mock_source_client:
            mock_source_client.list_email_templates.return_value = [mock_template]

            mock_target_client = MagicMock()
            mock_target_client.internal_client.base_url = "https://api.example.com/v1"
            mock_target_client.create_new_email_template.return_value = mock_new_template

            mapping = IdMapping(source_org_id=1, target_org_id=2)
            mapping.add(ObjectType.QUEUE, 100, 200)
            result = CopyResult()

            workspace._copy_email_templates(mock_source_client, mock_target_client, source_queue_urls, mapping, result)

        assert len(result.created) == 1

    def test_copy_rules(self, workspace: Workspace):
        mock_action = Mock()
        mock_action.id = "action1"
        mock_action.type = "set_value"
        mock_action.payload = {}
        mock_action.event = "field_changed"
        mock_action.enabled = True

        mock_rule = Mock()
        mock_rule.id = 1000
        mock_rule.name = "Test Rule"
        mock_rule.schema = "https://api.example.com/v1/schemas/50"
        mock_rule.trigger_condition = "True"
        mock_rule.actions = [mock_action]
        mock_rule.enabled = True

        mock_new_rule = Mock()
        mock_new_rule.id = 1001

        source_schema_urls = {"https://api.example.com/v1/schemas/50"}

        with patch.object(workspace, "_client") as mock_source_client:
            mock_source_client.list_rules.return_value = [mock_rule]

            mock_target_client = MagicMock()
            mock_target_client.internal_client.base_url = "https://api.example.com/v1"
            mock_target_client.create_new_rule.return_value = mock_new_rule

            mapping = IdMapping(source_org_id=1, target_org_id=2)
            mapping.add(ObjectType.SCHEMA, 50, 60)
            result = CopyResult()

            workspace._copy_rules(mock_source_client, mock_target_client, source_schema_urls, mapping, result)

        assert len(result.created) == 1


class TestDeployEdgeCases:
    """Additional edge case tests for the deploy() method."""

    def test_deploy_raises_without_org_id(self, workspace: Workspace):
        """deploy() should raise if org_id is not configured (pull not run)."""
        with pytest.raises(ValueError, match="No source org_id configured"):
            workspace.deploy(target_org_id=789012)

    def test_deploy_multiple_types_dry_run(self, workspace: Workspace):
        """deploy() with dry_run=True should handle multiple object types."""
        workspace._config.org_id = 123456

        workspace._save_object(ObjectType.QUEUE, 100, "Test Queue", {"id": 100, "name": "Test Queue"})
        workspace._save_object(ObjectType.SCHEMA, 200, "Test Schema", {"id": 200, "name": "Test Schema"})

        mapping = IdMapping(source_org_id=123456, target_org_id=789012)
        mapping.add(ObjectType.QUEUE, 100, 500)
        mapping.add(ObjectType.SCHEMA, 200, 600)

        result = workspace.deploy(target_org_id=789012, id_mapping=mapping, dry_run=True)

        assert len(result.updated) == 2
        assert len(result.skipped) == 0
        assert len(result.failed) == 0
        updated_types = {obj_type for obj_type, _, _ in result.updated}
        assert ObjectType.QUEUE in updated_types
        assert ObjectType.SCHEMA in updated_types

    def test_deploy_skips_objects_without_mapping(self, workspace: Workspace):
        """deploy() should skip objects that have no mapping."""
        workspace._config.org_id = 123456

        workspace._save_object(ObjectType.QUEUE, 100, "Mapped Queue", {"id": 100, "name": "Mapped Queue"})
        workspace._save_object(ObjectType.QUEUE, 101, "Unmapped Queue", {"id": 101, "name": "Unmapped Queue"})

        mapping = IdMapping(source_org_id=123456, target_org_id=789012)
        mapping.add(ObjectType.QUEUE, 100, 500)

        result = workspace.deploy(target_org_id=789012, id_mapping=mapping, dry_run=True)

        assert len(result.updated) == 1
        assert len(result.skipped) == 1
        assert result.skipped[0][1] == 101
        assert "no target mapping" in result.skipped[0][3]

    def test_deploy_handles_api_error(self, workspace: Workspace):
        """deploy() should record failed objects when API calls fail."""
        workspace._config.org_id = 123456

        workspace._save_object(ObjectType.QUEUE, 100, "Test Queue", {"id": 100, "name": "Test Queue"})

        mapping = IdMapping(source_org_id=123456, target_org_id=789012)
        mapping.add(ObjectType.QUEUE, 100, 500)

        with patch.object(workspace, "_client") as mock_client:
            mock_client.internal_client.base_url = "https://api.example.com/v1"
            mock_client.internal_client.update.side_effect = Exception("API error")

            result = workspace.deploy(target_org_id=789012, id_mapping=mapping, dry_run=False)

            assert len(result.failed) == 1
            assert "API error" in result.failed[0][3]


class TestPrepareDeployData:
    """Tests for _prepare_deploy_data helper."""

    def test_remap_queue_schema_and_workspace(self, workspace: Workspace):
        """_prepare_deploy_data should remap schema and workspace references."""
        data = {
            "id": 100,
            "name": "Test Queue",
            "schema": "https://api.example.com/v1/schemas/200",
            "workspace": "https://api.example.com/v1/workspaces/10",
        }

        mapping = IdMapping(source_org_id=123456, target_org_id=789012)
        mapping.add(ObjectType.SCHEMA, 200, 600)
        mapping.add(ObjectType.WORKSPACE, 10, 20)

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.target.com/v1"

        result = workspace._prepare_deploy_data(data, ObjectType.QUEUE, mapping, mock_client)

        assert result["schema"] == "https://api.target.com/v1/schemas/600"
        assert result["workspace"] == "https://api.target.com/v1/workspaces/20"

    def test_remap_hook_queues(self, workspace: Workspace):
        """_prepare_deploy_data should remap hook queue references."""
        data = {
            "id": 300,
            "name": "Test Hook",
            "queues": ["https://api.example.com/v1/queues/100", "https://api.example.com/v1/queues/101"],
            "config": {"code": "pass"},
        }

        mapping = IdMapping(source_org_id=123456, target_org_id=789012)
        mapping.add(ObjectType.QUEUE, 100, 500)
        mapping.add(ObjectType.QUEUE, 101, 501)

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.target.com/v1"

        result = workspace._prepare_deploy_data(data, ObjectType.HOOK, mapping, mock_client)

        assert len(result["queues"]) == 2
        assert "https://api.target.com/v1/queues/500" in result["queues"]
        assert "https://api.target.com/v1/queues/501" in result["queues"]
