"""Tests for AgentService."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.agent.memory import AgentMemory, MemoryStep, TaskStep
from rossum_agent.agent.models import (
    ErrorStep,
    FinalAnswerStep,
    StepType,
    TextDeltaStep,
    ThinkingBlockData,
    ThinkingStep,
    ToolCall,
    ToolResult,
    ToolResultStep,
    ToolStartStep,
)
from rossum_agent.api.models.schemas import (
    ImageContent,
    StepEvent,
    SubAgentProgressEvent,
    SubAgentTextEvent,
    TaskSnapshotEvent,
)
from rossum_agent.api.services.agent_service import (
    AgentService,
    _create_tool_result_event,
    _create_tool_start_event,
    _log_commit_hook,
    convert_step_to_events,
    convert_sub_agent_progress_to_event,
)
from rossum_agent.change_tracking.models import ConfigCommit, EntityChange
from rossum_agent.tools.core import SubAgentProgress, SubAgentText


class TestConvertStepToEvents:
    """Tests for convert_step_to_events function."""

    def test_convert_error_step(self):
        """Test converting error step."""
        step = ErrorStep(step_number=1, error="Something went wrong")
        events = convert_step_to_events(step)

        assert len(events) == 1
        assert events[0].type == "error"
        assert events[0].step_number == 1
        assert events[0].content == "Something went wrong"
        assert events[0].is_final is True

    def test_convert_final_answer_step(self):
        """Test converting final answer step."""
        step = FinalAnswerStep(step_number=2, final_answer="Here is your answer")
        events = convert_step_to_events(step)

        assert len(events) == 1
        assert events[0].type == "final_answer"
        assert events[0].step_number == 2
        assert events[0].content == "Here is your answer"
        assert events[0].is_final is True

    def test_convert_tool_start_step(self):
        """Test converting tool start step with current_tool."""
        step = ToolStartStep(
            step_number=1,
            tool_calls=[ToolCall(id="tc_1", name="list_annotations", arguments={"queue_id": 123})],
            tool_progress=(1, 3),
            current_tool="list_annotations",
        )
        events = convert_step_to_events(step)

        assert len(events) == 1
        assert events[0].type == "tool_start"
        assert events[0].step_number == 1
        assert events[0].tool_name == "list_annotations"
        assert events[0].tool_progress == (1, 3)
        assert events[0].tool_call_id == "tc_1"

    def test_convert_tool_result_step(self):
        """Test converting tool result step."""
        step = ToolResultStep(
            step_number=1,
            tool_calls=[ToolCall(id="call_123", name="list_annotations", arguments={})],
            tool_results=[
                ToolResult(
                    tool_call_id="call_123", name="list_annotations", content='{"annotations": []}', is_error=False
                ),
            ],
        )
        events = convert_step_to_events(step)

        assert len(events) == 1
        assert events[0].type == "tool_result"
        assert events[0].step_number == 1
        assert events[0].tool_name == "list_annotations"
        assert events[0].result == '{"annotations": []}'
        assert events[0].is_error is False
        assert events[0].tool_call_id == "call_123"

    def test_convert_tool_result_error_step(self):
        """Test converting tool result with error."""
        step = ToolResultStep(
            step_number=1,
            tool_calls=[ToolCall(id="call_456", name="get_annotation", arguments={})],
            tool_results=[
                ToolResult(
                    tool_call_id="call_456", name="get_annotation", content="Annotation not found", is_error=True
                ),
            ],
        )
        events = convert_step_to_events(step)

        assert len(events) == 1
        assert events[0].type == "tool_result"
        assert events[0].is_error is True
        assert events[0].tool_call_id == "call_456"

    def test_convert_thinking_step(self):
        """Test converting thinking step."""
        step = ThinkingStep(step_number=1, thinking="I'll help you with that...")
        events = convert_step_to_events(step)

        assert len(events) == 1
        assert events[0].type == "thinking"
        assert events[0].step_number == 1
        assert events[0].content == "I'll help you with that..."
        assert events[0].is_streaming is True

    def test_convert_thinking_step_not_streaming(self):
        """Test converting thinking step when not streaming."""
        step = ThinkingStep(step_number=1, thinking="Complete thought", is_streaming=False)
        events = convert_step_to_events(step)

        assert len(events) == 1
        assert events[0].type == "thinking"
        assert events[0].is_streaming is False

    def test_convert_intermediate_text_step(self):
        """Test converting intermediate text step."""
        step = TextDeltaStep(
            step_number=1,
            step_type=StepType.INTERMEDIATE,
            text_delta="delta",
            accumulated_text="Here is some intermediate text",
        )
        events = convert_step_to_events(step)

        assert len(events) == 1
        assert events[0].type == "intermediate"
        assert events[0].step_number == 1
        assert events[0].content == "Here is some intermediate text"
        assert events[0].is_streaming is True

    def test_convert_final_answer_streaming_text_step(self):
        """Test converting final answer streaming text step."""
        step = TextDeltaStep(
            step_number=2,
            step_type=StepType.FINAL_ANSWER,
            text_delta="delta",
            accumulated_text="Final response text",
        )
        events = convert_step_to_events(step)

        assert len(events) == 1
        assert events[0].type == "final_answer"
        assert events[0].step_number == 2
        assert events[0].content == "Final response text"
        assert events[0].is_streaming is True

    def test_convert_intermediate_text_step_finalized(self):
        """Test converting finalized intermediate text step passes is_streaming=False."""
        step = TextDeltaStep(
            step_number=1,
            step_type=StepType.INTERMEDIATE,
            text_delta="",
            accumulated_text="Intermediate text",
            is_streaming=False,
        )
        events = convert_step_to_events(step)

        assert len(events) == 1
        assert events[0].type == "intermediate"
        assert events[0].is_streaming is False

    def test_convert_final_answer_text_step_finalized(self):
        """Test converting finalized final_answer text step passes is_streaming=False."""
        step = TextDeltaStep(
            step_number=2,
            step_type=StepType.FINAL_ANSWER,
            text_delta="",
            accumulated_text="Final text",
            is_streaming=False,
        )
        events = convert_step_to_events(step)

        assert len(events) == 1
        assert events[0].type == "final_answer"
        assert events[0].is_streaming is False

    def test_convert_multi_tool_result_step(self):
        """Test that multiple tool results produce one event per result."""
        step = ToolResultStep(
            step_number=3,
            tool_calls=[
                ToolCall(id="tc_1", name="list_annotations", arguments={}),
                ToolCall(id="tc_2", name="get_queue", arguments={}),
                ToolCall(id="tc_3", name="get_annotation", arguments={}),
            ],
            tool_results=[
                ToolResult(tool_call_id="tc_1", name="list_annotations", content="result_1", is_error=False),
                ToolResult(tool_call_id="tc_2", name="get_queue", content="result_2", is_error=False),
                ToolResult(tool_call_id="tc_3", name="get_annotation", content="error_result", is_error=True),
            ],
        )
        events = convert_step_to_events(step)

        assert len(events) == 3
        assert events[0].tool_name == "list_annotations"
        assert events[0].result == "result_1"
        assert events[0].tool_call_id == "tc_1"
        assert events[0].is_error is False
        assert events[1].tool_name == "get_queue"
        assert events[1].result == "result_2"
        assert events[1].tool_call_id == "tc_2"
        assert events[1].is_error is False
        assert events[2].tool_name == "get_annotation"
        assert events[2].result == "error_result"
        assert events[2].tool_call_id == "tc_3"
        assert events[2].is_error is True
        for e in events:
            assert e.type == "tool_result"
            assert e.step_number == 3

    def test_convert_tool_start_all_tools(self):
        """Test converting tool start step with current_tool=None emits all tools."""
        step = ToolStartStep(
            step_number=1,
            tool_calls=[
                ToolCall(id="tc_1", name="list_annotations", arguments={}),
                ToolCall(id="tc_2", name="get_queue", arguments={}),
            ],
            tool_progress=(0, 2),
        )
        events = convert_step_to_events(step)

        assert len(events) == 2
        assert events[0].type == "tool_start"
        assert events[0].tool_name == "list_annotations"
        assert events[0].tool_progress == (1, 2)
        assert events[1].type == "tool_start"
        assert events[1].tool_name == "get_queue"
        assert events[1].tool_progress == (2, 2)


class TestCreateToolStartEvent:
    """Tests for _create_tool_start_event function."""

    def test_create_tool_start_event_with_tool_args(self):
        """Test creating tool start event with matching tool call args."""
        step = ToolStartStep(
            step_number=1,
            tool_calls=[
                ToolCall(id="tc_1", name="list_annotations", arguments={"queue_id": 123}),
            ],
            tool_progress=(1, 2),
            current_tool="list_annotations",
        )
        event = _create_tool_start_event(step, current_tool="list_annotations")

        assert event.type == "tool_start"
        assert event.step_number == 1
        assert event.tool_name == "list_annotations"
        assert event.tool_arguments == {"queue_id": 123}
        assert event.tool_progress == (1, 2)
        assert event.tool_call_id == "tc_1"

    def test_create_tool_start_event_no_matching_tool_call(self):
        """Test creating tool start event when tool call is not found."""
        step = ToolStartStep(
            step_number=1,
            tool_calls=[
                ToolCall(id="tc_1", name="list_annotations", arguments={"queue_id": 123}),
            ],
            tool_progress=(2, 3),
            current_tool="get_annotation",
        )
        event = _create_tool_start_event(step, current_tool="get_annotation")

        assert event.type == "tool_start"
        assert event.tool_name == "get_annotation"
        assert event.tool_arguments is None
        assert event.tool_call_id is None

    def test_create_tool_start_event_prefers_tool_call_id_for_same_name_tools(self):
        """Test that same-name tools resolve by call id, not first matching name."""
        step = ToolStartStep(
            step_number=1,
            tool_calls=[
                ToolCall(id="tc_1", name="search", arguments={"entity": "workspace"}),
                ToolCall(id="tc_2", name="search", arguments={"entity": "queue"}),
            ],
            tool_progress=(2, 2),
            current_tool="search",
            current_tool_call_id="tc_2",
        )
        event = _create_tool_start_event(step, current_tool="search")

        assert event.type == "tool_start"
        assert event.tool_name == "search"
        assert event.tool_arguments == {"entity": "queue"}
        assert event.tool_call_id == "tc_2"


class TestCreateToolResultEvent:
    """Tests for _create_tool_result_event function."""

    def test_create_tool_result_event_success(self):
        """Test creating tool result event from successful result."""
        result = ToolResult(
            tool_call_id="tc_1",
            name="list_annotations",
            content='{"annotations": [1, 2, 3]}',
            is_error=False,
        )
        event = _create_tool_result_event(1, result)

        assert event.type == "tool_result"
        assert event.step_number == 1
        assert event.tool_name == "list_annotations"
        assert event.result == '{"annotations": [1, 2, 3]}'
        assert event.is_error is False
        assert event.tool_call_id == "tc_1"

    def test_create_tool_result_event_error(self):
        """Test creating tool result event from error result."""
        result = ToolResult(
            tool_call_id="tc_2",
            name="get_annotation",
            content="Annotation not found",
            is_error=True,
        )
        event = _create_tool_result_event(2, result)

        assert event.type == "tool_result"
        assert event.step_number == 2
        assert event.tool_name == "get_annotation"
        assert event.result == "Annotation not found"
        assert event.is_error is True
        assert event.tool_call_id == "tc_2"

    def test_create_tool_result_event_emits_all_results(self):
        """Test that all tool results are emitted, not just the last one."""
        results = [
            ToolResult(tool_call_id="tc_1", name="first_tool", content="first", is_error=False),
            ToolResult(tool_call_id="tc_2", name="second_tool", content="second", is_error=False),
        ]
        events = [_create_tool_result_event(1, r) for r in results]

        assert len(events) == 2
        assert events[0].tool_name == "first_tool"
        assert events[0].result == "first"
        assert events[0].tool_call_id == "tc_1"
        assert events[1].tool_name == "second_tool"
        assert events[1].result == "second"
        assert events[1].tool_call_id == "tc_2"


class TestAgentServiceBuildUpdatedHistory:
    """Tests for build_updated_history method."""

    def test_build_history_with_response(self):
        """Test building history with final response."""
        service = AgentService()
        existing = [{"role": "user", "content": "Previous message"}]

        updated = service.build_updated_history(
            existing_history=existing, user_prompt="New question", final_response="Here is the answer"
        )

        assert len(updated) == 3
        assert updated[0] == {"role": "user", "content": "Previous message"}
        assert updated[1] == {"role": "user", "content": "New question"}
        assert updated[2] == {"role": "assistant", "content": "Here is the answer"}

    def test_build_history_without_response(self):
        """Test building history without final response."""
        service = AgentService()
        existing = []

        updated = service.build_updated_history(existing_history=existing, user_prompt="Question", final_response=None)

        assert len(updated) == 1
        assert updated[0] == {"role": "user", "content": "Question"}

    def test_build_history_does_not_mutate_original(self):
        """Test that building history doesn't mutate original list."""
        service = AgentService()
        existing = [{"role": "user", "content": "Original"}]

        updated = service.build_updated_history(
            existing_history=existing, user_prompt="New", final_response="Response"
        )

        assert len(existing) == 1
        assert len(updated) == 3


