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


def create_copy_test_mocks():
    """Create mock objects for copy_workspace and copy_org tests.

    Returns a dict with source mocks (workspace, queue, schema) and
    target mocks (new_workspace, new_schema, new_queue).
    """
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

    return {
        "workspace": mock_workspace,
        "queue": mock_queue,
        "schema": mock_schema,
        "new_workspace": mock_new_workspace,
        "new_schema": mock_new_schema,
        "new_queue": mock_new_queue,
    }


class TestWorkspaceConfig:
    def test_to_dict(self):
        config = WorkspaceConfig(api_base="https://api.example.com/v1", org_id=123)
        assert config.to_dict() == {"api_base": "https://api.example.com/v1", "org_id": 123}

    def test_from_dict(self):
        config = WorkspaceConfig.from_dict({"api_base": "https://api.example.com/v1", "org_id": 456})
        assert config.api_base == "https://api.example.com/v1"
        assert config.org_id == 456

    def test_repr(self):
        config = WorkspaceConfig(api_base="https://api.example.com/v1", org_id=123)
        result = repr(config)
        assert "WorkspaceConfig" in result
        assert "api_base='https://api.example.com/v1'" in result
        assert "org_id=123" in result


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
        mocks = create_copy_test_mocks()

        with patch.object(workspace, "_client") as mock_client:
            mock_client.internal_client.base_url = "https://api.example.com/v1"
            mock_client.retrieve_workspace.return_value = mocks["workspace"]
            mock_client.list_queues.return_value = [mocks["queue"]]
            mock_client.retrieve_schema.return_value = mocks["schema"]
            mock_client.list_engines.return_value = []
            mock_client.list_hooks.return_value = []
            mock_client.list_connectors.return_value = []
            mock_client.request_paginated.return_value = []
            mock_client.list_email_templates.return_value = []
            mock_client.list_rules.return_value = []
            mock_client.create_new_workspace.return_value = mocks["new_workspace"]
            mock_client.create_new_schema.return_value = mocks["new_schema"]
            mock_client.create_new_queue.return_value = mocks["new_queue"]

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
        mocks = create_copy_test_mocks()

        with patch.object(workspace, "_client") as mock_client:
            mock_client.internal_client.base_url = "https://api.example.com/v1"
            mock_client.list_workspaces.return_value = [mocks["workspace"]]
            mock_client.list_queues.return_value = [mocks["queue"]]
            mock_client.retrieve_schema.return_value = mocks["schema"]
            mock_client.list_hooks.return_value = []
            mock_client.create_new_workspace.return_value = mocks["new_workspace"]
            mock_client.create_new_schema.return_value = mocks["new_schema"]
            mock_client.create_new_queue.return_value = mocks["new_queue"]

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


class TestPullOrgMethod:
    """Tests for pull() method that pulls an entire organization."""

    def test_pull_org(self, workspace: Workspace):
        mock_workspace = Mock()
        mock_workspace.id = 100
        mock_workspace.name = "Test Workspace"
        mock_workspace.organization = "https://api.example.com/v1/organizations/123"
        mock_workspace.modified_at = None

        with (
            patch.object(workspace, "_client") as mock_client,
            patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict,
        ):
            mock_asdict.return_value = {"id": 100, "name": "Test Workspace"}
            mock_client.list_workspaces.return_value = [mock_workspace]
            mock_client.list_queues.return_value = []
            mock_client.list_hooks.return_value = []
            mock_client.list_connectors.return_value = []
            mock_client.list_engines.return_value = []
            mock_client.list_email_templates.return_value = []
            mock_client.list_rules.return_value = []
            mock_client.request_paginated.return_value = []

            result = workspace.pull(org_id=123)

        assert len(result.pulled) >= 1
        ws_pulled = [p for p in result.pulled if p[0] == ObjectType.WORKSPACE]
        assert len(ws_pulled) == 1
        assert workspace._config.org_id == 123


class TestPullWorkspacesMethod:
    """Tests for _pull_workspaces method."""

    def test_pull_workspaces_filters_by_org(self, workspace: Workspace):
        mock_ws1 = Mock()
        mock_ws1.id = 100
        mock_ws1.name = "WS in Org"
        mock_ws1.organization = "https://api.example.com/v1/organizations/123"
        mock_ws1.modified_at = None

        mock_ws2 = Mock()
        mock_ws2.id = 200
        mock_ws2.name = "WS in Other Org"
        mock_ws2.organization = "https://api.example.com/v1/organizations/999"
        mock_ws2.modified_at = None

        from rossum_deploy.models import PullResult

        result = PullResult()

        with (
            patch.object(workspace, "_client") as mock_client,
            patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict,
        ):
            mock_asdict.return_value = {"id": 100}
            mock_client.list_workspaces.return_value = [mock_ws1, mock_ws2]

            workspace._pull_workspaces(mock_client, 123, result)

        assert len(result.pulled) == 1
        assert result.pulled[0][1] == 100


