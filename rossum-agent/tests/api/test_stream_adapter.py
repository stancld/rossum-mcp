"""Tests for simplified stream adapter (AI SDK UI Message Stream)."""

from __future__ import annotations

import json

from rossum_agent.agent.models import (
    AgentQuestionPart,
    ErrorStep,
    FinalAnswerStep,
    ReasoningStep,
    StepType,
    TaskSnapshotPart,
    TaskSnapshotTask,
    TaskStatus,
    TextDeltaStep,
    ToolCall,
    ToolResult,
    ToolResultStep,
    ToolStartStep,
)
from rossum_agent.api.models.schemas import (
    AgentQuestionItemSchema,
    QuestionOptionSchema,
    StreamDoneEvent,
)
from rossum_agent.api.routes.messages import STREAM_DONE, _format_sse
from rossum_agent.api.routes.stream_adapter import (
    StreamState,
    build_finish_events,
    convert_agent_event,
)


class TestFormatSSE:
    def test_basic_serialization(self):
        event = {"type": "text-delta", "id": "text_1", "delta": "hello"}
        result = _format_sse(event)
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        payload = json.loads(result[len("data: ") : -2])
        assert payload["type"] == "text-delta"
        assert payload["delta"] == "hello"

    def test_stream_done_sentinel(self):
        assert STREAM_DONE == "data: [DONE]\n\n"


class TestStreamLifecycle:
    def test_finish_events_minimal(self):
        state = StreamState()
        events = build_finish_events(state)
        assert len(events) == 1
        assert events[0]["type"] == "finish"

    def test_finish_events_close_open_text_block(self):
        state = StreamState()
        convert_agent_event(
            TextDeltaStep(
                step_number=1,
                step_type=StepType.FINAL_ANSWER,
                text_delta="Hello",
                accumulated_text="Hello",
                is_streaming=True,
            ),
            state,
        )
        events = build_finish_events(state)
        assert events[0]["type"] == "text-end"
        assert events[-1]["type"] == "finish"

    def test_finish_events_close_open_reasoning_block(self):
        state = StreamState()
        convert_agent_event(
            ReasoningStep(step_number=1, reasoning="Thinking...", is_streaming=True),
            state,
        )
        events = build_finish_events(state)
        assert events[0]["type"] == "reasoning-end"
        assert events[-1]["type"] == "finish"