class TestAgentServiceRestoreConversationHistory:
    """Tests for _restore_conversation_history method."""

    def test_restore_user_messages(self):
        """Test restoring user messages."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [{"role": "user", "content": "Hello"}, {"role": "user", "content": "Another question"}]

        service._restore_conversation_history(mock_agent, history)

        assert mock_agent.add_user_message.call_count == 2
        mock_agent.add_user_message.assert_any_call("Hello")
        mock_agent.add_user_message.assert_any_call("Another question")

    def test_restore_assistant_messages(self):
        """Test restoring assistant messages."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [
            {"role": "assistant", "content": "Hello back"},
            {"role": "assistant", "content": "Here to help"},
        ]

        service._restore_conversation_history(mock_agent, history)

        assert mock_agent.add_assistant_message.call_count == 2

    def test_restore_mixed_messages(self):
        """Test restoring mixed user and assistant messages."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
            {"role": "assistant", "content": "Answer 2"},
        ]

        service._restore_conversation_history(mock_agent, history)

        assert mock_agent.add_user_message.call_count == 2
        assert mock_agent.add_assistant_message.call_count == 2

    def test_restore_ignores_other_roles(self):
        """Test that non-user/assistant messages are ignored."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Question"},
            {"role": "tool", "content": "Tool output"},
            {"role": "assistant", "content": "Answer"},
        ]

        service._restore_conversation_history(mock_agent, history)

        assert mock_agent.add_user_message.call_count == 1
        assert mock_agent.add_assistant_message.call_count == 1

    def test_restore_empty_history(self):
        """Test restoring empty history."""
        service = AgentService()
        mock_agent = MagicMock()

        service._restore_conversation_history(mock_agent, [])

        mock_agent.add_user_message.assert_not_called()
        mock_agent.add_assistant_message.assert_not_called()