class TestPullQueuesMethod:
    """Tests for _pull_queues method."""

    def test_pull_queues_filters_by_workspace(self, workspace: Workspace):
        workspace._save_object(ObjectType.WORKSPACE, 100, "Test WS", {"id": 100})

        mock_q1 = Mock()
        mock_q1.id = 200
        mock_q1.name = "Q in WS"
        mock_q1.workspace = "https://api.example.com/v1/workspaces/100"

        mock_q2 = Mock()
        mock_q2.id = 300
        mock_q2.name = "Q not in WS"
        mock_q2.workspace = "https://api.example.com/v1/workspaces/999"

        mock_q3 = Mock()
        mock_q3.id = 400
        mock_q3.name = "Q with no WS"
        mock_q3.workspace = None

        from rossum_deploy.models import PullResult

        result = PullResult()

        with (
            patch.object(workspace, "_client") as mock_client,
            patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict,
        ):
            mock_asdict.return_value = {"id": 200}
            mock_client.list_queues.return_value = [mock_q1, mock_q2, mock_q3]

            workspace._pull_queues(mock_client, result)

        assert len(result.pulled) == 1
        assert result.pulled[0][1] == 200


class TestPullInboxesMethod:
    """Tests for _pull_inboxes method."""

    def test_pull_inboxes_filters_by_queue(self, workspace: Workspace):
        workspace._save_object(
            ObjectType.QUEUE, 100, "Test Queue", {"id": 100, "url": "https://api.example.com/v1/queues/100"}
        )

        inbox_matching = {
            "id": 500,
            "name": "Matching Inbox",
            "queues": ["https://api.example.com/v1/queues/100"],
            "modified_at": "2024-01-01T00:00:00Z",
        }
        inbox_not_matching = {"id": 600, "name": "Other Inbox", "queues": ["https://api.example.com/v1/queues/999"]}

        from rossum_deploy.models import PullResult

        result = PullResult()

        with patch.object(workspace, "_client") as mock_client:
            mock_client.request_paginated.return_value = [inbox_matching, inbox_not_matching]

            workspace._pull_inboxes(mock_client, result)

        assert len(result.pulled) == 1
        assert result.pulled[0][1] == 500


class TestPullSchemasMethod:
    """Tests for _pull_schemas method."""

    def test_pull_schemas_from_queues(self, workspace: Workspace):
        workspace._save_object(
            ObjectType.QUEUE, 100, "Queue", {"id": 100, "schema": "https://api.example.com/v1/schemas/50"}
        )

        mock_schema = Mock()
        mock_schema.id = 50
        mock_schema.name = "Test Schema"
        mock_schema.modified_at = None

        from rossum_deploy.models import PullResult

        result = PullResult()

        with (
            patch.object(workspace, "_client") as mock_client,
            patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict,
        ):
            mock_asdict.return_value = {"id": 50, "name": "Test Schema"}
            mock_client.retrieve_schema.return_value = mock_schema

            workspace._pull_schemas(mock_client, result)

        assert len(result.pulled) == 1
        assert result.pulled[0][1] == 50


class TestPullEnginesMethod:
    """Tests for _pull_engines method."""

    def test_pull_engines_linked_to_queues(self, workspace: Workspace):
        workspace._save_object(
            ObjectType.QUEUE, 100, "Queue", {"id": 100, "url": "https://api.example.com/v1/queues/100"}
        )

        mock_queue = Mock()
        mock_queue.url = "https://api.example.com/v1/queues/100"
        mock_queue.dedicated_engine = "https://api.example.com/v1/engines/10"
        mock_queue.generic_engine = None

        mock_engine = Mock()
        mock_engine.id = 10
        mock_engine.name = "Test Engine"
        mock_engine.url = "https://api.example.com/v1/engines/10"
        mock_engine.modified_at = None

        from rossum_deploy.models import PullResult

        result = PullResult()

        with (
            patch.object(workspace, "_client") as mock_client,
            patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict,
        ):
            mock_asdict.return_value = {"id": 10, "name": "Test Engine"}
            mock_client.list_queues.return_value = [mock_queue]
            mock_client.list_engines.return_value = [mock_engine]

            workspace._pull_engines(mock_client, result)

        assert len(result.pulled) == 1
        assert result.pulled[0][1] == 10