class TestReasoningConversion:
    def test_reasoning_opens_block(self):
        state = StreamState()
        events = convert_agent_event(
            ReasoningStep(step_number=1, reasoning="Let me think...", is_streaming=True),
            state,
        )
        assert len(events) == 2
        assert events[0]["type"] == "reasoning-start"
        assert events[1]["type"] == "reasoning-delta"
        assert events[1]["delta"] == "Let me think..."

    def test_reasoning_accumulates_deltas(self):
        state = StreamState()
        convert_agent_event(
            ReasoningStep(step_number=1, reasoning="Hello", is_streaming=True),
            state,
        )
        events = convert_agent_event(
            ReasoningStep(step_number=1, reasoning="Hello world", is_streaming=True),
            state,
        )
        assert len(events) == 1
        assert events[0]["type"] == "reasoning-delta"
        assert events[0]["delta"] == " world"

    def test_reasoning_finalized_closes_block(self):
        state = StreamState()
        events = convert_agent_event(
            ReasoningStep(step_number=1, reasoning="Done thinking", is_streaming=False),
            state,
        )
        types = [e["type"] for e in events]
        assert types == ["reasoning-start", "reasoning-delta", "reasoning-end"]

    def test_reasoning_closed_by_text_delta(self):
        state = StreamState()
        convert_agent_event(
            ReasoningStep(step_number=1, reasoning="Thinking...", is_streaming=True),
            state,
        )
        assert state.active_reasoning_id is not None
        events = convert_agent_event(
            TextDeltaStep(
                step_number=1,
                step_type=StepType.INTERMEDIATE,
                text_delta="Hello",
                accumulated_text="Hello",
                is_streaming=True,
            ),
            state,
        )
        assert events[0]["type"] == "reasoning-end"
        assert events[1]["type"] == "text-start"
        assert events[2]["type"] == "text-delta"

    def test_reasoning_closed_by_tool_start(self):
        state = StreamState()
        convert_agent_event(
            ReasoningStep(step_number=1, reasoning="Thinking...", is_streaming=True),
            state,
        )
        events = convert_agent_event(
            ToolStartStep(
                step_number=1,
                tool_calls=[ToolCall(id="tc_1", name="search", arguments={})],
                tool_progress=(0, 1),
            ),
            state,
        )
        assert events[0]["type"] == "reasoning-end"
        assert events[1]["type"] == "tool-input-start"

    def test_reasoning_closed_by_error(self):
        state = StreamState()
        convert_agent_event(
            ReasoningStep(step_number=1, reasoning="Thinking...", is_streaming=True),
            state,
        )
        events = convert_agent_event(ErrorStep(step_number=1, error="Failed"), state)
        assert events[0]["type"] == "reasoning-end"
        assert events[1]["type"] == "error"

    def test_reasoning_closed_by_final_answer(self):
        state = StreamState()
        convert_agent_event(
            ReasoningStep(step_number=1, reasoning="Thinking...", is_streaming=True),
            state,
        )
        events = convert_agent_event(FinalAnswerStep(step_number=2, final_answer="Done!"), state)
        types = [e["type"] for e in events]
        assert types == ["reasoning-end", "text-start", "text-delta", "text-end"]

    def test_no_delta_when_no_new_content(self):
        state = StreamState()
        convert_agent_event(
            ReasoningStep(step_number=1, reasoning="Hello", is_streaming=True),
            state,
        )
        events = convert_agent_event(
            ReasoningStep(step_number=1, reasoning="Hello", is_streaming=True),
            state,
        )
        assert events == []


class TestTextConversion:
    def test_text_delta_opens_text_block(self):
        state = StreamState()
        events = convert_agent_event(
            TextDeltaStep(
                step_number=1,
                step_type=StepType.INTERMEDIATE,
                text_delta="Processing...",
                accumulated_text="Processing...",
                is_streaming=True,
            ),
            state,
        )
        assert len(events) == 2
        assert events[0]["type"] == "text-start"
        assert events[1]["type"] == "text-delta"
        assert events[1]["delta"] == "Processing..."

    def test_text_delta_continues_block(self):
        state = StreamState()
        convert_agent_event(
            TextDeltaStep(
                step_number=1,
                step_type=StepType.INTERMEDIATE,
                text_delta="Hello",
                accumulated_text="Hello",
                is_streaming=True,
            ),
            state,
        )
        events = convert_agent_event(
            TextDeltaStep(
                step_number=1,
                step_type=StepType.INTERMEDIATE,
                text_delta=" world",
                accumulated_text="Hello world",
                is_streaming=True,
            ),
            state,
        )
        assert len(events) == 1
        assert events[0]["type"] == "text-delta"
        assert events[0]["delta"] == " world"

    def test_text_delta_finalized_closes_block(self):
        state = StreamState()
        events = convert_agent_event(
            TextDeltaStep(
                step_number=1,
                step_type=StepType.INTERMEDIATE,
                text_delta="Done",
                accumulated_text="Done",
                is_streaming=False,
            ),
            state,
        )
        types = [e["type"] for e in events]
        assert types == ["text-start", "text-delta", "text-end"]

    def test_final_answer_opens_text_block(self):
        state = StreamState()
        events = convert_agent_event(FinalAnswerStep(step_number=2, final_answer="Done!"), state)
        assert events[0]["type"] == "text-start"
        assert events[1]["type"] == "text-delta"
        assert events[1]["delta"] == "Done!"
        assert events[2]["type"] == "text-end"

    def test_final_answer_empty_content_skipped(self):
        state = StreamState()
        events = convert_agent_event(FinalAnswerStep(step_number=2, final_answer=""), state)
        assert events == []

    def test_final_answer_closes_active_text_block(self):
        state = StreamState()
        convert_agent_event(
            TextDeltaStep(
                step_number=1,
                step_type=StepType.INTERMEDIATE,
                text_delta="Thinking...",
                accumulated_text="Thinking...",
                is_streaming=True,
            ),
            state,
        )
        assert state.active_text_id is not None
        events = convert_agent_event(FinalAnswerStep(step_number=2, final_answer="Done!"), state)
        types = [e["type"] for e in events]
        assert types == ["text-end", "text-start", "text-delta", "text-end"]