class TestAgentServiceRestoreConversationHistoryNewFormat:
    """Tests for _restore_conversation_history with new memory format."""

    def test_restore_new_format_sets_memory_directly(self):
        """Test that new format history sets agent.memory directly."""
        service = AgentService()
        mock_agent = MagicMock()
        mock_agent.memory = AgentMemory()

        history = [
            {"type": "task_step", "task": "What is 2+2?"},
            {
                "type": "memory_step",
                "step_number": 1,
                "text": "The answer is 4.",
                "tool_calls": [],
                "tool_results": [],
                "input_tokens": 100,
                "output_tokens": 50,
            },
        ]

        service._restore_conversation_history(mock_agent, history)

        assert isinstance(mock_agent.memory, AgentMemory)
        assert len(mock_agent.memory.steps) == 2
        assert isinstance(mock_agent.memory.steps[0], TaskStep)
        assert mock_agent.memory.steps[0].task == "What is 2+2?"
        assert isinstance(mock_agent.memory.steps[1], MemoryStep)
        assert mock_agent.memory.steps[1].text == "The answer is 4."

    def test_restore_new_format_with_tool_calls(self):
        """Test restoring new format with tool calls and results."""
        service = AgentService()
        mock_agent = MagicMock()
        mock_agent.memory = AgentMemory()

        history = [
            {"type": "task_step", "task": "Get the weather"},
            {
                "type": "memory_step",
                "step_number": 1,
                "text": "Let me check the weather.",
                "tool_calls": [{"id": "tc1", "name": "get_weather", "arguments": {"city": "Prague"}}],
                "tool_results": [
                    {"tool_call_id": "tc1", "name": "get_weather", "content": "Sunny, 25C", "is_error": False}
                ],
                "input_tokens": 200,
                "output_tokens": 100,
            },
            {
                "type": "memory_step",
                "step_number": 2,
                "text": "It's sunny and 25°C in Prague.",
                "tool_calls": [],
                "tool_results": [],
            },
        ]

        service._restore_conversation_history(mock_agent, history)

        assert len(mock_agent.memory.steps) == 3
        step1 = mock_agent.memory.steps[1]
        assert len(step1.tool_calls) == 1
        assert step1.tool_calls[0].name == "get_weather"
        assert step1.tool_calls[0].arguments == {"city": "Prague"}
        assert len(step1.tool_results) == 1
        assert step1.tool_results[0].content == "Sunny, 25C"

    def test_restore_new_format_multi_turn(self):
        """Test restoring multi-turn conversation in new format."""
        service = AgentService()
        mock_agent = MagicMock()
        mock_agent.memory = AgentMemory()

        history = [
            {"type": "task_step", "task": "Hello"},
            {"type": "memory_step", "step_number": 1, "text": "Hi there!"},
            {"type": "task_step", "task": "What can you do?"},
            {"type": "memory_step", "step_number": 2, "text": "I can help with many things."},
            {"type": "task_step", "task": "Tell me a joke"},
            {"type": "memory_step", "step_number": 3, "text": "Why did the programmer quit? No arrays!"},
        ]

        service._restore_conversation_history(mock_agent, history)

        assert len(mock_agent.memory.steps) == 6
        messages = mock_agent.memory.write_to_messages()
        assert len(messages) == 6
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"

    def test_restore_detects_legacy_format(self):
        """Test that legacy format (with 'role') uses old restore method."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        service._restore_conversation_history(mock_agent, history)

        mock_agent.add_user_message.assert_called_once_with("Hello")
        mock_agent.add_assistant_message.assert_called_once_with("Hi there!")


class TestAgentServiceBuildUpdatedHistoryWithMemory:
    """Tests for build_updated_history using stored memory."""

    def test_build_history_uses_stored_memory(self):
        """Test that build_updated_history uses memory when provided."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("What is 2+2?")
        memory.steps.append(MemoryStep(step_number=1, text="The answer is 4."))

        updated = service.build_updated_history(
            existing_history=[], user_prompt="ignored", final_response="ignored", memory=memory
        )

        assert len(updated) == 2
        assert updated[0]["type"] == "task_step"
        assert updated[0]["task"] == "What is 2+2?"
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] == "The answer is 4."

    def test_build_history_preserves_tool_calls_and_results(self):
        """Test that tool calls and results are preserved in history."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("Check the weather")
        memory.steps.append(
            MemoryStep(
                step_number=1,
                text="Let me check...",
                tool_calls=[ToolCall(id="tc1", name="weather", arguments={"city": "NYC"})],
                tool_results=[ToolResult(tool_call_id="tc1", name="weather", content="Rainy")],
            )
        )
        memory.steps.append(MemoryStep(step_number=2, text="It's rainy in NYC."))

        updated = service.build_updated_history(
            existing_history=[], user_prompt="ignored", final_response="ignored", memory=memory
        )

        assert len(updated) == 3
        assert updated[0]["type"] == "task_step"
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] == "Let me check..."
        assert updated[1]["tool_calls"] == [{"id": "tc1", "name": "weather", "arguments": {"city": "NYC"}}]
        assert updated[1]["tool_results"] == [
            {"tool_call_id": "tc1", "name": "weather", "content": "Rainy", "is_error": False}
        ]
        assert updated[2]["text"] == "It's rainy in NYC."

    def test_build_history_preserves_steps_with_only_tool_calls(self):
        """Test that memory steps with tool calls but no text are preserved."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("Do something")
        memory.steps.append(
            MemoryStep(
                step_number=1,
                text=None,
                tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
                tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="result")],
            )
        )
        memory.steps.append(MemoryStep(step_number=2, text="Final answer"))

        updated = service.build_updated_history(
            existing_history=[], user_prompt="ignored", final_response="ignored", memory=memory
        )

        assert len(updated) == 3
        assert updated[0]["type"] == "task_step"
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] is None
        assert updated[1]["tool_calls"] == [{"id": "tc1", "name": "tool", "arguments": {}}]
        assert updated[1]["tool_results"] == [
            {"tool_call_id": "tc1", "name": "tool", "content": "result", "is_error": False}
        ]
        assert updated[2]["type"] == "memory_step"
        assert updated[2]["text"] == "Final answer"

    def test_build_history_preserves_steps_with_only_tool_results(self):
        """Test that memory steps with tool results but no text are preserved."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("Do something")
        memory.steps.append(
            MemoryStep(
                step_number=1,
                text=None,
                tool_calls=[],
                tool_results=[ToolResult(tool_call_id="tc1", name="tool", content="result")],
            )
        )
        memory.steps.append(MemoryStep(step_number=2, text="Final answer"))

        updated = service.build_updated_history(
            existing_history=[], user_prompt="ignored", final_response="ignored", memory=memory
        )

        assert len(updated) == 3
        assert updated[0]["type"] == "task_step"
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] is None
        assert updated[1]["tool_calls"] == []
        assert updated[1]["tool_results"] == [
            {"tool_call_id": "tc1", "name": "tool", "content": "result", "is_error": False}
        ]
        assert updated[2]["type"] == "memory_step"
        assert updated[2]["text"] == "Final answer"

    def test_build_history_falls_back_when_no_memory(self):
        """Test fallback to legacy behavior when memory is None."""
        service = AgentService()

        existing = [{"role": "user", "content": "Previous"}]
        updated = service.build_updated_history(
            existing_history=existing, user_prompt="New question", final_response="Answer"
        )

        assert len(updated) == 3
        assert updated[0] == {"role": "user", "content": "Previous"}
        assert updated[1] == {"role": "user", "content": "New question"}
        assert updated[2] == {"role": "assistant", "content": "Answer"}

    def test_build_history_preserves_thinking_blocks(self):
        """Test that thinking_blocks are preserved in lean history for extended thinking continuity."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("Analyze this document")
        memory.steps.append(
            MemoryStep(
                step_number=1,
                text="Let me analyze...",
                thinking_blocks=[
                    ThinkingBlockData(thinking="I need to consider...", signature="sig123"),
                    ThinkingBlockData(thinking="Also important...", signature="sig456"),
                ],
                tool_calls=[ToolCall(id="tc1", name="get_doc", arguments={})],
                tool_results=[ToolResult(tool_call_id="tc1", name="get_doc", content="doc content")],
            )
        )

        updated = service.build_updated_history(
            existing_history=[], user_prompt="ignored", final_response="ignored", memory=memory
        )

        assert len(updated) == 2
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] == "Let me analyze..."
        assert updated[1]["tool_calls"] == [{"id": "tc1", "name": "get_doc", "arguments": {}}]
        assert updated[1]["tool_results"] == [
            {"tool_call_id": "tc1", "name": "get_doc", "content": "doc content", "is_error": False}
        ]
        assert len(updated[1]["thinking_blocks"]) == 2
        assert updated[1]["thinking_blocks"][0]["thinking"] == "I need to consider..."
        assert updated[1]["thinking_blocks"][0]["signature"] == "sig123"

    def test_build_history_includes_step_with_only_thinking_blocks(self):
        """Test that memory steps with only thinking_blocks (no text) are preserved."""
        service = AgentService()

        memory = AgentMemory()
        memory.add_task("Process request")
        memory.steps.append(
            MemoryStep(
                step_number=1,
                text=None,
                thinking_blocks=[ThinkingBlockData(thinking="Internal reasoning", signature="sig789")],
                tool_calls=[ToolCall(id="tc1", name="tool", arguments={})],
            )
        )

        updated = service.build_updated_history(
            existing_history=[], user_prompt="ignored", final_response="ignored", memory=memory
        )

        assert len(updated) == 2
        assert updated[1]["type"] == "memory_step"
        assert updated[1]["text"] is None
        assert len(updated[1]["thinking_blocks"]) == 1
        assert updated[1]["thinking_blocks"][0]["signature"] == "sig789"