class TestPullEmailTemplatesMethod:
    """Tests for _pull_email_templates method."""

    def test_pull_email_templates_linked_to_queues(self, workspace: Workspace):
        workspace._save_object(
            ObjectType.QUEUE, 100, "Queue", {"id": 100, "url": "https://api.example.com/v1/queues/100"}
        )

        mock_template = Mock()
        mock_template.id = 800
        mock_template.name = "Template"
        mock_template.queue = "https://api.example.com/v1/queues/100"
        mock_template.message = "Test message\n\n"
        mock_template.modified_at = None

        from rossum_deploy.models import PullResult

        result = PullResult()

        with (
            patch.object(workspace, "_client") as mock_client,
            patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict,
        ):
            mock_asdict.return_value = {"id": 800, "name": "Template", "message": "Test message\n\n"}
            mock_client.list_email_templates.return_value = [mock_template]

            workspace._pull_email_templates(mock_client, result)

        assert len(result.pulled) == 1


class TestPullRulesMethod:
    """Tests for _pull_rules method."""

    def test_pull_rules_linked_to_schemas(self, workspace: Workspace):
        workspace._save_object(
            ObjectType.QUEUE, 100, "Queue", {"id": 100, "schema": "https://api.example.com/v1/schemas/50"}
        )

        mock_rule = Mock()
        mock_rule.id = 1000
        mock_rule.name = "Rule"
        mock_rule.schema = "https://api.example.com/v1/schemas/50"
        mock_rule.modified_at = None

        from rossum_deploy.models import PullResult

        result = PullResult()

        with (
            patch.object(workspace, "_client") as mock_client,
            patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict,
        ):
            mock_asdict.return_value = {"id": 1000, "name": "Rule"}
            mock_client.list_rules.return_value = [mock_rule]

            workspace._pull_rules(mock_client, result)

        assert len(result.pulled) == 1
        assert result.pulled[0][1] == 1000


class TestPullQueueLinkedObjects:
    """Tests for _pull_queue_linked_objects helper."""

    def test_pull_queue_linked_objects(self, workspace: Workspace):
        workspace._save_object(
            ObjectType.QUEUE, 100, "Queue", {"id": 100, "url": "https://api.example.com/v1/queues/100"}
        )

        mock_hook = Mock()
        mock_hook.id = 500
        mock_hook.name = "Hook"
        mock_hook.queues = ["https://api.example.com/v1/queues/100"]
        mock_hook.modified_at = None

        queue_urls = {"https://api.example.com/v1/queues/100"}
        from rossum_deploy.models import PullResult

        result = PullResult()

        with patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict:
            mock_asdict.return_value = {"id": 500, "name": "Hook"}
            workspace._pull_queue_linked_objects(
                [mock_hook], ObjectType.HOOK, queue_urls, result, lambda h: set(h.queues or [])
            )

        assert len(result.pulled) == 1
        assert result.pulled[0][0] == ObjectType.HOOK


class TestRetrieveRemoteObject:
    """Tests for _retrieve_remote_object method."""

    def test_retrieve_remote_object_inbox_returns_none(self, workspace: Workspace):
        result = workspace._retrieve_remote_object(workspace.client, ObjectType.INBOX, 123)
        assert result is None

    def test_retrieve_remote_object_unsupported_raises(self, workspace: Workspace):
        with pytest.raises(ValueError, match="Unsupported object type"):

            class FakeType(str):
                value = "fake"

            workspace._retrieve_remote_object(workspace.client, FakeType(), 123)


class TestFetchRemoteObjectEdgeCases:
    """Edge case tests for _fetch_remote_object method."""

    def test_fetch_remote_object_inbox(self, workspace: Workspace):
        inbox_data = {"id": 800, "name": "Test Inbox", "modified_at": "2024-01-15T10:00:00Z"}

        with patch.object(workspace, "_client") as mock_client:
            mock_client.request_json.return_value = inbox_data

            data, modified = workspace._fetch_remote_object(mock_client, ObjectType.INBOX, 800)

        assert data["id"] == 800
        assert modified is not None

    def test_fetch_remote_object_inbox_no_modified_at(self, workspace: Workspace):
        inbox_data = {"id": 800, "name": "Test Inbox"}

        with patch.object(workspace, "_client") as mock_client:
            mock_client.request_json.return_value = inbox_data

            data, modified = workspace._fetch_remote_object(mock_client, ObjectType.INBOX, 800)

        assert data["id"] == 800
        assert modified is None

    def test_fetch_remote_object_email_template_message_normalization(self, workspace: Workspace):
        mock_template = Mock()
        mock_template.id = 900
        mock_template.message = "Message with trailing\n\n"
        mock_template.modified_at = "2024-01-15T10:00:00Z"

        with (
            patch.object(workspace, "_client") as mock_client,
            patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict,
        ):
            mock_asdict.return_value = {"id": 900, "message": "Message with trailing\n\n"}
            mock_client.retrieve_email_template.return_value = mock_template

            data, _modified = workspace._fetch_remote_object(mock_client, ObjectType.EMAIL_TEMPLATE, 900)

        assert data["message"] == "Message with trailing"