class TestErrorConversion:
    def test_error_emits_error_event(self):
        state = StreamState()
        events = convert_agent_event(ErrorStep(step_number=1, error="Something broke"), state)
        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert events[0]["errorText"] == "Something broke"

    def test_error_empty_content(self):
        state = StreamState()
        events = convert_agent_event(ErrorStep(step_number=1, error=""), state)
        assert events[0]["errorText"] == "Unknown error"

    def test_error_closes_open_text_block(self):
        state = StreamState()
        convert_agent_event(
            TextDeltaStep(
                step_number=1,
                step_type=StepType.INTERMEDIATE,
                text_delta="...",
                accumulated_text="...",
                is_streaming=True,
            ),
            state,
        )
        events = convert_agent_event(ErrorStep(step_number=2, error="Failed"), state)
        assert events[0]["type"] == "text-end"
        assert events[1]["type"] == "error"


class TestToolConversion:
    def test_tool_start_emits_input_events(self):
        state = StreamState()
        events = convert_agent_event(
            ToolStartStep(
                step_number=1,
                tool_calls=[ToolCall(id="tc_1", name="search", arguments={"query": "users"})],
                tool_progress=(0, 1),
                current_tool="search",
            ),
            state,
        )
        assert len(events) == 2
        assert events[0] == {"type": "tool-input-start", "toolCallId": "tc_1", "toolName": "search"}
        assert events[1] == {
            "type": "tool-input-available",
            "toolCallId": "tc_1",
            "toolName": "search",
            "input": {"query": "users"},
        }

    def test_tool_start_multiple_calls(self):
        state = StreamState()
        events = convert_agent_event(
            ToolStartStep(
                step_number=1,
                tool_calls=[
                    ToolCall(id="tc_1", name="search", arguments={"q": "a"}),
                    ToolCall(id="tc_2", name="list_users", arguments={}),
                ],
                tool_progress=(0, 2),
            ),
            state,
        )
        types = [e["type"] for e in events]
        assert types == ["tool-input-start", "tool-input-available", "tool-input-start", "tool-input-available"]
        assert events[0]["toolCallId"] == "tc_1"
        assert events[2]["toolCallId"] == "tc_2"

    def test_tool_start_deduplicates_repeated_emissions(self):
        state = StreamState()
        tool_calls = [ToolCall(id="tc_1", name="search", arguments={})]
        convert_agent_event(
            ToolStartStep(step_number=1, tool_calls=tool_calls, tool_progress=(0, 1)),
            state,
        )
        events = convert_agent_event(
            ToolStartStep(step_number=1, tool_calls=tool_calls, tool_progress=(0, 1), current_tool="search"),
            state,
        )
        assert events == []

    def test_tool_start_closes_active_text_block(self):
        state = StreamState()
        convert_agent_event(
            TextDeltaStep(
                step_number=1,
                step_type=StepType.INTERMEDIATE,
                text_delta="Thinking...",
                accumulated_text="Thinking...",
                is_streaming=True,
            ),
            state,
        )
        assert state.active_text_id is not None
        events = convert_agent_event(
            ToolStartStep(
                step_number=2,
                tool_calls=[ToolCall(id="tc_1", name="search", arguments={})],
                tool_progress=(0, 1),
            ),
            state,
        )
        assert events[0]["type"] == "text-end"
        assert events[1]["type"] == "tool-input-start"

    def test_tool_result_emits_output_event(self):
        state = StreamState()
        events = convert_agent_event(
            ToolResultStep(
                step_number=1,
                tool_calls=[ToolCall(id="tc_1", name="search", arguments={})],
                tool_results=[ToolResult(tool_call_id="tc_1", name="search", content="found 3 results")],
            ),
            state,
        )
        assert len(events) == 1
        assert events[0] == {
            "type": "tool-output-available",
            "toolCallId": "tc_1",
            "output": "found 3 results",
        }

    def test_tool_result_multiple_results(self):
        state = StreamState()
        events = convert_agent_event(
            ToolResultStep(
                step_number=1,
                tool_calls=[
                    ToolCall(id="tc_1", name="search", arguments={}),
                    ToolCall(id="tc_2", name="list_users", arguments={}),
                ],
                tool_results=[
                    ToolResult(tool_call_id="tc_1", name="search", content="result1"),
                    ToolResult(tool_call_id="tc_2", name="list_users", content="result2"),
                ],
            ),
            state,
        )
        assert len(events) == 2
        assert events[0]["toolCallId"] == "tc_1"
        assert events[1]["toolCallId"] == "tc_2"

    def test_full_tool_lifecycle(self):
        """ToolStart → ToolResult produces the full AI SDK tool event sequence."""
        state = StreamState()
        tc = ToolCall(id="tc_1", name="get_queue", arguments={"id": 42})
        start_events = convert_agent_event(
            ToolStartStep(step_number=1, tool_calls=[tc], tool_progress=(0, 1)),
            state,
        )
        result_events = convert_agent_event(
            ToolResultStep(
                step_number=1,
                tool_calls=[tc],
                tool_results=[ToolResult(tool_call_id="tc_1", name="get_queue", content='{"name":"invoices"}')],
            ),
            state,
        )
        all_types = [e["type"] for e in start_events + result_events]
        assert all_types == ["tool-input-start", "tool-input-available", "tool-output-available"]


