"""Tests for rossum_agent.tools.task_tracker module."""

from __future__ import annotations

import json

import pytest
from rossum_agent.tools.core import AgentContext, get_context, set_context
from rossum_agent.tools.task_tracker import TaskStatus, TaskTracker, create_task, list_tasks, update_task


class TestTaskTracker:
    """Tests for TaskTracker dataclass."""

    def test_create_task(self) -> None:
        tracker = TaskTracker()
        task = tracker.create_task(subject="Deploy schema")
        assert task.id == "1"
        assert task.subject == "Deploy schema"
        assert task.status == TaskStatus.pending
        assert task.description == ""

    def test_create_task_with_description(self) -> None:
        tracker = TaskTracker()
        task = tracker.create_task(subject="Push changes", description="Deploy to prod")
        assert task.description == "Deploy to prod"

    def test_create_multiple_tasks_increments_id(self) -> None:
        tracker = TaskTracker()
        t1 = tracker.create_task(subject="First")
        t2 = tracker.create_task(subject="Second")
        t3 = tracker.create_task(subject="Third")
        assert t1.id == "1"
        assert t2.id == "2"
        assert t3.id == "3"

    def test_update_task_status(self) -> None:
        tracker = TaskTracker()
        tracker.create_task(subject="Test")
        updated = tracker.update_task("1", status=TaskStatus.in_progress)
        assert updated.status == TaskStatus.in_progress

    def test_update_task_subject(self) -> None:
        tracker = TaskTracker()
        tracker.create_task(subject="Old name")
        updated = tracker.update_task("1", subject="New name")
        assert updated.subject == "New name"

    def test_update_task_not_found(self) -> None:
        tracker = TaskTracker()
        with pytest.raises(KeyError, match="Task 999 not found"):
            tracker.update_task("999", status=TaskStatus.completed)

    def test_list_tasks(self) -> None:
        tracker = TaskTracker()
        tracker.create_task(subject="A")
        tracker.create_task(subject="B")
        tasks = tracker.list_tasks()
        assert len(tasks) == 2
        assert tasks[0].subject == "A"
        assert tasks[1].subject == "B"

    def test_list_tasks_empty(self) -> None:
        tracker = TaskTracker()
        assert tracker.list_tasks() == []

    def test_list_tasks_sorted_by_numbered_prefix(self) -> None:
        tracker = TaskTracker()
        tracker.create_task(subject="3. Deploy")
        tracker.create_task(subject="1. Create queue")
        tracker.create_task(subject="2. Prune schema")
        tasks = tracker.list_tasks()
        assert [t.subject for t in tasks] == ["1. Create queue", "2. Prune schema", "3. Deploy"]

    def test_list_tasks_preserves_creation_order_without_prefix(self) -> None:
        tracker = TaskTracker()
        tracker.create_task(subject="Deploy")
        tracker.create_task(subject="Create queue")
        tasks = tracker.list_tasks()
        assert [t.subject for t in tasks] == ["Deploy", "Create queue"]

    def test_list_tasks_preserves_creation_order_with_partial_prefix(self) -> None:
        tracker = TaskTracker()
        tracker.create_task(subject="1. Create queue")
        tracker.create_task(subject="Deploy")
        tasks = tracker.list_tasks()
        assert [t.subject for t in tasks] == ["1. Create queue", "Deploy"]

    def test_snapshot(self) -> None:
        tracker = TaskTracker()
        tracker.create_task(subject="Deploy", description="Push to prod")
        tracker.create_task(subject="Verify")
        tracker.update_task("1", status=TaskStatus.completed)
        snapshot = tracker.snapshot()
        assert snapshot == [
            {"id": "1", "subject": "Deploy", "status": "completed", "description": "Push to prod"},
            {"id": "2", "subject": "Verify", "status": "pending", "description": ""},
        ]

    def test_snapshot_sorted_by_numbered_prefix(self) -> None:
        tracker = TaskTracker()
        tracker.create_task(subject="3. Deploy")
        tracker.create_task(subject="1. Create queue")
        tracker.create_task(subject="2. Prune schema")
        snapshot = tracker.snapshot()
        assert [s["subject"] for s in snapshot] == ["1. Create queue", "2. Prune schema", "3. Deploy"]

    def test_create_task_atomic(self) -> None:
        tracker = TaskTracker()
        task, snapshot = tracker.create_task_atomic(subject="Deploy", description="Push to prod")
        assert task.id == "1"
        assert task.subject == "Deploy"
        assert len(snapshot) == 1
        assert snapshot[0]["id"] == "1"

    def test_update_task_atomic(self) -> None:
        tracker = TaskTracker()
        tracker.create_task(subject="Test")
        task, snapshot = tracker.update_task_atomic("1", status=TaskStatus.completed)
        assert task.status == TaskStatus.completed
        assert snapshot[0]["status"] == "completed"

    def test_update_task_atomic_not_found(self) -> None:
        tracker = TaskTracker()
        with pytest.raises(KeyError, match="Task 999 not found"):
            tracker.update_task_atomic("999", status=TaskStatus.completed)