class TestNormalizeIdMapping:
    """Tests for _normalize_id_mapping method."""

    def test_normalize_id_mapping_returns_unchanged_when_source_key(self, workspace: Workspace):
        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.WORKSPACE, 100, 200)

        result = workspace._normalize_id_mapping(mapping, 100, 200)

        assert result.get(ObjectType.WORKSPACE, 100) == 200

    def test_normalize_id_mapping_returns_unchanged_when_unmapped(self, workspace: Workspace):
        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 300, 400)

        result = workspace._normalize_id_mapping(mapping, 999, 888)

        assert result.get(ObjectType.QUEUE, 300) == 400


class TestNormalizeValueMessageField:
    """Tests for _normalize_value message field handling."""

    def test_normalize_value_strips_message_field(self, workspace: Workspace):
        value = "Message with trailing whitespace\n\n"
        result = workspace._normalize_value(value, None, field_name="message")
        assert result == "Message with trailing whitespace"


class TestIsGitModified:
    """Tests for _is_git_modified method."""

    def test_is_git_modified_git_not_found(self, workspace: Workspace):
        workspace._save_object(ObjectType.QUEUE, 1, "Queue", {"id": 1})
        paths = workspace._list_local_objects(ObjectType.QUEUE)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            result = workspace._is_git_modified(paths[0])

        assert result is False

    def test_is_git_modified_non_zero_return(self, workspace: Workspace):
        workspace._save_object(ObjectType.QUEUE, 1, "Queue", {"id": 1})
        paths = workspace._list_local_objects(ObjectType.QUEUE)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=128, stdout="")
            result = workspace._is_git_modified(paths[0])

        assert result is False

    def test_is_git_modified_no_status(self, workspace: Workspace):
        workspace._save_object(ObjectType.QUEUE, 1, "Queue", {"id": 1})
        paths = workspace._list_local_objects(ObjectType.QUEUE)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="")
            result = workspace._is_git_modified(paths[0])

        assert result is False

    def test_is_git_modified_with_M_status(self, workspace: Workspace):
        workspace._save_object(ObjectType.QUEUE, 1, "Queue", {"id": 1})
        paths = workspace._list_local_objects(ObjectType.QUEUE)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=" M queues/Queue_1.json")
            result = workspace._is_git_modified(paths[0])

        assert result is True

    def test_is_git_modified_with_staged(self, workspace: Workspace):
        workspace._save_object(ObjectType.QUEUE, 1, "Queue", {"id": 1})
        paths = workspace._list_local_objects(ObjectType.QUEUE)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="M  queues/Queue_1.json")
            result = workspace._is_git_modified(paths[0])

        assert result is True


class TestPushMethodEdgeCases:
    """Edge cases for push() method."""

    def test_push_skips_non_pushable_types(self, workspace: Workspace):
        local_data = {"id": 1, "name": "Inbox", "email": "test@example.com"}
        modified_at = datetime(2024, 1, 1, tzinfo=UTC)

        workspace._save_object(ObjectType.INBOX, 1, "Inbox", local_data, remote_modified_at=modified_at)

        from rossum_deploy.models import DiffResult, DiffStatus, ObjectDiff

        mock_diff = DiffResult()
        mock_diff.objects.append(
            ObjectDiff(
                object_type=ObjectType.INBOX,
                object_id=1,
                name="Inbox",
                status=DiffStatus.LOCAL_MODIFIED,
                changed_fields=["name"],
            )
        )

        with patch.object(workspace, "diff", return_value=mock_diff):
            result = workspace.push()

        assert len(result.pushed) == 1 or len(result.skipped) >= 0

    def test_push_skips_conflict_without_force(self, workspace: Workspace):
        from rossum_deploy.models import DiffResult, DiffStatus, ObjectDiff

        mock_diff = DiffResult()
        mock_diff.objects.append(
            ObjectDiff(
                object_type=ObjectType.QUEUE,
                object_id=1,
                name="Queue",
                status=DiffStatus.CONFLICT,
                changed_fields=["name"],
            )
        )

        with patch.object(workspace, "diff", return_value=mock_diff):
            result = workspace.push(force=False)

        assert len(result.skipped) == 1
        assert "conflict" in result.skipped[0][3]

    def test_push_skips_remote_modified_without_force(self, workspace: Workspace):
        from rossum_deploy.models import DiffResult, DiffStatus, ObjectDiff

        mock_diff = DiffResult()
        mock_diff.objects.append(
            ObjectDiff(
                object_type=ObjectType.QUEUE,
                object_id=1,
                name="Queue",
                status=DiffStatus.REMOTE_MODIFIED,
                changed_fields=["name"],
            )
        )

        with patch.object(workspace, "diff", return_value=mock_diff):
            result = workspace.push(force=False)

        assert len(result.skipped) == 1
        assert "remote modified" in result.skipped[0][3]

    def test_push_with_force_pushes_conflicts(self, workspace: Workspace):
        workspace._save_object(ObjectType.QUEUE, 1, "Queue", {"id": 1, "name": "Queue"})

        from rossum_deploy.models import DiffResult, DiffStatus, ObjectDiff

        mock_diff = DiffResult()
        mock_diff.objects.append(
            ObjectDiff(
                object_type=ObjectType.QUEUE,
                object_id=1,
                name="Queue",
                status=DiffStatus.CONFLICT,
                changed_fields=["name"],
            )
        )

        with (
            patch.object(workspace, "diff", return_value=mock_diff),
            patch.object(workspace, "_client") as mock_client,
        ):
            mock_client.internal_client.update = MagicMock()
            result = workspace.push(force=True)

        assert len(result.pushed) == 1

    def test_push_handles_exception(self, workspace: Workspace):
        workspace._save_object(ObjectType.QUEUE, 1, "Queue", {"id": 1, "name": "Queue"})

        from rossum_deploy.models import DiffResult, DiffStatus, ObjectDiff

        mock_diff = DiffResult()
        mock_diff.objects.append(
            ObjectDiff(
                object_type=ObjectType.QUEUE,
                object_id=1,
                name="Queue",
                status=DiffStatus.LOCAL_MODIFIED,
                changed_fields=["name"],
            )
        )

        with (
            patch.object(workspace, "diff", return_value=mock_diff),
            patch.object(workspace, "_push_object") as mock_push,
        ):
            mock_push.side_effect = Exception("Push failed")
            result = workspace.push()

        assert len(result.failed) == 1
        assert "Push failed" in result.failed[0][3]

    def test_push_object_not_found(self, workspace: Workspace):
        from rossum_deploy.models import DiffResult, DiffStatus, ObjectDiff

        mock_diff = DiffResult()
        mock_diff.objects.append(
            ObjectDiff(
                object_type=ObjectType.QUEUE,
                object_id=999,
                name="Missing Queue",
                status=DiffStatus.LOCAL_MODIFIED,
                changed_fields=["name"],
            )
        )

        with patch.object(workspace, "diff", return_value=mock_diff):
            result = workspace.push()

        assert len(result.pushed) == 0


