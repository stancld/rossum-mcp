"""Stream adapter: converts internal AgentStep/StreamEvent → minimal AI SDK wire dicts."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from rossum_agent.agent.models import AgentQuestionPart, ErrorStep, FinalAnswerStep, TextDeltaStep
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

    def next_id(self, prefix: str) -> str:
        self.part_counter += 1
        return f"{prefix}_{self.part_counter}"


def _close_text(state: StreamState) -> list[dict]:
    if state.active_text_id is None:
        return []
    events: list[dict] = [{"type": "text-end", "id": state.active_text_id}]
    state.active_text_id = None
    return events


def convert_agent_event(event: StreamEvent, state: StreamState) -> list[dict]:
    """Convert an internal StreamEvent to a list of AI SDK wire event dicts.

    Only emits: text-start/delta/end, error, data-agent-question.
    All other event types (thinking, tool, sub-agent progress, task snapshots) are dropped.
    """
    if isinstance(event, StreamDoneEvent):
        return []
    if isinstance(event, AgentQuestionPart):
        return [
            {
                "type": "data-agent-question",
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
            }
        ]
    if isinstance(event, TextDeltaStep):
        events: list[dict] = []
        if state.active_text_id is None:
            state.active_text_id = state.next_id("text")
            events.append({"type": "text-start", "id": state.active_text_id})
        events.append({"type": "text-delta", "id": state.active_text_id, "delta": event.text_delta})
        if not event.is_streaming:
            events.extend(_close_text(state))
        return events
    if isinstance(event, FinalAnswerStep):
        if not event.final_answer:
            return []
        # Sanitize mermaid blocks to fix common LLM syntax mistakes
        # (e.g. unquoted labels with parens/braces — see mermaid-js/mermaid#7002).
        answer = sanitize_mermaid_in_markdown(event.final_answer)
        events = []
        events.extend(_close_text(state))
        text_id = state.next_id("text")
        events.append({"type": "text-start", "id": text_id})
        events.append({"type": "text-delta", "id": text_id, "delta": answer})
        events.append({"type": "text-end", "id": text_id})
        return events
    if isinstance(event, ErrorStep):
        events = []
        events.extend(_close_text(state))
        events.append({"type": "error", "errorText": event.error or "Unknown error"})
        return events
    # All other event types (ThinkingStep, ToolStartStep, ToolResultStep,
    # TaskSnapshotPart) are silently dropped.
    return []


def build_finish_events(state: StreamState) -> list[dict]:
    """Build the sequence of events that close out a stream."""
    return [*_close_text(state), {"type": "finish"}]
