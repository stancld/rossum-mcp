"""Stream adapter: converts internal AgentStep/StreamEvent → minimal AI SDK wire dicts."""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from rossum_agent.agent.models import (
    AgentQuestionPart,
    ErrorStep,
    FileCreatedPart,
    FinalAnswerStep,
    ReasoningStep,
    StepType,
    TaskSnapshotPart,
    TextDeltaStep,
    ToolResultStep,
    ToolStartStep,
)
from rossum_agent.api.services.agent_service.service import StreamEvent
from rossum_agent.mermaid_sanitizer import sanitize_mermaid_in_markdown

logger = structlog.get_logger(__name__)


@dataclass
class StreamState:
    active_text_id: str | None = None
    active_reasoning_id: str | None = None
    reasoning_sent_length: int = 0
    part_counter: int = 0
    emitted_tool_call_ids: set[str] = field(default_factory=set)

    def next_id(self, prefix: str) -> str:
        self.part_counter += 1
        return f"{prefix}_{self.part_counter}"


def _close_reasoning(state: StreamState) -> list[dict]:
    if state.active_reasoning_id is None:
        return []
    events: list[dict] = [{"type": "reasoning-end", "id": state.active_reasoning_id}]
    state.active_reasoning_id = None
    state.reasoning_sent_length = 0
    return events


def _close_text(state: StreamState) -> list[dict]:
    if state.active_text_id is None:
        return []
    events: list[dict] = [{"type": "text-end", "id": state.active_text_id}]
    state.active_text_id = None
    return events


def _convert_agent_question(event: AgentQuestionPart) -> list[dict]:
    return [
        {
            "type": "data-agent-question",
            "data": {
                "questions": [
                    {
                        "question": q.question,
                        "options": [
                            {"value": o.value, "label": o.label, "description": o.description} for o in q.options
                        ],
                        "multi_select": q.multi_select,
                    }
                    for q in event.questions
                ],
            },
        }
    ]


def _convert_file_created(event: FileCreatedPart) -> list[dict]:
    return [
        {
            "type": "data-file-created",
            "data": {"filename": event.filename, "url": event.url},
        }
    ]


def _convert_task_snapshot(event: TaskSnapshotPart) -> list[dict]:
    return [
        {
            "type": "data-task-snapshot",
            "data": {
                "tasks": [
                    {
                        "id": t.id,
                        "subject": t.subject,
                        "status": t.status.value,
                        "description": t.description,
                    }
                    for t in event.tasks
                ],
            },
        }
    ]


def _convert_reasoning(event: ReasoningStep, state: StreamState) -> list[dict]:
    events: list[dict] = []
    if state.active_reasoning_id is None:
        state.active_reasoning_id = state.next_id("reasoning")
        events.append({"type": "reasoning-start", "id": state.active_reasoning_id})
    delta = event.reasoning[state.reasoning_sent_length :]
    if delta:
        events.append({"type": "reasoning-delta", "id": state.active_reasoning_id, "delta": delta})
        state.reasoning_sent_length = len(event.reasoning)
    if not event.is_streaming:
        events.extend(_close_reasoning(state))
    return events


def _convert_text_delta(event: TextDeltaStep, state: StreamState) -> list[dict]:
    # Intermediate text (before tool calls) is sent as reasoning so the client
    # can distinguish it from the final answer.
    if event.step_type == StepType.INTERMEDIATE:
        return _convert_intermediate_as_reasoning(event, state)
    events: list[dict] = _close_reasoning(state)
    if state.active_text_id is None:
        state.active_text_id = state.next_id("text")
        events.append({"type": "text-start", "id": state.active_text_id})
    events.append({"type": "text-delta", "id": state.active_text_id, "delta": event.text_delta})
    if not event.is_streaming:
        events.extend(_close_text(state))
    return events


def _convert_intermediate_as_reasoning(event: TextDeltaStep, state: StreamState) -> list[dict]:
    events: list[dict] = []
    if state.active_reasoning_id is None:
        state.active_reasoning_id = state.next_id("reasoning")
        events.append({"type": "reasoning-start", "id": state.active_reasoning_id})
    if event.text_delta:
        events.append({"type": "reasoning-delta", "id": state.active_reasoning_id, "delta": event.text_delta})
    if not event.is_streaming:
        events.extend(_close_reasoning(state))
    return events


def _convert_final_answer(event: FinalAnswerStep, state: StreamState) -> list[dict]:
    if not event.final_answer:
        return []
    # Sanitize mermaid blocks to fix common LLM syntax mistakes
    # (e.g. unquoted labels with parens/braces — see mermaid-js/mermaid#7002).
    answer = sanitize_mermaid_in_markdown(event.final_answer)
    events: list[dict] = [*_close_reasoning(state)]
    events.extend(_close_text(state))
    # Emit as data event — elis-frontend ignores it; TUI renders it.
    events.append({"type": "data-final-answer", "data": {"text": answer}})
    return events


def _convert_tool_start(event: ToolStartStep, state: StreamState) -> list[dict]:
    events: list[dict] = [*_close_reasoning(state), *_close_text(state)]
    for tc in event.tool_calls:
        if tc.id in state.emitted_tool_call_ids:
            continue
        state.emitted_tool_call_ids.add(tc.id)
        events.append({"type": "tool-input-start", "toolCallId": tc.id, "toolName": tc.name})
        events.append(
            {
                "type": "tool-input-available",
                "toolCallId": tc.id,
                "toolName": tc.name,
                "input": tc.arguments,
            }
        )
    return events


def _convert_tool_result(event: ToolResultStep) -> list[dict]:
    return [
        {"type": "tool-output-available", "toolCallId": tr.tool_call_id, "output": tr.content}
        for tr in event.tool_results
    ]


def convert_agent_event(event: StreamEvent, state: StreamState) -> list[dict]:
    """Convert an internal StreamEvent to a list of AI SDK wire event dicts.

    Emits: reasoning-start/delta/end, text-start/delta/end, tool-input-start/available,
    tool-output-available, error, data-agent-question, data-task-snapshot, data-file-created,
    data-final-answer.
    Dropped: SubAgentProgressPart.
    Pre-filtered by caller: StreamDoneEvent.
    """
    if isinstance(event, FileCreatedPart):
        return _convert_file_created(event)
    if isinstance(event, AgentQuestionPart):
        return _convert_agent_question(event)
    if isinstance(event, TaskSnapshotPart):
        return _convert_task_snapshot(event)
    if isinstance(event, ReasoningStep):
        return _convert_reasoning(event, state)
    if isinstance(event, TextDeltaStep):
        return _convert_text_delta(event, state)
    if isinstance(event, FinalAnswerStep):
        return _convert_final_answer(event, state)
    if isinstance(event, ErrorStep):
        return [
            *_close_reasoning(state),
            *_close_text(state),
            {"type": "error", "errorText": event.error or "Unknown error"},
        ]
    if isinstance(event, ToolStartStep):
        return _convert_tool_start(event, state)
    if isinstance(event, ToolResultStep):
        return _convert_tool_result(event)
    # SubAgentProgressPart is silently dropped.
    return []


def build_finish_events(state: StreamState) -> list[dict]:
    """Build the sequence of events that close out a stream."""
    return [*_close_reasoning(state), *_close_text(state), {"type": "finish"}]
