"""Tests for rossum_agent.tools.deploy module."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.tools import DEPLOY_TOOLS, execute_tool, set_output_dir
from rossum_agent.tools.core import require_rossum_credentials
from rossum_agent.tools.deploy import (
    create_workspace,
    deploy_compare_workspaces,
    deploy_copy_org,
    deploy_copy_workspace,
    deploy_diff,
    deploy_pull,
    deploy_push,
    deploy_to_org,
    get_deploy_tool_names,
    get_deploy_tools,
)
from rossum_deploy.models import (
    CopyResult,
    DeployResult,
    DiffResult,
    DiffStatus,
    ObjectDiff,
    ObjectType,
    PullResult,
    PushResult,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestDeployToolsRegistration:
    """Test that deployment tools are properly registered."""

    def test_deploy_pull_is_registered(self):
        """Test that deploy_pull is in deploy tools."""
        tools = get_deploy_tools()
        tool_names = [t["name"] for t in tools]
        assert "deploy_pull" in tool_names

    def test_deploy_diff_is_registered(self):
        """Test that deploy_diff is in deploy tools."""
        tools = get_deploy_tools()
        tool_names = [t["name"] for t in tools]
        assert "deploy_diff" in tool_names

    def test_deploy_push_is_registered(self):
        """Test that deploy_push is in deploy tools."""
        tools = get_deploy_tools()
        tool_names = [t["name"] for t in tools]
        assert "deploy_push" in tool_names

    def test_deploy_copy_org_is_registered(self):
        """Test that deploy_copy_org is in deploy tools."""
        tools = get_deploy_tools()
        tool_names = [t["name"] for t in tools]
        assert "deploy_copy_org" in tool_names

    def test_deploy_copy_workspace_is_registered(self):
        """Test that deploy_copy_workspace is in deploy tools."""
        tools = get_deploy_tools()
        tool_names = [t["name"] for t in tools]
        assert "deploy_copy_workspace" in tool_names

    def test_deploy_compare_workspaces_is_registered(self):
        """Test that deploy_compare_workspaces is in deploy tools."""
        tools = get_deploy_tools()
        tool_names = [t["name"] for t in tools]
        assert "deploy_compare_workspaces" in tool_names

    def test_deploy_to_org_is_registered(self):
        """Test that deploy_to_org is in deploy tools."""
        tools = get_deploy_tools()
        tool_names = [t["name"] for t in tools]
        assert "deploy_to_org" in tool_names

    def test_deploy_tools_in_tool_names(self):
        """Test that all deploy tools are in get_deploy_tool_names."""
        names = get_deploy_tool_names()
        assert "deploy_pull" in names
        assert "deploy_diff" in names
        assert "deploy_push" in names
        assert "deploy_copy_org" in names
        assert "deploy_copy_workspace" in names
        assert "deploy_compare_workspaces" in names
        assert "deploy_to_org" in names


class TestDeployToolsSchema:
    """Test input schemas for deployment tools."""

    def test_deploy_pull_schema(self):
        """Test deploy_pull has correct input schema."""
        tools = get_deploy_tools()
        tool = next(t for t in tools if t["name"] == "deploy_pull")
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "org_id" in schema["properties"]
        assert "workspace_path" in schema["properties"]
        assert "api_base_url" in schema["properties"]
        assert "token" in schema["properties"]
        assert "org_id" in schema["required"]

    def test_deploy_diff_schema(self):
        """Test deploy_diff has correct input schema."""
        tools = get_deploy_tools()
        tool = next(t for t in tools if t["name"] == "deploy_diff")
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "workspace_path" in schema["properties"]

    def test_deploy_push_schema(self):
        """Test deploy_push has correct input schema."""
        tools = get_deploy_tools()
        tool = next(t for t in tools if t["name"] == "deploy_push")
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "dry_run" in schema["properties"]
        assert "force" in schema["properties"]
        assert "workspace_path" in schema["properties"]

    def test_deploy_copy_org_schema(self):
        """Test deploy_copy_org has correct input schema."""
        tools = get_deploy_tools()
        tool = next(t for t in tools if t["name"] == "deploy_copy_org")
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "source_org_id" in schema["properties"]
        assert "target_org_id" in schema["properties"]
        assert "target_api_base" in schema["properties"]
        assert "target_token" in schema["properties"]
        assert "source_org_id" in schema["required"]
        assert "target_org_id" in schema["required"]

    def test_deploy_copy_workspace_schema(self):
        """Test deploy_copy_workspace has correct input schema."""
        tools = get_deploy_tools()
        tool = next(t for t in tools if t["name"] == "deploy_copy_workspace")
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "source_workspace_id" in schema["properties"]
        assert "target_org_id" in schema["properties"]
        assert "source_workspace_id" in schema["required"]
        assert "target_org_id" in schema["required"]

    def test_deploy_compare_workspaces_schema(self):
        """Test deploy_compare_workspaces has correct input schema."""
        tools = get_deploy_tools()
        tool = next(t for t in tools if t["name"] == "deploy_compare_workspaces")
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "source_workspace_path" in schema["properties"]
        assert "target_workspace_path" in schema["properties"]
        assert "id_mapping_path" in schema["properties"]
        assert "source_workspace_path" in schema["required"]
        assert "target_workspace_path" in schema["required"]

    def test_deploy_to_org_schema(self):
        """Test deploy_to_org has correct input schema."""
        tools = get_deploy_tools()
        tool = next(t for t in tools if t["name"] == "deploy_to_org")
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "target_org_id" in schema["properties"]
        assert "target_api_base" in schema["properties"]
        assert "target_token" in schema["properties"]
        assert "dry_run" in schema["properties"]
        assert "target_org_id" in schema["required"]


class TestDeployPull:
    """Test deploy_pull function."""

    def test_successful_pull(self, tmp_path: Path):
        """Test successful pull operation."""
        mock_result = PullResult(
            organization_name="Test Org",
            pulled=[
                (ObjectType.WORKSPACE, 123, "Test Workspace"),
                (ObjectType.QUEUE, 456, "Test Queue"),
            ],
            skipped=[],
        )

        mock_workspace = MagicMock()
        mock_workspace.pull.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_pull(org_id=12345, workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["pulled_count"] == 2
        assert result["skipped_count"] == 0
        assert result["workspace_path"] == str(tmp_path)
        assert "summary" in result
        mock_workspace.pull.assert_called_once_with(org_id=12345)

    def test_pull_with_custom_credentials(self, tmp_path: Path):
        """Test pull with custom API base and token."""
        mock_result = PullResult(pulled=[], skipped=[])
        mock_workspace = MagicMock()
        mock_workspace.pull.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace) as mock_create:
            deploy_pull(
                org_id=123,
                workspace_path=str(tmp_path),
                api_base_url="https://sandbox.api.rossum.ai/v1",
                token="sandbox_token",
            )

        mock_create.assert_called_once_with(
            str(tmp_path),
            api_base_url="https://sandbox.api.rossum.ai/v1",
            token="sandbox_token",
        )

    def test_pull_handles_error(self, tmp_path: Path):
        """Test pull error handling."""
        with patch(
            "rossum_agent.tools.deploy.create_workspace",
            side_effect=Exception("API connection failed"),
        ):
            result_json = deploy_pull(org_id=123, workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "API connection failed" in result["error"]


class TestDeployDiff:
    """Test deploy_diff function."""

    def test_successful_diff(self, tmp_path: Path):
        """Test successful diff operation."""
        mock_result = DiffResult(
            objects=[
                ObjectDiff(
                    object_type=ObjectType.SCHEMA, object_id=1, name="Invoice Schema", status=DiffStatus.LOCAL_MODIFIED
                ),
            ],
            total_unchanged=5,
            total_local_modified=1,
            total_remote_modified=0,
            total_conflicts=0,
        )

        mock_workspace = MagicMock()
        mock_workspace.diff.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_diff(workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["unchanged"] == 5
        assert result["local_modified"] == 1
        assert result["remote_modified"] == 0
        assert result["conflicts"] == 0
        assert result["workspace_path"] == str(tmp_path)
        assert "summary" in result

    def test_diff_with_conflicts(self, tmp_path: Path):
        """Test diff with conflicts."""
        mock_result = DiffResult(total_unchanged=3, total_local_modified=1, total_remote_modified=1, total_conflicts=2)

        mock_workspace = MagicMock()
        mock_workspace.diff.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_diff(workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["conflicts"] == 2

    def test_diff_handles_error(self, tmp_path: Path):
        """Test diff error handling."""
        with patch(
            "rossum_agent.tools.deploy.create_workspace",
            side_effect=Exception("Workspace not initialized"),
        ):
            result_json = deploy_diff(workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "Workspace not initialized" in result["error"]


class TestDeployPush:
    """Test deploy_push function."""

    def test_successful_push(self, tmp_path: Path):
        """Test successful push operation."""
        mock_result = PushResult(
            pushed=[(ObjectType.SCHEMA, 1, "Invoice Schema"), (ObjectType.HOOK, 2, "Validation Hook")],
            skipped=[],
            failed=[],
        )

        mock_workspace = MagicMock()
        mock_workspace.push.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_push(workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["dry_run"] is False
        assert result["pushed_count"] == 2
        assert result["skipped_count"] == 0
        assert result["failed_count"] == 0
        mock_workspace.push.assert_called_once_with(force=False)

    def test_push_dry_run(self, tmp_path: Path):
        """Test push dry run mode."""
        mock_result = PushResult(pushed=[(ObjectType.SCHEMA, 1, "Test Schema")], skipped=[], failed=[])

        mock_workspace = MagicMock()
        mock_workspace.push.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_push(dry_run=True, workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["dry_run"] is True
        assert result["would_push_count"] == 1
        mock_workspace.push.assert_called_once_with(dry_run=True)

    def test_push_with_force(self, tmp_path: Path):
        """Test push with force option."""
        mock_result = PushResult(pushed=[], skipped=[], failed=[])
        mock_workspace = MagicMock()
        mock_workspace.push.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            deploy_push(force=True, workspace_path=str(tmp_path))

        mock_workspace.push.assert_called_once_with(force=True)

    def test_push_with_failures(self, tmp_path: Path):
        """Test push with some failures."""
        mock_result = PushResult(
            pushed=[(ObjectType.SCHEMA, 1, "Schema1")],
            skipped=[(ObjectType.QUEUE, 2, "Queue1", "No local changes")],
            failed=[(ObjectType.HOOK, 3, "Hook1", "Permission denied")],
        )

        mock_workspace = MagicMock()
        mock_workspace.push.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_push(workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["pushed_count"] == 1
        assert result["skipped_count"] == 1
        assert result["failed_count"] == 1

    def test_push_handles_error(self, tmp_path: Path):
        """Test push error handling."""
        mock_workspace = MagicMock()
        mock_workspace.push.side_effect = Exception("Conflict detected")
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_push(workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "Conflict detected" in result["error"]


class TestDeployCopyOrg:
    """Test deploy_copy_org function."""

    def test_successful_copy_org(self, tmp_path: Path):
        """Test successful org copy operation."""
        mock_result = CopyResult(
            created=[(ObjectType.WORKSPACE, 1, 101, "Workspace1"), (ObjectType.QUEUE, 2, 102, "Queue1")],
            skipped=[],
            failed=[],
        )

        mock_workspace = MagicMock()
        mock_workspace.copy_org.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_copy_org(source_org_id=100, target_org_id=200, workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["created_count"] == 2
        assert result["skipped_count"] == 0
        assert result["failed_count"] == 0
        mock_workspace.copy_org.assert_called_once_with(
            source_org_id=100, target_org_id=200, target_api_base=None, target_token=None
        )

    def test_copy_org_with_target_credentials(self, tmp_path: Path):
        """Test copy org with custom target credentials."""
        mock_result = CopyResult(created=[], skipped=[], failed=[])
        mock_workspace = MagicMock()
        mock_workspace.copy_org.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            deploy_copy_org(
                source_org_id=100,
                target_org_id=200,
                target_api_base="https://sandbox.api.rossum.ai/v1",
                target_token="sandbox_token",
                workspace_path=str(tmp_path),
            )

        mock_workspace.copy_org.assert_called_once_with(
            source_org_id=100,
            target_org_id=200,
            target_api_base="https://sandbox.api.rossum.ai/v1",
            target_token="sandbox_token",
        )

    def test_copy_org_handles_error(self, tmp_path: Path):
        """Test copy org error handling."""
        mock_workspace = MagicMock()
        mock_workspace.copy_org.side_effect = Exception("Target org not accessible")
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_copy_org(source_org_id=100, target_org_id=200, workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "Target org not accessible" in result["error"]


class TestDeployCopyWorkspace:
    """Test deploy_copy_workspace function."""

    def test_successful_copy_workspace(self, tmp_path: Path):
        """Test successful workspace copy operation."""
        mock_result = CopyResult(
            created=[(ObjectType.WORKSPACE, 10, 110, "Copied Workspace"), (ObjectType.QUEUE, 11, 111, "Copied Queue")],
            skipped=[],
            failed=[],
        )

        mock_workspace = MagicMock()
        mock_workspace.copy_workspace.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_copy_workspace(
                source_workspace_id=10, target_org_id=200, workspace_path=str(tmp_path)
            )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["created_count"] == 2
        mock_workspace.copy_workspace.assert_called_once_with(
            source_workspace_id=10, target_org_id=200, target_api_base=None, target_token=None
        )

    def test_copy_workspace_with_target_credentials(self, tmp_path: Path):
        """Test copy workspace with custom target credentials."""
        mock_result = CopyResult(created=[], skipped=[], failed=[])
        mock_workspace = MagicMock()
        mock_workspace.copy_workspace.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            deploy_copy_workspace(
                source_workspace_id=10,
                target_org_id=200,
                target_api_base="https://sandbox.api.rossum.ai/v1",
                target_token="sandbox_token",
                workspace_path=str(tmp_path),
            )

        mock_workspace.copy_workspace.assert_called_once_with(
            source_workspace_id=10,
            target_org_id=200,
            target_api_base="https://sandbox.api.rossum.ai/v1",
            target_token="sandbox_token",
        )

    def test_copy_workspace_handles_error(self, tmp_path: Path):
        """Test copy workspace error handling."""
        mock_workspace = MagicMock()
        mock_workspace.copy_workspace.side_effect = Exception("Workspace not found")
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_copy_workspace(
                source_workspace_id=999, target_org_id=200, workspace_path=str(tmp_path)
            )

        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "Workspace not found" in result["error"]


class TestDeployCompareWorkspaces:
    """Test deploy_compare_workspaces function."""

    def test_successful_compare(self, tmp_path: Path):
        """Test successful workspace comparison."""
        source_path = tmp_path / "source"
        target_path = tmp_path / "target"
        source_path.mkdir()
        target_path.mkdir()

        mock_result = MagicMock()
        mock_result.summary.return_value = "Comparison summary"
        mock_result.source_workspace_id = 1
        mock_result.target_workspace_id = 2
        mock_result.total_identical = 5
        mock_result.total_different = 2
        mock_result.source_only = [(ObjectType.HOOK, 1, "Hook1")]
        mock_result.target_only = []

        with patch("rossum_agent.tools.deploy.require_rossum_credentials", return_value=("https://api.test", "token")):
            with patch("rossum_agent.tools.deploy.Workspace") as mock_ws_class:
                mock_source_ws = MagicMock()
                mock_source_ws.compare_workspaces.return_value = mock_result
                mock_ws_class.return_value = mock_source_ws

                result_json = deploy_compare_workspaces(
                    source_workspace_path=str(source_path),
                    target_workspace_path=str(target_path),
                )

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["total_identical"] == 5
        assert result["total_different"] == 2
        assert result["source_only_count"] == 1
        assert result["target_only_count"] == 0

    def test_compare_with_id_mapping(self, tmp_path: Path):
        """Test comparison with ID mapping file."""
        source_path = tmp_path / "source"
        target_path = tmp_path / "target"
        source_path.mkdir()
        target_path.mkdir()

        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"mapping": {}}')

        mock_result = MagicMock()
        mock_result.summary.return_value = "Summary"
        mock_result.source_workspace_id = 1
        mock_result.target_workspace_id = 2
        mock_result.total_identical = 0
        mock_result.total_different = 0
        mock_result.source_only = []
        mock_result.target_only = []

        with patch("rossum_agent.tools.deploy.require_rossum_credentials", return_value=("https://api.test", "token")):
            with patch("rossum_agent.tools.deploy.Workspace") as mock_ws_class:
                with patch("rossum_agent.tools.deploy.IdMapping.model_validate") as mock_validate:
                    mock_source_ws = MagicMock()
                    mock_source_ws.compare_workspaces.return_value = mock_result
                    mock_ws_class.return_value = mock_source_ws
                    mock_validate.return_value = MagicMock()

                    result_json = deploy_compare_workspaces(
                        source_workspace_path=str(source_path),
                        target_workspace_path=str(target_path),
                        id_mapping_path=str(mapping_file),
                    )

        result = json.loads(result_json)
        assert result["status"] == "success"

    def test_compare_handles_error(self, tmp_path: Path):
        """Test compare error handling."""
        with patch("rossum_agent.tools.deploy.require_rossum_credentials", side_effect=Exception("Creds error")):
            result_json = deploy_compare_workspaces(
                source_workspace_path=str(tmp_path),
                target_workspace_path=str(tmp_path),
            )

        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "Creds error" in result["error"]


class TestDeployToOrg:
    """Test deploy_to_org function."""

    def test_successful_deploy(self, tmp_path: Path):
        """Test successful deploy to org operation."""
        mock_result = DeployResult(
            created=[(ObjectType.HOOK, 1, "New Hook")],
            updated=[(ObjectType.SCHEMA, 2, "Updated Schema")],
            skipped=[],
            failed=[],
        )

        mock_workspace = MagicMock()
        mock_workspace.deploy.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_to_org(target_org_id=200, workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["dry_run"] is False
        assert result["created_count"] == 1
        assert result["updated_count"] == 1
        assert result["skipped_count"] == 0
        assert result["failed_count"] == 0
        mock_workspace.deploy.assert_called_once_with(
            target_org_id=200,
            target_api_base=None,
            target_token=None,
            dry_run=False,
        )

    def test_deploy_dry_run(self, tmp_path: Path):
        """Test deploy dry run mode."""
        mock_result = DeployResult(
            created=[(ObjectType.HOOK, 1, "Would Create Hook")], updated=[], skipped=[], failed=[]
        )

        mock_workspace = MagicMock()
        mock_workspace.deploy.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_to_org(target_org_id=200, dry_run=True, workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["dry_run"] is True
        mock_workspace.deploy.assert_called_once_with(
            target_org_id=200, target_api_base=None, target_token=None, dry_run=True
        )

    def test_deploy_with_target_credentials(self, tmp_path: Path):
        """Test deploy with custom target credentials."""
        mock_result = DeployResult(created=[], updated=[], skipped=[], failed=[])
        mock_workspace = MagicMock()
        mock_workspace.deploy.return_value = mock_result
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            deploy_to_org(
                target_org_id=200,
                target_api_base="https://sandbox.api.rossum.ai/v1",
                target_token="sandbox_token",
                workspace_path=str(tmp_path),
            )

        mock_workspace.deploy.assert_called_once_with(
            target_org_id=200,
            target_api_base="https://sandbox.api.rossum.ai/v1",
            target_token="sandbox_token",
            dry_run=False,
        )

    def test_deploy_handles_error(self, tmp_path: Path):
        """Test deploy error handling."""
        mock_workspace = MagicMock()
        mock_workspace.deploy.side_effect = Exception("ID mapping not found")
        mock_workspace.path = tmp_path

        with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
            result_json = deploy_to_org(target_org_id=200, workspace_path=str(tmp_path))

        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "ID mapping not found" in result["error"]


class TestExecuteDeployTool:
    """Test execute_tool integration for deploy tools."""

    def test_execute_deploy_pull(self, tmp_path: Path):
        """Test execute_tool with deploy_pull."""
        mock_result = PullResult(pulled=[], skipped=[])
        mock_workspace = MagicMock()
        mock_workspace.pull.return_value = mock_result
        mock_workspace.path = tmp_path

        set_output_dir(tmp_path)
        try:
            with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
                result_json = execute_tool("deploy_pull", {"org_id": 123}, DEPLOY_TOOLS)

            result = json.loads(result_json)
            assert result["status"] == "success"
        finally:
            set_output_dir(None)

    def test_execute_deploy_diff(self, tmp_path: Path):
        """Test execute_tool with deploy_diff."""
        mock_result = DiffResult()
        mock_workspace = MagicMock()
        mock_workspace.diff.return_value = mock_result
        mock_workspace.path = tmp_path

        set_output_dir(tmp_path)
        try:
            with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
                result_json = execute_tool("deploy_diff", {}, DEPLOY_TOOLS)

            result = json.loads(result_json)
            assert result["status"] == "success"
        finally:
            set_output_dir(None)

    def test_execute_deploy_push(self, tmp_path: Path):
        """Test execute_tool with deploy_push."""
        mock_result = PushResult(pushed=[], skipped=[], failed=[])
        mock_workspace = MagicMock()
        mock_workspace.push.return_value = mock_result
        mock_workspace.path = tmp_path

        set_output_dir(tmp_path)
        try:
            with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
                result_json = execute_tool("deploy_push", {"dry_run": True}, DEPLOY_TOOLS)

            result = json.loads(result_json)
            assert result["status"] == "success"
            assert result["dry_run"] is True
        finally:
            set_output_dir(None)

    def test_execute_deploy_copy_org(self, tmp_path: Path):
        """Test execute_tool with deploy_copy_org."""
        mock_result = CopyResult(created=[], skipped=[], failed=[])
        mock_workspace = MagicMock()
        mock_workspace.copy_org.return_value = mock_result
        mock_workspace.path = tmp_path

        set_output_dir(tmp_path)
        try:
            with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
                result_json = execute_tool(
                    "deploy_copy_org", {"source_org_id": 100, "target_org_id": 200}, DEPLOY_TOOLS
                )

            result = json.loads(result_json)
            assert result["status"] == "success"
        finally:
            set_output_dir(None)

    def test_execute_deploy_copy_workspace(self, tmp_path: Path):
        """Test execute_tool with deploy_copy_workspace."""
        mock_result = CopyResult(created=[], skipped=[], failed=[])
        mock_workspace = MagicMock()
        mock_workspace.copy_workspace.return_value = mock_result
        mock_workspace.path = tmp_path

        set_output_dir(tmp_path)
        try:
            with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
                result_json = execute_tool(
                    "deploy_copy_workspace", {"source_workspace_id": 10, "target_org_id": 200}, DEPLOY_TOOLS
                )

            result = json.loads(result_json)
            assert result["status"] == "success"
        finally:
            set_output_dir(None)

    def test_execute_deploy_to_org(self, tmp_path: Path):
        """Test execute_tool with deploy_to_org."""
        mock_result = DeployResult(created=[], updated=[], skipped=[], failed=[])
        mock_workspace = MagicMock()
        mock_workspace.deploy.return_value = mock_result
        mock_workspace.path = tmp_path

        set_output_dir(tmp_path)
        try:
            with patch("rossum_agent.tools.deploy.create_workspace", return_value=mock_workspace):
                result_json = execute_tool("deploy_to_org", {"target_org_id": 200}, DEPLOY_TOOLS)

            result = json.loads(result_json)
            assert result["status"] == "success"
        finally:
            set_output_dir(None)

    def test_execute_deploy_tool_unknown_name(self):
        """Test that unknown tool name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            execute_tool("nonexistent_tool", {}, DEPLOY_TOOLS)