class TestDroppedEvents:
    def test_task_snapshot_dropped(self):
        state = StreamState()
        part = TaskSnapshotPart(
            tasks=[TaskSnapshotTask(id="1", subject="Deploy schema", status=TaskStatus.COMPLETED, description="Done")]
        )
        events = convert_agent_event(part, state)
        assert events == []

    def test_stream_done_event_dropped(self):
        state = StreamState()
        events = convert_agent_event(
            StreamDoneEvent(total_steps=5, input_tokens=1000, output_tokens=500),
            state,
        )
        assert events == []


class TestAgentQuestionConversion:
    def test_agent_question_emitted(self):
        state = StreamState()
        part = AgentQuestionPart(
            questions=[
                AgentQuestionItemSchema(
                    question="Which queue?",
                    options=[QuestionOptionSchema(value="q1", label="Queue 1", description="First queue")],
                    multi_select=False,
                )
            ]
        )
        events = convert_agent_event(part, state)
        assert len(events) == 1
        assert events[0]["type"] == "data-agent-question"
        assert len(events[0]["questions"]) == 1
        assert events[0]["questions"][0]["question"] == "Which queue?"
        assert events[0]["questions"][0]["options"][0]["value"] == "q1"


class TestFinishEvents:
    def test_without_done_event(self):
        state = StreamState()
        events = build_finish_events(state)
        assert len(events) == 1
        assert events[0]["type"] == "finish"

    def test_closes_open_text_block(self):
        state = StreamState()
        convert_agent_event(
            TextDeltaStep(
                step_number=1,
                step_type=StepType.FINAL_ANSWER,
                text_delta="Hello",
                accumulated_text="Hello",
                is_streaming=True,
            ),
            state,
        )
        events = build_finish_events(state)
        assert events[0]["type"] == "text-end"
        assert events[-1]["type"] == "finish"

    def test_no_usage_or_file_events(self):
        state = StreamState()
        state.done_event = StreamDoneEvent(
            total_steps=5,
            input_tokens=1000,
            output_tokens=500,
            config_commit_hash="abc123",
        )
        events = build_finish_events(state)
        types = [e["type"] for e in events]
        assert "data-usage" not in types
        assert "data-file-created" not in types
        assert "data-commit-info" not in types
        assert types == ["finish"]