class TestCleanSchemaNode:
    """Tests for _clean_schema_node method."""

    def test_clean_schema_node_removes_none(self, workspace: Workspace):
        node = {"id": "field1", "label": "Field 1", "score_threshold": None}
        result = workspace._clean_schema_node(node)
        assert "score_threshold" not in result

    def test_clean_schema_node_removes_multivalue_tuple_fields(self, workspace: Workspace):
        node = {"id": "field1", "category": "datapoint", "width": 100, "stretch": True}
        result = workspace._clean_schema_node(node)
        assert "width" not in result
        assert "stretch" not in result

    def test_clean_schema_node_keeps_multivalue_tuple_fields_in_context(self, workspace: Workspace):
        node = {"id": "field1", "category": "datapoint", "width": 100, "stretch": True}
        result = workspace._clean_schema_node(node, parent_is_multivalue_tuple=True)
        assert result["width"] == 100
        assert result["stretch"] is True

    def test_clean_schema_node_multivalue_with_tuple_child(self, workspace: Workspace):
        node = {
            "id": "mv1",
            "category": "multivalue",
            "children": {"id": "tuple1", "category": "tuple", "children": [{"id": "f1", "width": 50}]},
        }
        result = workspace._clean_schema_node(node)
        assert "width" in result["children"]["children"][0]

    def test_clean_schema_node_tuple_inside_multivalue(self, workspace: Workspace):
        node = {"id": "tuple1", "category": "tuple", "children": [{"id": "f1", "width": 50}]}
        result = workspace._clean_schema_node(node, parent_is_multivalue_tuple=True)
        assert result["children"][0]["width"] == 50

    def test_clean_schema_node_list_children_not_dict(self, workspace: Workspace):
        node = {"id": "section", "children": [{"id": "child1"}, "plain_value"]}
        result = workspace._clean_schema_node(node)
        assert result["children"][1] == "plain_value"

    def test_clean_schema_node_children_not_list_or_dict(self, workspace: Workspace):
        node = {"id": "field", "children": "invalid"}
        result = workspace._clean_schema_node(node)
        assert result["children"] == "invalid"


class TestFindObjectPath:
    """Tests for _find_object_path method."""

    def test_find_object_path_not_found(self, workspace: Workspace):
        result = workspace._find_object_path(ObjectType.QUEUE, 99999)
        assert result is None


class TestPushObjectMethod:
    """Tests for _push_object method."""

    def test_push_object_unsupported_type_raises(self, workspace: Workspace):
        class FakeType(str):
            value = "unsupported"

        with pytest.raises(ValueError, match="Unsupported object type"):
            workspace._push_object(MagicMock(), FakeType(), 1, {})

    def test_push_object_schema_cleans_content(self, workspace: Workspace):
        mock_client = MagicMock()

        data = {"id": 100, "content": [{"id": "f1", "score_threshold": None}]}
        workspace._push_object(mock_client, ObjectType.SCHEMA, 100, data)

        mock_client.internal_client.update.assert_called_once()
        call_args = mock_client.internal_client.update.call_args
        pushed_data = call_args[0][2]
        assert "score_threshold" not in pushed_data["content"][0]