class TestAgentServiceRunAgent:
    """Tests for run_agent method."""

    @pytest.mark.asyncio
    async def test_run_agent_yields_events(self, tmp_path):
        """Test that run_agent yields step events."""
        from rossum_agent.api.models.schemas import StreamDoneEvent, TokenUsageBreakdown

        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 100
        mock_agent.tokens.total_output = 50
        mock_agent.tokens.last_main_input = 80
        mock_agent.get_token_usage_breakdown.return_value = TokenUsageBreakdown.from_raw_counts(
            total_input=100, total_output=50, main_input=100, main_output=50, sub_input=0, sub_output=0, sub_by_tool={}
        )

        async def mock_run(prompt):
            yield ThinkingStep(step_number=1, thinking="Processing...")
            yield FinalAnswerStep(step_number=1, final_answer="Done!")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(AgentService, "_try_create_config_commit", return_value=None),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            events = []
            async for event in service.run_agent(
                chat_id="test-chat",
                prompt="Test prompt",
                conversation_history=[],
                rossum_api_token="test_token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                events.append(event)

            assert len(events) == 3
            assert isinstance(events[0], StepEvent)
            assert events[0].type == "thinking"
            assert events[0].context_usage_fraction is None  # streaming events don't carry it
            assert isinstance(events[1], StepEvent)
            assert events[1].type == "final_answer"
            assert events[1].context_usage_fraction == 80 / 1_000_000
            assert isinstance(events[2], StreamDoneEvent)
            done_event = events[2]
            assert done_event.max_input_tokens == 1_000_000
            assert done_event.context_usage_fraction == 80 / 1_000_000

    @pytest.mark.asyncio
    async def test_run_agent_handles_error(self, tmp_path):
        """Test that run_agent yields error event on exception."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()

        async def mock_run(prompt):
            raise RuntimeError("Agent failed")
            yield  # pragma: no cover

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(
                AgentService,
                "_setup_change_tracking",
                new_callable=AsyncMock,
                return_value=(None, None, "https://api.rossum.ai"),
            ),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            events = []
            async for event in service.run_agent(
                chat_id="test-chat",
                prompt="Test prompt",
                conversation_history=[],
                rossum_api_token="test_token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                events.append(event)

            assert len(events) == 1
            assert isinstance(events[0], StepEvent)
            assert events[0].type == "error"
            assert "Agent failed" in events[0].content

    @pytest.mark.asyncio
    async def test_run_agent_restores_history(self, tmp_path):
        """Test that run_agent restores conversation history."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.last_main_input = 0

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(service, "_restore_conversation_history") as mock_restore,
            patch.object(
                AgentService,
                "_setup_change_tracking",
                new_callable=AsyncMock,
                return_value=(None, None, "https://api.rossum.ai"),
            ),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            async for _ in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=history,
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                pass

            mock_restore.assert_called_once_with(mock_agent, history)

    @pytest.mark.asyncio
    async def test_run_agent_creates_output_dir(self, tmp_path):
        """Test that run_agent creates and sets session output directory."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.total_cache_creation = 0
        mock_agent.tokens.total_cache_read = 0
        mock_agent.tokens.last_main_input = 0
        mock_agent.get_token_usage_breakdown.return_value = {}
        mock_agent.log_token_usage_summary = MagicMock()
        mock_agent.memory = MagicMock()

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch(
                "rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path
            ) as mock_create_dir,
            patch.object(
                AgentService,
                "_setup_change_tracking",
                new_callable=AsyncMock,
                return_value=(None, None, "https://api.rossum.ai"),
            ),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            async for _ in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                pass

            mock_create_dir.assert_called_once()
            assert service.get_output_dir("test-chat") == tmp_path

    @pytest.mark.asyncio
    async def test_run_agent_memory_available_after_run_for_pop(self, tmp_path):
        """Test that run memory remains available until consumed by pop_last_memory."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.total_cache_creation = 0
        mock_agent.tokens.total_cache_read = 0
        mock_agent.tokens.last_main_input = 0
        mock_agent.get_token_usage_breakdown.return_value = {}
        mock_agent.log_token_usage_summary = MagicMock()

        memory = AgentMemory()
        memory.add_task("Test")
        mock_agent.memory = memory

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(
                AgentService,
                "_setup_change_tracking",
                new_callable=AsyncMock,
                return_value=(None, None, "https://api.rossum.ai"),
            ),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            async for _ in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                pass

            assert service.pop_last_memory("test-chat") is memory
            assert service.pop_last_memory("test-chat") is None

    @pytest.mark.asyncio
    async def test_run_agent_seeds_last_main_input_from_previous_turn(self, tmp_path):
        """Test that last_main_input is carried forward across turns."""
        from rossum_agent.api.models.schemas import StreamDoneEvent, TokenUsageBreakdown

        service = AgentService()

        # Simulate a previous turn that ended with last_main_input = 50_000
        state = service._get_chat_run_state("test-chat")
        state.last_main_input_tokens = 50_000

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens = MagicMock()
        mock_agent.tokens.total_input = 60_000
        mock_agent.tokens.total_output = 1_000
        mock_agent.tokens.last_main_input = 60_000
        mock_agent.tokens.total_cache_creation = 0
        mock_agent.tokens.total_cache_read = 0
        mock_agent.get_token_usage_breakdown.return_value = TokenUsageBreakdown.from_raw_counts(
            total_input=60_000,
            total_output=1_000,
            main_input=60_000,
            main_output=1_000,
            sub_input=0,
            sub_output=0,
            sub_by_tool={},
        )
        mock_agent.log_token_usage_summary = MagicMock()
        mock_agent.memory = MagicMock()

        seeded_value = None

        async def mock_run(prompt):
            nonlocal seeded_value
            # Capture the seeded value before the agent's first API call overwrites it
            seeded_value = mock_agent.tokens.last_main_input
            # Simulate the agent updating last_main_input after API call
            mock_agent.tokens.last_main_input = 60_000
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(AgentService, "_try_create_config_commit", return_value=None),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            events = []
            async for event in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                events.append(event)

            # Verify seeded value was set before agent.run()
            assert seeded_value == 50_000

            # Verify last_main_input_tokens is updated after the run
            assert state.last_main_input_tokens == 60_000

            # Verify the done event carries the final context_usage_fraction
            done_event = next(e for e in events if isinstance(e, StreamDoneEvent))
            assert done_event.context_usage_fraction == 60_000 / 1_000_000

    @pytest.mark.asyncio
    async def test_register_run_clears_stale_memory(self):
        """Test that stale memory is cleared at start of a new run."""
        service = AgentService()
        state = service._get_chat_run_state("test-chat")
        state.last_memory = AgentMemory()

        run_id = await service._register_run("test-chat")
        assert state.last_memory is None

        await service._clear_run("test-chat", run_id)

    def test_output_dir_initially_none(self):
        """Test that output_dir is None before running agent."""
        service = AgentService()
        assert service.get_output_dir("test-chat") is None


class TestAgentServiceBuildUserContent:
    """Tests for AgentService._build_user_content method."""

    def test_text_only_returns_string(self):
        """Test that text-only prompt returns a plain string."""
        service = AgentService()
        result = service._build_user_content("Hello, agent!", None)
        assert result == "Hello, agent!"
        assert isinstance(result, str)

    def test_with_images_returns_list(self):
        """Test that prompt with images returns a content list."""
        service = AgentService()
        images = [ImageContent(media_type="image/png", data="aGVsbG8=")]
        result = service._build_user_content("Analyze this", images)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["type"] == "image"
        assert result[0]["source"]["type"] == "base64"
        assert result[0]["source"]["media_type"] == "image/png"
        assert result[0]["source"]["data"] == "aGVsbG8="
        assert result[1]["type"] == "text"
        assert result[1]["text"] == "Analyze this"

    def test_with_multiple_images(self):
        """Test that multiple images are included in correct order."""
        service = AgentService()
        images = [
            ImageContent(media_type="image/png", data="aW1hZ2Ux"),
            ImageContent(media_type="image/jpeg", data="aW1hZ2Uy"),
        ]
        result = service._build_user_content("Compare these images", images)

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]["source"]["data"] == "aW1hZ2Ux"
        assert result[1]["source"]["data"] == "aW1hZ2Uy"
        assert result[2]["text"] == "Compare these images"

    def test_empty_images_list_returns_string(self):
        """Test that empty images list returns plain string."""
        service = AgentService()
        result = service._build_user_content("Hello", [])
        assert result == "Hello"
        assert isinstance(result, str)