class TestCreateTaskTool:
    """Tests for the create_task @beta_tool function."""

    def setup_method(self) -> None:
        self.tracker = TaskTracker()
        self.snapshots: list[list[dict[str, object]]] = []
        set_context(AgentContext(task_tracker=self.tracker, task_snapshot_callback=self.snapshots.append))

    def teardown_method(self) -> None:
        set_context(AgentContext())

    def test_create_task_returns_json(self) -> None:
        result = json.loads(create_task(subject="Test task"))
        assert result["id"] == "1"
        assert result["subject"] == "Test task"
        assert result["status"] == "pending"

    def test_create_task_triggers_snapshot(self) -> None:
        create_task(subject="Step 1")
        assert len(self.snapshots) == 1
        assert len(self.snapshots[0]) == 1
        assert self.snapshots[0][0]["subject"] == "Step 1"

    def test_create_task_no_tracker(self) -> None:
        get_context().task_tracker = None
        result = json.loads(create_task(subject="Test"))
        assert "error" in result


class TestUpdateTaskTool:
    """Tests for the update_task @beta_tool function."""

    def setup_method(self) -> None:
        self.tracker = TaskTracker()
        self.tracker.create_task(subject="Existing task")
        self.snapshots: list[list[dict[str, object]]] = []
        set_context(AgentContext(task_tracker=self.tracker, task_snapshot_callback=self.snapshots.append))

    def teardown_method(self) -> None:
        set_context(AgentContext())

    def test_update_task_status(self) -> None:
        result = json.loads(update_task(task_id="1", status="in_progress"))
        assert result["status"] == "in_progress"

    def test_update_task_triggers_snapshot(self) -> None:
        update_task(task_id="1", status="completed")
        assert len(self.snapshots) == 1
        assert self.snapshots[0][0]["status"] == "completed"

    def test_update_task_not_found(self) -> None:
        result = json.loads(update_task(task_id="999", status="completed"))
        assert "error" in result

    def test_update_task_invalid_status(self) -> None:
        result = json.loads(update_task(task_id="1", status="invalid"))
        assert "error" in result
        assert "Invalid status" in result["error"]

    def test_update_task_no_tracker(self) -> None:
        get_context().task_tracker = None
        result = json.loads(update_task(task_id="1", status="completed"))
        assert "error" in result


class TestListTasksTool:
    """Tests for the list_tasks @beta_tool function."""

    def setup_method(self) -> None:
        self.tracker = TaskTracker()
        self.snapshots: list[list[dict[str, object]]] = []
        set_context(AgentContext(task_tracker=self.tracker, task_snapshot_callback=self.snapshots.append))

    def teardown_method(self) -> None:
        set_context(AgentContext())

    def test_list_tasks_empty(self) -> None:
        result = json.loads(list_tasks())
        assert result == []

    def test_list_tasks_returns_all(self) -> None:
        self.tracker.create_task(subject="A")
        self.tracker.create_task(subject="B")
        result = json.loads(list_tasks())
        assert len(result) == 2

    def test_list_tasks_does_not_trigger_snapshot(self) -> None:
        self.tracker.create_task(subject="A")
        self.snapshots.clear()
        list_tasks()
        assert len(self.snapshots) == 0

    def test_list_tasks_no_tracker(self) -> None:
        get_context().task_tracker = None
        result = json.loads(list_tasks())
        assert "error" in result
