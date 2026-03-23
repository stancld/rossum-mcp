"""Stream adapter: converts internal AgentStep/StreamEvent → minimal AI SDK wire dicts."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from rossum_agent.agent.models import (
    AgentQuestionPart,
    ErrorStep,
    FinalAnswerStep,
    TextDeltaStep,
    ToolResultStep,
    ToolStartStep,
)
from rossum_agent.api.models.schemas import StreamDoneEvent
from rossum_agent.api.services.agent_service import StreamEvent
from rossum_agent.mermaid_sanitizer import sanitize_mermaid_in_markdown

logger = logging.getLogger(__name__)


@dataclass
class StreamState:
    active_text_id: str | None = None
    part_counter: int = 0
    final_response: str | None = None
    done_event: StreamDoneEvent | None = None
    emitted_tool_call_ids: set[str] = field(default_factory=set)

    def next_id(self, prefix: str) -> str:
        self.part_counter += 1
        return f"{prefix}_{self.part_counter}"


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
            "questions": [
                {
                    "question": q.question,
                    "options": [{"value": o.value, "label": o.label, "description": o.description} for o in q.options],
                    "multi_select": q.multi_select,
                }
                for q in event.questions
            ],
        }
    ]


def _convert_text_delta(event: TextDeltaStep, state: StreamState) -> list[dict]:
    events: list[dict] = []
    if state.active_text_id is None:
        state.active_text_id = state.next_id("text")
        events.append({"type": "text-start", "id": state.active_text_id})
    events.append({"type": "text-delta", "id": state.active_text_id, "delta": event.text_delta})
    if not event.is_streaming:
        events.extend(_close_text(state))
    return events


def _convert_final_answer(event: FinalAnswerStep, state: StreamState) -> list[dict]:
    if not event.final_answer:
        return []
    # Sanitize mermaid blocks to fix common LLM syntax mistakes
    # (e.g. unquoted labels with parens/braces — see mermaid-js/mermaid#7002).
    answer = sanitize_mermaid_in_markdown(event.final_answer)
    events: list[dict] = _close_text(state)
    text_id = state.next_id("text")
    events.append({"type": "text-start", "id": text_id})
    events.append({"type": "text-delta", "id": text_id, "delta": answer})
    events.append({"type": "text-end", "id": text_id})
    return events


def _convert_tool_start(event: ToolStartStep, state: StreamState) -> list[dict]:
    events: list[dict] = _close_text(state)
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

    Emits: text-start/delta/end, tool-input-start/available, tool-output-available,
    error, data-agent-question.
    Dropped: ThinkingStep, SubAgentProgressPart, TaskSnapshotPart.
    """
    if isinstance(event, StreamDoneEvent):
        return []
    if isinstance(event, AgentQuestionPart):
        return _convert_agent_question(event)
    if isinstance(event, TextDeltaStep):
        return _convert_text_delta(event, state)
    if isinstance(event, FinalAnswerStep):
        return _convert_final_answer(event, state)
    if isinstance(event, ErrorStep):
        return [*_close_text(state), {"type": "error", "errorText": event.error or "Unknown error"}]
    if isinstance(event, ToolStartStep):
        return _convert_tool_start(event, state)
    if isinstance(event, ToolResultStep):
        return _convert_tool_result(event)
    # All other event types (ThinkingStep, SubAgentProgressPart, TaskSnapshotPart)
    # are silently dropped.
    return []


def build_finish_events(state: StreamState) -> list[dict]:
    """Build the sequence of events that close out a stream."""
    return [*_close_text(state), {"type": "finish"}]