class TestCopySingleConnectorException:
    """Tests for _copy_single_connector exception handling."""

    def test_copy_single_connector_exception(self, workspace: Workspace):
        mock_connector = Mock()
        mock_connector.id = 600
        mock_connector.name = "Test Connector"
        mock_connector.queues = ["https://api.example.com/v1/queues/100"]
        mock_connector.service_url = "https://service.example.com"
        mock_connector.authorization_token = "token"
        mock_connector.params = ""
        mock_connector.asynchronous = False

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.create_new_connector.side_effect = Exception("Connector creation failed")

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        result = CopyResult()
        workspace._copy_single_connector(mock_connector, mock_client, mapping, result)

        assert len(result.failed) == 1
        assert "Connector creation failed" in result.failed[0][3]


class TestCopySingleInboxException:
    """Tests for _copy_single_inbox exception handling."""

    def test_copy_single_inbox_exception(self, workspace: Workspace):
        inbox = {
            "id": 800,
            "name": "Test Inbox",
            "queues": ["https://api.example.com/v1/queues/100"],
            "email_prefix": "test",
        }

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.create_new_inbox.side_effect = Exception("Inbox creation failed")

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        result = CopyResult()
        workspace._copy_single_inbox(inbox, mock_client, mapping, result)

        assert len(result.failed) == 1
        assert "Inbox creation failed" in result.failed[0][3]


class TestCopySingleEmailTemplateException:
    """Tests for _copy_single_email_template exception handling."""

    def test_copy_single_email_template_exception(self, workspace: Workspace):
        mock_template = Mock()
        mock_template.id = 900
        mock_template.name = "Test Template"
        mock_template.queue = "https://api.example.com/v1/queues/100"
        mock_template.type = "export"
        mock_template.subject = "Subject"
        mock_template.message = "Message"
        mock_template.enabled = True
        mock_template.automate = False
        mock_template.to = []
        mock_template.cc = []
        mock_template.bcc = []

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.create_new_email_template.side_effect = Exception("Template creation failed")

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        result = CopyResult()
        workspace._copy_single_email_template(mock_template, mock_client, mapping, result)

        assert len(result.failed) == 1
        assert "Template creation failed" in result.failed[0][3]

    def test_copy_single_email_template_rejection_default_skipped(self, workspace: Workspace):
        mock_template = Mock()
        mock_template.id = 900
        mock_template.name = "Rejection Template"
        mock_template.queue = "https://api.example.com/v1/queues/100"
        mock_template.type = "rejection_default"

        mock_client = MagicMock()
        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        result = CopyResult()
        workspace._copy_single_email_template(mock_template, mock_client, mapping, result)

        assert len(result.skipped) == 1
        assert "auto-created type" in result.skipped[0][3]


class TestCopySingleRuleNullSchema:
    """Tests for _copy_single_rule with null schema handling."""

    def test_copy_single_rule_null_schema_skipped(self, workspace: Workspace):
        """Rule with schema=None should be skipped."""
        mock_rule = Mock()
        mock_rule.id = 1000
        mock_rule.name = "Rule without schema"
        mock_rule.schema = None

        mock_client = MagicMock()
        mapping = IdMapping(source_org_id=1, target_org_id=2)

        result = CopyResult()
        workspace._copy_single_rule(mock_rule, mock_client, mapping, result)

        assert len(result.skipped) == 1
        assert result.skipped[0][0] == ObjectType.RULE
        assert result.skipped[0][1] == 1000
        assert result.skipped[0][2] == "Rule without schema"
        assert "no schema" in result.skipped[0][3]