class TestCreateWorkspaceHelper:
    """Test create_workspace helper function."""

    def test_uses_default_path_when_none(self, tmp_path: Path):
        """Test that default path is used when workspace_path is None."""
        set_output_dir(tmp_path)
        try:
            with patch("rossum_agent.tools.deploy.Workspace") as mock_ws_class:
                mock_ws_class.return_value = MagicMock()
                with patch.dict(
                    "os.environ",
                    {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"},
                ):
                    create_workspace(None)

                call_args = mock_ws_class.call_args
                path_arg = call_args[0][0]
                assert str(path_arg).endswith("rossum-config")
        finally:
            set_output_dir(None)

    def test_uses_custom_path(self, tmp_path: Path):
        """Test that custom path is used when provided."""
        custom_path = tmp_path / "custom-config"

        with patch("rossum_agent.tools.deploy.Workspace") as mock_ws_class:
            mock_ws_class.return_value = MagicMock()
            with patch.dict(
                "os.environ",
                {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"},
            ):
                create_workspace(str(custom_path))

            call_args = mock_ws_class.call_args
            path_arg = call_args[0][0]
            assert path_arg == custom_path

    def test_overrides_credentials_when_provided(self, tmp_path: Path):
        """Test that provided credentials override env vars."""
        with patch("rossum_agent.tools.deploy.Workspace") as mock_ws_class:
            mock_ws_class.return_value = MagicMock()
            with patch.dict(
                "os.environ",
                {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "env_token"},
            ):
                create_workspace(str(tmp_path), api_base_url="https://sandbox.api.rossum.ai/v1", token="custom_token")

            call_kwargs = mock_ws_class.call_args[1]
            assert call_kwargs["api_base"] == "https://sandbox.api.rossum.ai/v1"
            assert call_kwargs["token"] == "custom_token"


class TestRequireRossumCredentials:
    """Test require_rossum_credentials helper function."""

    def test_returns_env_credentials(self):
        """Test that env vars are returned when set."""
        with patch.dict(
            "os.environ",
            {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"},
        ):
            api_base, token = require_rossum_credentials()

        assert api_base == "https://api.rossum.ai/v1"
        assert token == "test_token"

    @patch("rossum_agent.tools.core._rossum_credentials")
    def test_raises_when_credentials_missing(self, mock_creds):
        """Test that error is raised when neither context nor env vars have credentials."""
        mock_creds.get.return_value = None
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="credentials not available"):
                require_rossum_credentials()
