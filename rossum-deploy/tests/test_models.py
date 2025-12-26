from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from rossum_deploy.models import (
    _GREEN,
    _RED,
    _RESET,
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


class TestObjectMeta:
    def test_create(self):
        meta = ObjectMeta(
            pulled_at=datetime.now(UTC),
            remote_modified_at=datetime.now(UTC),
            object_type=ObjectType.QUEUE,
            object_id=123,
        )
        assert meta.object_id == 123
        assert meta.object_type == ObjectType.QUEUE


class TestLocalObject:
    def test_create_with_alias(self):
        obj = LocalObject(
            _meta=ObjectMeta(pulled_at=datetime.now(UTC), object_type=ObjectType.HOOK, object_id=456),
            data={"name": "Test Hook", "id": 456},
        )
        assert obj.meta.object_id == 456
        assert obj.data["name"] == "Test Hook"

    def test_serialize_with_alias(self):
        obj = LocalObject(
            _meta=ObjectMeta(pulled_at=datetime(2024, 1, 1, tzinfo=UTC), object_type=ObjectType.SCHEMA, object_id=789),
            data={"name": "Test Schema"},
        )
        dumped = obj.model_dump(by_alias=True)
        assert "_meta" in dumped
        assert "meta" not in dumped


class TestDiffResult:
    def test_summary_empty(self):
        result = DiffResult()
        summary = result.summary()
        assert "Unchanged: 0" in summary

    def test_summary_with_changes(self):
        result = DiffResult(
            objects=[
                ObjectDiff(
                    object_type=ObjectType.QUEUE,
                    object_id=1,
                    name="Test Queue",
                    status=DiffStatus.LOCAL_MODIFIED,
                    changed_fields=["name", "settings"],
                    field_diffs=[
                        FieldDiff(field="name", source_value="Old Name", target_value="New Name"),
                        FieldDiff(field="settings", source_value={"a": 1}, target_value={"a": 2}),
                    ],
                )
            ],
            total_local_modified=1,
        )
        summary = result.summary()
        assert "Local modified: 1" in summary
        assert "Test Queue" in summary
        assert "#### name" in summary
        assert "#### settings" in summary

    def test_summary_with_color_true(self):
        result = DiffResult(
            objects=[
                ObjectDiff(
                    object_type=ObjectType.QUEUE,
                    object_id=1,
                    name="Test Queue",
                    status=DiffStatus.LOCAL_MODIFIED,
                    changed_fields=["name"],
                    field_diffs=[
                        FieldDiff(field="name", source_value="Old", target_value="New"),
                    ],
                )
            ],
            total_local_modified=1,
        )
        summary = result.summary(color=True)
        assert _RED in summary
        assert _GREEN in summary
        assert _RESET in summary
        assert "```diff" not in summary

    def test_summary_with_color_false(self):
        result = DiffResult(
            objects=[
                ObjectDiff(
                    object_type=ObjectType.QUEUE,
                    object_id=1,
                    name="Test Queue",
                    status=DiffStatus.LOCAL_MODIFIED,
                    changed_fields=["name"],
                    field_diffs=[
                        FieldDiff(field="name", source_value="Old", target_value="New"),
                    ],
                )
            ],
            total_local_modified=1,
        )
        summary = result.summary(color=False)
        assert _RED not in summary
        assert _GREEN not in summary
        assert _RESET not in summary
        assert "```diff" in summary

    def test_summary_color_none_uses_tty_detection_true(self):
        result = DiffResult(
            objects=[
                ObjectDiff(
                    object_type=ObjectType.QUEUE,
                    object_id=1,
                    name="Test Queue",
                    status=DiffStatus.LOCAL_MODIFIED,
                    changed_fields=["name"],
                    field_diffs=[
                        FieldDiff(field="name", source_value="Old", target_value="New"),
                    ],
                )
            ],
            total_local_modified=1,
        )
        with patch("rossum_deploy.models._is_tty", return_value=True):
            summary = result.summary(color=None)
        assert _RED in summary
        assert "```diff" not in summary

    def test_summary_color_none_uses_tty_detection_false(self):
        result = DiffResult(
            objects=[
                ObjectDiff(
                    object_type=ObjectType.QUEUE,
                    object_id=1,
                    name="Test Queue",
                    status=DiffStatus.LOCAL_MODIFIED,
                    changed_fields=["name"],
                    field_diffs=[
                        FieldDiff(field="name", source_value="Old", target_value="New"),
                    ],
                )
            ],
            total_local_modified=1,
        )
        with patch("rossum_deploy.models._is_tty", return_value=False):
            summary = result.summary(color=None)
        assert _RED not in summary
        assert "```diff" in summary


class TestPushResult:
    def test_summary(self):
        result = PushResult(
            pushed=[(ObjectType.QUEUE, 1, "Queue 1")], skipped=[(ObjectType.HOOK, 2, "Hook 1", "conflict")]
        )
        summary = result.summary()
        assert "Pushed: 1" in summary
        assert "Skipped: 1" in summary
        assert "Queue 1" in summary


class TestPullResult:
    def test_summary(self):
        result = PullResult(pulled=[(ObjectType.WORKSPACE, 1, "WS 1"), (ObjectType.QUEUE, 2, "Queue 1")])
        summary = result.summary()
        assert "Pulled: 2" in summary
        assert "WS 1" in summary


class TestIdMapping:
    def test_add_and_get(self):
        mapping = IdMapping(source_org_id=123, target_org_id=456)
        mapping.add(ObjectType.QUEUE, 100, 200)
        mapping.add(ObjectType.QUEUE, 101, 201)

        assert mapping.get(ObjectType.QUEUE, 100) == 200
        assert mapping.get(ObjectType.QUEUE, 101) == 201
        assert mapping.get(ObjectType.QUEUE, 999) is None

    def test_get_all(self):
        mapping = IdMapping(source_org_id=123, target_org_id=456)
        mapping.add(ObjectType.QUEUE, 100, 200)
        mapping.add(ObjectType.QUEUE, 101, 201)
        mapping.add(ObjectType.HOOK, 500, 600)

        queue_mappings = mapping.get_all(ObjectType.QUEUE)
        assert queue_mappings == {100: 200, 101: 201}

        hook_mappings = mapping.get_all(ObjectType.HOOK)
        assert hook_mappings == {500: 600}


class TestCopyResult:
    def test_summary(self):
        result = CopyResult(
            created=[(ObjectType.WORKSPACE, 1, 10, "WS 1"), (ObjectType.QUEUE, 2, 20, "Queue 1")],
            skipped=[(ObjectType.HOOK, 3, "Hook 1", "no target queues")],
            failed=[(ObjectType.SCHEMA, 4, "Schema 1", "API error")],
        )
        summary = result.summary()
        assert "Created: 2" in summary
        assert "Skipped: 1" in summary
        assert "Failed: 1" in summary
        assert "WS 1" in summary
        assert "source: 1 → target: 10" in summary


class TestDeployResult:
    def test_summary(self):
        result = DeployResult(
            created=[(ObjectType.QUEUE, 100, "New Queue")],
            updated=[(ObjectType.HOOK, 200, "Updated Hook")],
            skipped=[(ObjectType.SCHEMA, 300, "Schema 1", "no target mapping")],
        )
        summary = result.summary()
        assert "Created: 1" in summary
        assert "Updated: 1" in summary
        assert "Skipped: 1" in summary
        assert "New Queue" in summary
        assert "Updated Hook" in summary

    def test_summary_with_failed(self):
        result = DeployResult(failed=[(ObjectType.HOOK, 100, "Hook 1", "API error")])
        summary = result.summary()
        assert "Failed: 1" in summary
        assert "Hook 1" in summary
        assert "API error" in summary


class TestDiffResultToMarkdown:
    def test_to_markdown_returns_summary(self):
        result = DiffResult(total_unchanged=5)
        assert result.to_markdown() == result.summary()

    def test_summary_with_conflicts(self):
        result = DiffResult(
            objects=[
                ObjectDiff(
                    object_type=ObjectType.QUEUE, object_id=1, name="Conflicting Queue", status=DiffStatus.CONFLICT
                )
            ],
            total_conflicts=1,
        )
        summary = result.summary()
        assert "Conflicts: 1" in summary
        assert "Conflicts (require resolution)" in summary
        assert "Conflicting Queue" in summary


class TestPushResultEdgeCases:
    def test_summary_with_failed(self):
        result = PushResult(failed=[(ObjectType.QUEUE, 1, "Queue 1", "Connection error")])
        summary = result.summary()
        assert "Failed: 1" in summary
        assert "Queue 1" in summary
        assert "Connection error" in summary


class TestPullResultEdgeCases:
    def test_summary_with_org_and_workspace(self):
        result = PullResult(
            organization_name="Test Org", workspace_name="Test Workspace", pulled=[(ObjectType.QUEUE, 1, "Queue 1")]
        )
        summary = result.summary()
        assert "Organization: Test Org" in summary
        assert "Workspace: Test Workspace" in summary


class TestCompareResultToMarkdown:
    def test_to_markdown_returns_summary(self):
        result = CompareResult(source_workspace_id=1, target_workspace_id=2, total_identical=5)
        assert result.to_markdown() == result.summary()

    def test_summary_with_source_only_and_target_only(self):
        result = CompareResult(
            source_workspace_id=1,
            target_workspace_id=2,
            source_only=[(ObjectType.HOOK, 100, "Source Hook")],
            target_only=[(ObjectType.RULE, 200, "Target Rule")],
        )
        summary = result.summary()
        assert "Source Only (not in target)" in summary
        assert "Source Hook" in summary
        assert "Target Only (not in source)" in summary
        assert "Target Rule" in summary


class TestCompareResultSummaryColor:
    def test_summary_with_color_true(self):
        result = CompareResult(
            source_workspace_id=1,
            target_workspace_id=2,
            objects=[
                ObjectCompare(
                    object_type=ObjectType.QUEUE,
                    source_id=1,
                    target_id=2,
                    name="Test Queue",
                    is_identical=False,
                    field_diffs=[
                        FieldDiff(field="name", source_value="Source Name", target_value="Target Name"),
                    ],
                )
            ],
            total_different=1,
        )
        summary = result.summary(color=True)
        assert _RED in summary
        assert _GREEN in summary
        assert _RESET in summary
        assert "```diff" not in summary

    def test_summary_with_color_false(self):
        result = CompareResult(
            source_workspace_id=1,
            target_workspace_id=2,
            objects=[
                ObjectCompare(
                    object_type=ObjectType.QUEUE,
                    source_id=1,
                    target_id=2,
                    name="Test Queue",
                    is_identical=False,
                    field_diffs=[
                        FieldDiff(field="name", source_value="Source Name", target_value="Target Name"),
                    ],
                )
            ],
            total_different=1,
        )
        summary = result.summary(color=False)
        assert _RED not in summary
        assert _GREEN not in summary
        assert _RESET not in summary
        assert "```diff" in summary

    def test_summary_color_none_uses_tty_detection_true(self):
        result = CompareResult(
            source_workspace_id=1,
            target_workspace_id=2,
            objects=[
                ObjectCompare(
                    object_type=ObjectType.QUEUE,
                    source_id=1,
                    target_id=2,
                    name="Test Queue",
                    is_identical=False,
                    field_diffs=[
                        FieldDiff(field="name", source_value="Source Name", target_value="Target Name"),
                    ],
                )
            ],
            total_different=1,
        )
        with patch("rossum_deploy.models._is_tty", return_value=True):
            summary = result.summary(color=None)
        assert _RED in summary
        assert "```diff" not in summary

    def test_summary_color_none_uses_tty_detection_false(self):
        result = CompareResult(
            source_workspace_id=1,
            target_workspace_id=2,
            objects=[
                ObjectCompare(
                    object_type=ObjectType.QUEUE,
                    source_id=1,
                    target_id=2,
                    name="Test Queue",
                    is_identical=False,
                    field_diffs=[
                        FieldDiff(field="name", source_value="Source Name", target_value="Target Name"),
                    ],
                )
            ],
            total_different=1,
        )
        with patch("rossum_deploy.models._is_tty", return_value=False):
            summary = result.summary(color=None)
        assert _RED not in summary
        assert "```diff" in summary