class TestAgentServiceBuildUpdatedHistoryWithImages:
    """Tests for build_updated_history with images."""

    def test_build_history_with_images(self):
        """Test building history with images included."""
        service = AgentService()

        existing = [{"role": "user", "content": "Previous message"}]
        images = [ImageContent(media_type="image/png", data="aGVsbG8=")]

        updated = service.build_updated_history(
            existing_history=existing,
            user_prompt="Analyze this image",
            final_response="Analysis complete",
            images=images,
        )

        assert len(updated) == 3
        assert updated[0] == {"role": "user", "content": "Previous message"}
        assert isinstance(updated[1]["content"], list)
        assert len(updated[1]["content"]) == 2
        assert updated[1]["content"][0]["type"] == "image"
        assert updated[1]["content"][0]["source"]["data"] == "aGVsbG8="
        assert updated[1]["content"][1]["type"] == "text"
        assert updated[1]["content"][1]["text"] == "Analyze this image"
        assert updated[2] == {"role": "assistant", "content": "Analysis complete"}

    def test_build_history_without_images(self):
        """Test building history without images returns text-only content."""
        service = AgentService()

        existing = []

        updated = service.build_updated_history(
            existing_history=existing, user_prompt="Text only", final_response="Response", images=None
        )

        assert len(updated) == 2
        assert updated[0] == {"role": "user", "content": "Text only"}


