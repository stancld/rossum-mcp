"""Tests for simplified stream adapter (AI SDK UI Message Stream)."""

from __future__ import annotations

import json

from rossum_agent.agent.models import (
    AgentQuestionPart,
    ErrorStep,
    FileCreatedPart,
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
        assert types == ["reasoning-end", "data-final-answer"]

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

    def test_final_answer_emits_data_event(self):
        """FinalAnswerStep emits data-final-answer (not text-* events)."""
        state = StreamState()
        events = convert_agent_event(FinalAnswerStep(step_number=2, final_answer="Done!"), state)
        assert len(events) == 1
        assert events[0]["type"] == "data-final-answer"
        assert events[0]["data"]["text"] == "Done!"

    def test_final_answer_empty_content_skipped(self):
        state = StreamState()
        events = convert_agent_event(FinalAnswerStep(step_number=2, final_answer=""), state)
        assert events == []

    def test_final_answer_closes_active_text_block(self):
        """When text was already streamed, FinalAnswerStep closes the block then emits data event."""
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
        assert types == ["text-end", "data-final-answer"]

    def test_hook_output_emits_data_event(self):
        """Hook output FinalAnswerStep also emits data-final-answer."""
        state = StreamState()
        events = convert_agent_event(
            FinalAnswerStep(step_number=2, final_answer="Commit summary", is_hook_output=True),
            state,
        )
        assert len(events) == 1
        assert events[0]["type"] == "data-final-answer"
        assert events[0]["data"]["text"] == "Commit summary"


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


class TestTaskSnapshotConversion:
    def test_task_snapshot_emitted(self):
        state = StreamState()
        part = TaskSnapshotPart(
            tasks=[TaskSnapshotTask(id="1", subject="Deploy schema", status=TaskStatus.COMPLETED, description="Done")]
        )
        events = convert_agent_event(part, state)
        assert len(events) == 1
        assert events[0]["type"] == "data-task-snapshot"
        assert len(events[0]["data"]["tasks"]) == 1
        task = events[0]["data"]["tasks"][0]
        assert task == {"id": "1", "subject": "Deploy schema", "status": "completed", "description": "Done"}

    def test_task_snapshot_multiple_tasks(self):
        state = StreamState()
        part = TaskSnapshotPart(
            tasks=[
                TaskSnapshotTask(id="1", subject="Analyze queue", status=TaskStatus.COMPLETED),
                TaskSnapshotTask(id="2", subject="Deploy schema", status=TaskStatus.IN_PROGRESS),
                TaskSnapshotTask(id="3", subject="Verify results", status=TaskStatus.PENDING),
            ]
        )
        events = convert_agent_event(part, state)
        assert len(events) == 1
        assert len(events[0]["data"]["tasks"]) == 3
        assert events[0]["data"]["tasks"][0]["status"] == "completed"
        assert events[0]["data"]["tasks"][1]["status"] == "in_progress"
        assert events[0]["data"]["tasks"][2]["status"] == "pending"

    def test_task_snapshot_empty_tasks(self):
        state = StreamState()
        part = TaskSnapshotPart(tasks=[])
        events = convert_agent_event(part, state)
        assert len(events) == 1
        assert events[0]["data"]["tasks"] == []


class TestFileCreatedConversion:
    def test_file_created_emitted(self):
        state = StreamState()
        part = FileCreatedPart(filename="report.csv", url="/api/v1/chats/c1/files/report.csv")
        events = convert_agent_event(part, state)
        assert len(events) == 1
        assert events[0]["type"] == "data-file-created"
        assert events[0]["data"] == {"filename": "report.csv", "url": "/api/v1/chats/c1/files/report.csv"}

    def test_multiple_files(self):
        state = StreamState()
        for name in ["a.csv", "b.png"]:
            events = convert_agent_event(
                FileCreatedPart(filename=name, url=f"/api/v1/chats/c1/files/{name}"),
                state,
            )
            assert len(events) == 1
            assert events[0]["data"]["filename"] == name


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
        assert len(events[0]["data"]["questions"]) == 1
        assert events[0]["data"]["questions"][0]["question"] == "Which queue?"
        assert events[0]["data"]["questions"][0]["options"][0]["value"] == "q1"


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

    def test_finish_only_emits_finish(self):
        """build_finish_events only closes open blocks and emits finish — no usage/file/commit events."""
        state = StreamState()
        events = build_finish_events(state)
        types = [e["type"] for e in events]
        assert types == ["finish"]