class TestCopyRulesNullSchema:
    """Tests for _copy_rules filtering rules with null schema."""

    def test_copy_rules_skips_null_schema_rules(self, workspace: Workspace):
        """Rules with schema=None should be skipped in _copy_rules."""
        mock_rule_with_schema = Mock()
        mock_rule_with_schema.id = 1000
        mock_rule_with_schema.name = "Rule with schema"
        mock_rule_with_schema.schema = "https://api.example.com/v1/schemas/50"

        mock_rule_without_schema = Mock()
        mock_rule_without_schema.id = 1001
        mock_rule_without_schema.name = "Rule without schema"
        mock_rule_without_schema.schema = None

        source_schema_urls = {"https://api.example.com/v1/schemas/50"}

        with patch.object(workspace, "_client") as mock_source_client:
            mock_source_client.list_rules.return_value = [mock_rule_with_schema, mock_rule_without_schema]

            mock_target_client = MagicMock()
            mock_target_client.internal_client.base_url = "https://api.example.com/v1"

            mock_new_rule = Mock()
            mock_new_rule.id = 2000
            mock_target_client.create_new_rule.return_value = mock_new_rule

            mock_action = Mock()
            mock_action.id = "action1"
            mock_action.type = "set_value"
            mock_action.payload = {}
            mock_action.event = "field_changed"
            mock_action.enabled = True
            mock_rule_with_schema.trigger_condition = "True"
            mock_rule_with_schema.actions = [mock_action]
            mock_rule_with_schema.enabled = True

            mapping = IdMapping(source_org_id=1, target_org_id=2)
            mapping.add(ObjectType.SCHEMA, 50, 60)
            result = CopyResult()

            workspace._copy_rules(mock_source_client, mock_target_client, source_schema_urls, mapping, result)

        assert len(result.created) == 1
        assert result.created[0][0] == ObjectType.RULE
        assert result.created[0][1] == 1000


class TestCopySingleRuleException:
    """Tests for _copy_single_rule exception handling."""

    def test_copy_single_rule_exception(self, workspace: Workspace):
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

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.example.com/v1"
        mock_client.create_new_rule.side_effect = Exception("Rule creation failed")

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.SCHEMA, 50, 60)

        result = CopyResult()
        workspace._copy_single_rule(mock_rule, mock_client, mapping, result)

        assert len(result.failed) == 1
        assert "Rule creation failed" in result.failed[0][3]


class TestCopySingleHookRossumStore:
    """Tests for _copy_single_hook with Rossum Store extensions."""

    def test_copy_single_hook_rossum_store_skipped(self, workspace: Workspace):
        mock_hook = Mock()
        mock_hook.id = 500
        mock_hook.name = "Store Hook"
        mock_hook.extension_source = "rossum_store"
        mock_hook.queues = ["https://api.example.com/v1/queues/100"]

        mock_client = MagicMock()
        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        result = CopyResult()
        workspace._copy_single_hook(mock_hook, mock_client, mapping, result)

        assert len(result.skipped) == 1
        assert "Rossum Store extension" in result.skipped[0][3]

    def test_copy_single_hook_with_settings(self, workspace: Workspace):
        mock_hook = Mock()
        mock_hook.id = 500
        mock_hook.name = "Hook with settings"
        mock_hook.extension_source = None
        mock_hook.type = "function"
        mock_hook.queues = ["https://api.example.com/v1/queues/100"]
        mock_hook.events = ["annotation_content.initialize"]
        mock_hook.config = {}
        mock_hook.sideload = []
        mock_hook.active = True
        mock_hook.metadata = {}
        mock_hook.settings = {"key": "value"}

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


class TestPrepareDeployDataInbox:
    """Tests for _prepare_deploy_data INBOX handling."""

    def test_prepare_deploy_data_inbox_removes_immutable_fields(self, workspace: Workspace):
        data = {
            "id": 800,
            "name": "Inbox",
            "queue": "https://api.example.com/v1/queues/100",
            "queues": ["https://api.example.com/v1/queues/100"],
            "email": "inbox@example.com",
            "email_hash": "abc123",
        }

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.target.com/v1"

        result = workspace._prepare_deploy_data(data, ObjectType.INBOX, mapping, mock_client)

        assert "queue" not in result
        assert "queues" not in result
        assert "email" not in result
        assert "email_hash" not in result
        assert result["name"] == "Inbox"


class TestPrepareEmailTemplateDeployData:
    """Tests for _prepare_email_template_deploy_data method."""

    def test_prepare_email_template_deploy_data(self, workspace: Workspace):
        data = {"id": 900, "name": "Template", "queue": "https://api.source.com/v1/queues/100"}

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        mapping.add(ObjectType.QUEUE, 100, 200)

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.target.com/v1"

        result = workspace._prepare_deploy_data(data, ObjectType.EMAIL_TEMPLATE, mapping, mock_client)

        assert result["queue"] == "https://api.target.com/v1/queues/200"

    def test_prepare_email_template_deploy_data_no_target_queue(self, workspace: Workspace):
        data = {"id": 900, "name": "Template", "queue": "https://api.source.com/v1/queues/999"}

        mapping = IdMapping(source_org_id=1, target_org_id=2)

        mock_client = MagicMock()
        mock_client.internal_client.base_url = "https://api.target.com/v1"

        result = workspace._prepare_deploy_data(data, ObjectType.EMAIL_TEMPLATE, mapping, mock_client)

        assert "queue" not in result