class TestAgentServiceParseStoredContent:
    """Tests for _parse_stored_content method."""

    def test_parse_string_content(self):
        """Test parsing string content returns string."""
        service = AgentService()
        result = service._parse_stored_content("Hello, world!")
        assert result == "Hello, world!"

    def test_parse_multimodal_content(self):
        """Test parsing multimodal content with images and text."""
        service = AgentService()
        stored_content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": "aGVsbG8=",
                },
            },
            {"type": "text", "text": "Analyze this"},
        ]

        result = service._parse_stored_content(stored_content)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["type"] == "image"
        assert result[0]["source"]["type"] == "base64"
        assert result[0]["source"]["media_type"] == "image/png"
        assert result[0]["source"]["data"] == "aGVsbG8="
        assert result[1]["type"] == "text"
        assert result[1]["text"] == "Analyze this"

    def test_parse_empty_list_returns_empty_string(self):
        """Test parsing empty list returns empty string."""
        service = AgentService()
        result = service._parse_stored_content([])
        assert result == ""

    def test_parse_unknown_block_types_ignored(self):
        """Test that unknown block types are ignored."""
        service = AgentService()
        stored_content = [
            {"type": "unknown", "data": "something"},
            {"type": "text", "text": "Valid text"},
        ]

        result = service._parse_stored_content(stored_content)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "text"


