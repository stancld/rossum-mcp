from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rossum_agent.api.models.schemas import AgentQuestionItemSchema


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class TaskSnapshotTask:
    id: str
    subject: str
    status: TaskStatus
    description: str = ""


@dataclass
class TaskSnapshotPart:
    tasks: list[TaskSnapshotTask]


@dataclass
class FileCreatedPart:
    filename: str
    url: str


@dataclass
class AgentQuestionPart:
    questions: list[AgentQuestionItemSchema]


type QueuedAgentEvent = TaskSnapshotPart | AgentQuestionPart | FileCreatedPart