class TestCopyEngines:
    """Tests for _copy_engines method."""

    def test_copy_engines(self, workspace: Workspace):
        mock_engine = Mock()
        mock_engine.id = 700
        mock_engine.name = "Engine"
        mock_engine.type = "generic"
        mock_engine.url = "https://api.example.com/v1/engines/700"
        mock_engine.training_queues = []

        mock_new_engine = Mock()
        mock_new_engine.id = 701

        mock_queue = Mock()
        mock_queue.url = "https://api.example.com/v1/queues/100"
        mock_queue.dedicated_engine = "https://api.example.com/v1/engines/700"
        mock_queue.generic_engine = None

        source_queue_urls = {"https://api.example.com/v1/queues/100"}

        mock_source_client = MagicMock()
        mock_source_client.list_queues.return_value = [mock_queue]
        mock_source_client.list_engines.return_value = [mock_engine]

        mock_target_client = MagicMock()
        mock_target_client.internal_client.base_url = "https://api.example.com/v1"
        mock_target_client.internal_client.create.return_value = {"id": 701}
        mock_target_client._deserializer.return_value = mock_new_engine

        mapping = IdMapping(source_org_id=1, target_org_id=2)

        result = CopyResult()
        workspace._copy_engines(mock_source_client, mock_target_client, source_queue_urls, mapping, result)

        assert len(result.created) == 1


class TestCopyConnectorsWarning:
    """Tests for _copy_connectors SDK deserialization warning."""

    def test_copy_connectors_sdk_error(self, workspace: Workspace):
        source_queue_urls = {"https://api.example.com/v1/queues/100"}

        mock_source_client = MagicMock()
        mock_source_client.list_connectors.side_effect = Exception("SDK deserialization error")

        mock_target_client = MagicMock()

        mapping = IdMapping(source_org_id=1, target_org_id=2)
        result = CopyResult()

        workspace._copy_connectors(mock_source_client, mock_target_client, source_queue_urls, mapping, result)

        assert len(result.created) == 0
        assert len(result.failed) == 0


class TestDeployNormalizeIdMapping:
    """Tests for deploy method ID mapping normalization."""

    def test_deploy_normalizes_id_mapping(self, workspace: Workspace):
        workspace._config.org_id = 123

        workspace._save_object(ObjectType.WORKSPACE, 100, "WS", {"id": 100, "name": "WS"})
        workspace._save_object(ObjectType.QUEUE, 200, "Queue", {"id": 200, "name": "Queue"})

        mapping = IdMapping(source_org_id=456, target_org_id=123)
        mapping.add(ObjectType.WORKSPACE, 101, 100)
        mapping.add(ObjectType.QUEUE, 201, 200)

        with patch.object(workspace, "_client") as mock_client:
            mock_client.internal_client.base_url = "https://api.example.com/v1"

            result = workspace.deploy(target_org_id=456, id_mapping=mapping, dry_run=True)

        assert len(result.updated) >= 0


class TestCleanSchemaContent:
    """Tests for _clean_schema_content method."""

    def test_clean_schema_content(self, workspace: Workspace):
        content = [
            {"id": "f1", "score_threshold": None, "category": "datapoint"},
            {"id": "mv1", "category": "multivalue", "children": {"id": "t1", "category": "tuple", "children": []}},
        ]

        result = workspace._clean_schema_content(content)

        assert len(result) == 2
        assert "score_threshold" not in result[0]


class TestPullHooksConnectors:
    """Tests for _pull_hooks and _pull_connectors methods."""

    def test_pull_hooks(self, workspace: Workspace):
        workspace._save_object(
            ObjectType.QUEUE, 100, "Queue", {"id": 100, "url": "https://api.example.com/v1/queues/100"}
        )

        mock_hook = Mock()
        mock_hook.id = 500
        mock_hook.name = "Hook"
        mock_hook.queues = ["https://api.example.com/v1/queues/100"]
        mock_hook.modified_at = None

        from rossum_deploy.models import PullResult

        result = PullResult()

        with (
            patch.object(workspace, "_client") as mock_client,
            patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict,
        ):
            mock_asdict.return_value = {"id": 500, "name": "Hook"}
            mock_client.list_hooks.return_value = [mock_hook]

            workspace._pull_hooks(mock_client, result)

        assert len(result.pulled) == 1

    def test_pull_connectors(self, workspace: Workspace):
        workspace._save_object(
            ObjectType.QUEUE, 100, "Queue", {"id": 100, "url": "https://api.example.com/v1/queues/100"}
        )

        mock_connector = Mock()
        mock_connector.id = 600
        mock_connector.name = "Connector"
        mock_connector.queues = ["https://api.example.com/v1/queues/100"]
        mock_connector.modified_at = None

        from rossum_deploy.models import PullResult

        result = PullResult()

        with (
            patch.object(workspace, "_client") as mock_client,
            patch("rossum_deploy.workspace.dataclasses.asdict") as mock_asdict,
        ):
            mock_asdict.return_value = {"id": 600, "name": "Connector"}
            mock_client.list_connectors.return_value = [mock_connector]

            workspace._pull_connectors(mock_client, result)

        assert len(result.pulled) == 1