class TestAgentServiceRestoreConversationHistoryWithImages:
    """Tests for _restore_conversation_history with multimodal content."""

    def test_restore_multimodal_user_message(self):
        """Test restoring user messages with images."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": "aGVsbG8="},
                    },
                    {"type": "text", "text": "What's in this image?"},
                ],
            },
            {"role": "assistant", "content": "I see a document."},
        ]

        service._restore_conversation_history(mock_agent, history)

        mock_agent.add_user_message.assert_called_once()
        call_args = mock_agent.add_user_message.call_args[0][0]
        assert isinstance(call_args, list)
        assert len(call_args) == 2
        assert call_args[0]["type"] == "image"
        assert call_args[1]["type"] == "text"
        mock_agent.add_assistant_message.assert_called_once_with("I see a document.")

    def test_restore_mixed_text_and_multimodal_messages(self):
        """Test restoring a mix of text-only and multimodal messages."""
        service = AgentService()
        mock_agent = MagicMock()

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "img1"}},
                    {"type": "text", "text": "What's this?"},
                ],
            },
            {"role": "assistant", "content": "That's a chart."},
        ]

        service._restore_conversation_history(mock_agent, history)

        assert mock_agent.add_user_message.call_count == 2
        assert mock_agent.add_assistant_message.call_count == 2

        first_call = mock_agent.add_user_message.call_args_list[0][0][0]
        assert first_call == "Hello"

        second_call = mock_agent.add_user_message.call_args_list[1][0][0]
        assert isinstance(second_call, list)
        assert len(second_call) == 2


class TestConvertSubAgentProgressToEvent:
    """Tests for convert_sub_agent_progress_to_event function."""

    def test_convert_sub_agent_progress(self):
        """Test converting SubAgentProgress to SubAgentProgressEvent."""
        progress = SubAgentProgress(
            tool_name="analyze_hook",
            iteration=2,
            max_iterations=5,
            current_tool="read_file",
            tool_calls=["grep", "read_file", "write_file"],
            status="running",
        )

        event = convert_sub_agent_progress_to_event(progress)

        assert isinstance(event, SubAgentProgressEvent)
        assert event.tool_name == "analyze_hook"
        assert event.iteration == 2
        assert event.max_iterations == 5
        assert event.current_tool == "read_file"
        assert event.tool_calls == ["grep", "read_file", "write_file"]
        assert event.status == "running"


class TestAgentServiceSubAgentCallbacks:
    """Tests for sub-agent callback handling.

    Callbacks use call_soon_threadsafe to marshal events onto the event loop,
    so tests must be async and allow time for the scheduled callback to run.
    """

    async def test_on_sub_agent_progress_with_queue(self):
        """Test _on_sub_agent_progress puts event on queue."""
        from rossum_agent.api.services.agent_service import _request_context, _RequestContext

        service = AgentService()
        ctx = _RequestContext()
        ctx.event_queue = asyncio.Queue(maxsize=100)
        ctx.event_loop = asyncio.get_running_loop()
        _request_context.set(ctx)

        progress = SubAgentProgress(
            tool_name="test_tool",
            iteration=1,
            max_iterations=3,
            current_tool="grep",
            tool_calls=["grep", "read_file"],
            status="running",
        )

        service._on_sub_agent_progress(progress)
        await asyncio.sleep(0)

        assert ctx.event_queue.qsize() == 1
        event = ctx.event_queue.get_nowait()
        assert isinstance(event, SubAgentProgressEvent)
        assert event.tool_name == "test_tool"

    def test_on_sub_agent_progress_without_queue(self):
        """Test _on_sub_agent_progress does nothing when queue is None."""
        from rossum_agent.api.services.agent_service import _request_context, _RequestContext

        service = AgentService()
        ctx = _RequestContext()
        ctx.event_queue = None
        _request_context.set(ctx)

        progress = SubAgentProgress(
            tool_name="test_tool",
            iteration=1,
            max_iterations=3,
            current_tool="grep",
            tool_calls=["grep"],
            status="running",
        )

        service._on_sub_agent_progress(progress)

    async def test_on_sub_agent_progress_queue_full(self, caplog):
        """Test _on_sub_agent_progress logs warning when queue is full."""

        from rossum_agent.api.services.agent_service import _request_context, _RequestContext

        service = AgentService()
        ctx = _RequestContext()
        ctx.event_queue = asyncio.Queue(maxsize=1)
        ctx.event_loop = asyncio.get_running_loop()
        _request_context.set(ctx)

        ctx.event_queue.put_nowait(
            SubAgentProgressEvent(
                tool_name="existing", iteration=1, max_iterations=1, tool_calls=["tool"], status="running"
            )
        )

        progress = SubAgentProgress(
            tool_name="new_tool",
            iteration=1,
            max_iterations=3,
            current_tool="grep",
            tool_calls=["grep"],
            status="running",
        )

        with caplog.at_level(logging.WARNING):
            service._on_sub_agent_progress(progress)
            await asyncio.sleep(0)

        assert "queue full" in caplog.text.lower()

    async def test_on_sub_agent_text_with_queue(self):
        """Test _on_sub_agent_text puts event on queue."""
        from rossum_agent.api.services.agent_service import _request_context, _RequestContext

        service = AgentService()
        ctx = _RequestContext()
        ctx.event_queue = asyncio.Queue(maxsize=100)
        ctx.event_loop = asyncio.get_running_loop()
        _request_context.set(ctx)

        text = SubAgentText(tool_name="analyze_hook", text="Analyzing...", is_final=False)

        service._on_sub_agent_text(text)
        await asyncio.sleep(0)

        assert ctx.event_queue.qsize() == 1
        event = ctx.event_queue.get_nowait()
        assert isinstance(event, SubAgentTextEvent)
        assert event.tool_name == "analyze_hook"
        assert event.text == "Analyzing..."
        assert event.is_final is False

    def test_on_sub_agent_text_without_queue(self):
        """Test _on_sub_agent_text does nothing when queue is None."""
        from rossum_agent.api.services.agent_service import _request_context, _RequestContext

        service = AgentService()
        ctx = _RequestContext()
        ctx.event_queue = None
        _request_context.set(ctx)

        text = SubAgentText(tool_name="test_tool", text="Hello", is_final=True)

        service._on_sub_agent_text(text)

    async def test_on_sub_agent_text_queue_full(self, caplog):
        """Test _on_sub_agent_text logs warning when queue is full."""

        from rossum_agent.api.services.agent_service import _request_context, _RequestContext

        service = AgentService()
        ctx = _RequestContext()
        ctx.event_queue = asyncio.Queue(maxsize=1)
        ctx.event_loop = asyncio.get_running_loop()
        _request_context.set(ctx)

        ctx.event_queue.put_nowait(SubAgentTextEvent(tool_name="existing", text="x", is_final=False))

        text = SubAgentText(tool_name="new_tool", text="Hello", is_final=True)

        with caplog.at_level(logging.WARNING):
            service._on_sub_agent_text(text)
            await asyncio.sleep(0)

        assert "queue full" in caplog.text.lower()

    async def test_on_task_snapshot_with_queue(self):
        """Test _on_task_snapshot puts TaskSnapshotEvent on queue."""
        from rossum_agent.api.services.agent_service import _request_context, _RequestContext

        service = AgentService()
        ctx = _RequestContext()
        ctx.event_queue = asyncio.Queue(maxsize=100)
        ctx.event_loop = asyncio.get_running_loop()
        _request_context.set(ctx)

        snapshot = [{"id": "1", "subject": "Deploy", "status": "completed"}]
        service._on_task_snapshot(snapshot)
        await asyncio.sleep(0)

        assert ctx.event_queue.qsize() == 1
        event = ctx.event_queue.get_nowait()
        assert isinstance(event, TaskSnapshotEvent)
        assert event.tasks == snapshot

    def test_on_task_snapshot_without_queue(self):
        """Test _on_task_snapshot does nothing when queue is None."""
        from rossum_agent.api.services.agent_service import _request_context, _RequestContext

        service = AgentService()
        ctx = _RequestContext()
        ctx.event_queue = None
        _request_context.set(ctx)

        service._on_task_snapshot([{"id": "1", "subject": "Task", "status": "pending"}])

    async def test_on_task_snapshot_queue_full(self, caplog):
        """Test _on_task_snapshot logs warning when queue is full."""

        from rossum_agent.api.services.agent_service import _request_context, _RequestContext

        service = AgentService()
        ctx = _RequestContext()
        ctx.event_queue = asyncio.Queue(maxsize=1)
        ctx.event_loop = asyncio.get_running_loop()
        _request_context.set(ctx)

        ctx.event_queue.put_nowait(TaskSnapshotEvent(tasks=[]))

        with caplog.at_level(logging.WARNING):
            service._on_task_snapshot([{"id": "1", "subject": "Task", "status": "pending"}])
            await asyncio.sleep(0)

        assert "queue full" in caplog.text.lower()


class TestAgentServiceRunAgentWithImages:
    """Tests for run_agent with images parameter."""

    @pytest.mark.asyncio
    async def test_run_agent_logs_image_count(self, tmp_path, caplog):
        """Test that run_agent logs the number of images."""

        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.last_main_input = 0

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        images = [
            ImageContent(media_type="image/png", data="aW1hZ2Ux"),
            ImageContent(media_type="image/jpeg", data="aW1hZ2Uy"),
        ]

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(
                AgentService,
                "_setup_change_tracking",
                new_callable=AsyncMock,
                return_value=(None, None, "https://api.rossum.ai"),
            ),
            caplog.at_level(logging.INFO),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            async for _ in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
                images=images,
            ):
                pass

        assert "2 images" in caplog.text


class TestAgentServiceUrlContext:
    """Tests for URL context handling in run_agent."""

    @pytest.mark.asyncio
    async def test_run_agent_with_url_context(self, tmp_path):
        """Test that run_agent appends URL context to system prompt."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.last_main_input = 0

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch("rossum_agent.api.services.agent_service.get_system_prompt", return_value="Base prompt"),
            patch("rossum_agent.api.services.agent_service.extract_url_context") as mock_extract,
            patch("rossum_agent.api.services.agent_service.format_context_for_prompt", return_value="URL context"),
            patch.object(
                AgentService,
                "_setup_change_tracking",
                new_callable=AsyncMock,
                return_value=(None, None, "https://api.rossum.ai"),
            ),
        ):
            mock_url_context = MagicMock()
            mock_url_context.is_empty.return_value = False
            mock_extract.return_value = mock_url_context

            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            async for _ in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
                rossum_url="https://elis.rossum.ai/annotations/123",
            ):
                pass

            call_kwargs = mock_create_agent.call_args
            assert "URL context" in call_kwargs.kwargs["system_prompt"]


