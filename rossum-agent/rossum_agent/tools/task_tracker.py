"""Task tracking system for multi-step agent operations.

Provides a TaskTracker (mutable state container in contextvar) and three @beta_tool
functions that let the agent create, update, and list tasks. State changes trigger
a snapshot callback that streams TaskSnapshotEvents to the frontend via SSE.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from enum import StrEnum

from anthropic import beta_tool

from rossum_agent.tools.core import get_context

_NUMBERED_PREFIX = re.compile(r"^(\d+)\.\s")


class TaskStatus(StrEnum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


@dataclass
class Task:
    id: str
    subject: str
    status: TaskStatus = TaskStatus.pending
    description: str = ""


@dataclass
class TaskTracker:
    """Thread-safe state container for task tracking.

    The tracker is stored in a contextvar and passed by reference. A threading.Lock
    serializes all mutations and reads. Atomic methods (create_task_atomic, update_task_atomic)
    return both the task and snapshot under a single lock acquisition to prevent races.
    """

    tasks: dict[str, Task] = field(default_factory=dict)
    _next_id: int = 1
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _sorted_tasks_unlocked(self) -> list[Task]:
        """Return tasks sorted by numbered prefix if all have one, else by creation order."""
        tasks = list(self.tasks.values())
        if tasks and all(_NUMBERED_PREFIX.match(t.subject) for t in tasks):
            tasks.sort(key=lambda t: int(_NUMBERED_PREFIX.match(t.subject).group(1)))  # ty:ignore[unresolved-attribute]
            return tasks
        return tasks

    def _snapshot_unlocked(self) -> list[dict[str, object]]:
        """Build snapshot without acquiring lock (caller must hold lock)."""
        return [
            {
                "id": t.id,
                "subject": t.subject,
                "status": t.status.value,
                "description": t.description,
            }
            for t in self._sorted_tasks_unlocked()
        ]

    def _create_task_unlocked(self, subject: str, description: str) -> Task:
        """Create task without acquiring lock (caller must hold lock)."""
        task_id = str(self._next_id)
        self._next_id += 1
        task = Task(id=task_id, subject=subject, description=description)
        self.tasks[task_id] = task
        return task

    def _update_task_unlocked(self, task_id: str, status: TaskStatus | None, subject: str | None) -> Task:
        """Update task without acquiring lock (caller must hold lock)."""
        task = self.tasks.get(task_id)
        if task is None:
            msg = f"Task {task_id} not found"
            raise KeyError(msg)
        if status is not None:
            task.status = status
        if subject is not None:
            task.subject = subject
        return task

    def create_task(self, subject: str, description: str = "") -> Task:
        with self._lock:
            return self._create_task_unlocked(subject, description)

    def create_task_atomic(self, subject: str, description: str = "") -> tuple[Task, list[dict[str, object]]]:
        """Create task and return snapshot atomically under one lock."""
        with self._lock:
            task = self._create_task_unlocked(subject, description)
            return task, self._snapshot_unlocked()

    def update_task(self, task_id: str, status: TaskStatus | None = None, subject: str | None = None) -> Task:
        with self._lock:
            return self._update_task_unlocked(task_id, status, subject)

    def update_task_atomic(
        self, task_id: str, status: TaskStatus | None = None, subject: str | None = None
    ) -> tuple[Task, list[dict[str, object]]]:
        """Update task and return snapshot atomically under one lock."""
        with self._lock:
            task = self._update_task_unlocked(task_id, status, subject)
            return task, self._snapshot_unlocked()

    def list_tasks(self) -> list[Task]:
        with self._lock:
            return self._sorted_tasks_unlocked()

    def snapshot(self) -> list[dict[str, object]]:
        with self._lock:
            return self._snapshot_unlocked()


def _task_to_json(task: Task) -> str:
    return json.dumps(
        {"id": task.id, "subject": task.subject, "status": task.status.value, "description": task.description}
    )


@beta_tool
def create_task(subject: str, description: str = "") -> str:
    """Create a task to track progress on a multi-step operation.

    Args:
        subject: Brief imperative title (e.g., "Deploy schema changes").
        description: Detailed description of what needs to be done.

    Returns:
        JSON with the created task's id, subject, and status.
    """
    tracker = get_context().task_tracker
    if tracker is None:
        return json.dumps({"error": "Task tracking not available"})
    task, snapshot = tracker.create_task_atomic(subject=subject, description=description)
    get_context().report_task_snapshot(snapshot)
    return _task_to_json(task)


@beta_tool
def update_task(task_id: str, status: str | None = None, subject: str | None = None) -> str:
    """Update a task's status or subject.

    Args:
        task_id: The ID of the task to update.
        status: New status - one of "pending", "in_progress", "completed".
        subject: New subject text, if changing.

    Returns:
        JSON with the updated task's id, subject, and status.
    """
    tracker = get_context().task_tracker
    if tracker is None:
        return json.dumps({"error": "Task tracking not available"})
    try:
        parsed_status = TaskStatus(status) if status else None
    except ValueError:
        return json.dumps({"error": f"Invalid status '{status}'. Must be one of: pending, in_progress, completed"})
    try:
        task, snapshot = tracker.update_task_atomic(task_id=task_id, status=parsed_status, subject=subject)
    except KeyError:
        return json.dumps({"error": f"Task {task_id} not found"})
    get_context().report_task_snapshot(snapshot)
    return _task_to_json(task)


@beta_tool
def list_tasks() -> str:
    """List all tracked tasks with their current status.

    Returns:
        JSON array of tasks with id, subject, status, and description.
    """
    tracker = get_context().task_tracker
    if tracker is None:
        return json.dumps({"error": "Task tracking not available"})
    return json.dumps(tracker.snapshot())