class TestAfterLoopHook:
    """Tests for the log_commit hook invocation."""

    @pytest.mark.asyncio
    async def test_log_commit_hook_no_changes(self):
        commit = ConfigCommit(
            hash="deadbeef1234",
            chat_id="test",
            timestamp=datetime.now(),
            message="Updated queue settings",
            user_request="Update settings",
            environment="https://api.rossum.ai",
            changes=[],
        )
        result = await _log_commit_hook(commit)
        assert result == "✓ deadbeef — Updated queue settings"

    async def test_log_commit_hook_with_changes(self):
        commit = ConfigCommit(
            hash="cafebabe5678",
            chat_id="test",
            timestamp=datetime.now(),
            message="Configured schema",
            user_request="Configure",
            environment="https://api.rossum.ai",
            changes=[
                EntityChange(
                    entity_type="queue",
                    entity_id="1",
                    entity_name="Main Queue",
                    operation="update",
                    before={},
                    after={},
                ),
                EntityChange(
                    entity_type="schema",
                    entity_id="2",
                    entity_name="Invoice",
                    operation="create",
                    before=None,
                    after={},
                ),
                EntityChange(
                    entity_type="hook",
                    entity_id="3",
                    entity_name="Old Hook",
                    operation="delete",
                    before={},
                    after=None,
                ),
            ],
        )
        result = await _log_commit_hook(commit)
        assert result is not None
        lines = result.splitlines()
        assert lines[0] == "✓ cafebabe — Configured schema"
        assert lines[1] == '  [~] queue "Main Queue"'
        assert lines[2] == '  [+] schema "Invoice"'
        assert lines[3] == '  [-] hook "Old Hook"'

    @pytest.mark.asyncio
    async def test_run_agent_calls_hook_on_commit(self, tmp_path):
        """Test that the log_commit hook is called when a commit is created."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.total_cache_creation = 0
        mock_agent.tokens.total_cache_read = 0
        mock_agent.tokens.last_main_input = 0
        mock_agent.get_token_usage_breakdown.return_value = {}
        mock_agent.log_token_usage_summary = MagicMock()
        mock_agent.memory = MagicMock()

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        fake_commit = ConfigCommit(
            hash="abc123",
            chat_id="test-chat",
            timestamp=datetime.now(),
            message="Updated schema",
            user_request="Update schema",
            environment="https://api.rossum.ai",
            changes=[],
        )

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(AgentService, "_try_create_config_commit", return_value=fake_commit),
            patch.object(
                AgentService,
                "_setup_change_tracking",
                new_callable=AsyncMock,
                return_value=(MagicMock(), MagicMock(), "https://api.rossum.ai"),
            ),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            events = []
            async for event in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                events.append(event)

        # Hook output is yielded as a StepEvent before StreamDoneEvent
        hook_events = [e for e in events if isinstance(e, StepEvent) and e.is_hook_output]
        assert len(hook_events) == 1
        assert hook_events[0].type == "final_answer"
        assert "abc123" in hook_events[0].content
        assert hook_events[0].is_final is True

    @pytest.mark.asyncio
    async def test_run_agent_skips_hook_when_no_commit(self, tmp_path):
        """Test that hook output is not emitted when no commit is created."""
        service = AgentService()

        mock_mcp_connection = MagicMock()
        mock_agent = MagicMock()
        mock_agent.tokens.total_input = 0
        mock_agent.tokens.total_output = 0
        mock_agent.tokens.total_cache_creation = 0
        mock_agent.tokens.total_cache_read = 0
        mock_agent.tokens.last_main_input = 0
        mock_agent.get_token_usage_breakdown.return_value = {}
        mock_agent.log_token_usage_summary = MagicMock()
        mock_agent.memory = MagicMock()

        async def mock_run(prompt):
            yield FinalAnswerStep(step_number=1, final_answer="Done")

        mock_agent.run = mock_run

        with (
            patch("rossum_agent.api.services.agent_service.connect_mcp_server") as mock_connect,
            patch("rossum_agent.api.services.agent_service.create_agent") as mock_create_agent,
            patch("rossum_agent.api.services.agent_service.create_session_output_dir", return_value=tmp_path),
            patch.object(AgentService, "_try_create_config_commit", return_value=None),
            patch.object(
                AgentService,
                "_setup_change_tracking",
                new_callable=AsyncMock,
                return_value=(MagicMock(), MagicMock(), "https://api.rossum.ai"),
            ),
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_mcp_connection)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_create_agent.return_value = mock_agent

            events = []
            async for event in service.run_agent(
                chat_id="test-chat",
                prompt="Test",
                conversation_history=[],
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ):
                events.append(event)

        hook_events = [e for e in events if isinstance(e, StepEvent) and e.is_hook_output]
        assert len(hook_events) == 0


class TestResolveCautiousPreapprovals:
    """Test AgentService._resolve_cautious_preapprovals."""

    def test_empty_pending_returns_empty(self):
        result = AgentService._resolve_cautious_preapprovals(set(), "Yes, proceed")
        assert result == set()

    def test_approval_returns_pending_copy(self):
        pending = {"update_queue", "delete_workspace"}
        result = AgentService._resolve_cautious_preapprovals(pending, "1. Do you want?\nYes, proceed")
        assert result == pending
        assert result is not pending  # must be a copy

    def test_no_answer_returns_empty(self):
        pending = {"update_queue"}
        result = AgentService._resolve_cautious_preapprovals(pending, "1. Do you want?\nNo, cancel")
        assert result == set()

    def test_chat_answer_returns_empty(self):
        pending = {"update_queue"}
        result = AgentService._resolve_cautious_preapprovals(pending, "1. Do you want?\nLet me provide context")
        assert result == set()

    def test_freeform_answer_returns_empty(self):
        pending = {"update_queue"}
        result = AgentService._resolve_cautious_preapprovals(pending, "I'd rather not do this right now")
        assert result == set()
