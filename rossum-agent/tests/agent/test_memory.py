"""Tests for rossum_agent.agent.memory module."""

from __future__ import annotations

from rossum_agent.agent.memory import AgentMemory, MemoryStep, TaskStep
from rossum_agent.agent.models import ToolCall, ToolResult


class TestMemoryStep:
    """Test MemoryStep to_messages conversion."""

    def test_to_messages_with_tool_calls_and_text(self):
        """Test that tool calls with text include text block first."""
        step = MemoryStep(
            step_number=1,
            text="Analyzing the data...",
            tool_calls=[ToolCall(id="tc1", name="get_data", arguments={"key": "value"})],
            tool_results=[ToolResult(tool_call_id="tc1", name="get_data", content="result")],
        )

        messages = step.to_messages()

        assert len(messages) == 2
        assert messages[0]["role"] == "assistant"
        assert len(messages[0]["content"]) == 2
        assert messages[0]["content"][0]["type"] == "text"
        assert messages[0]["content"][0]["text"] == "Analyzing the data..."
        assert messages[0]["content"][1]["type"] == "tool_use"
        assert messages[0]["content"][1]["id"] == "tc1"
        assert messages[0]["content"][1]["name"] == "get_data"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"][0]["type"] == "tool_result"

    def test_to_messages_with_tool_calls_no_text(self):
        """Test that tool calls without text only include tool_use blocks."""
        step = MemoryStep(
            step_number=1,
            tool_calls=[ToolCall(id="tc1", name="list_items", arguments={})],
            tool_results=[ToolResult(tool_call_id="tc1", name="list_items", content="items")],
        )

        messages = step.to_messages()

        assert len(messages) == 2
        assert len(messages[0]["content"]) == 1
        assert messages[0]["content"][0]["type"] == "tool_use"

    def test_to_messages_with_multiple_tool_calls(self):
        """Test conversion with multiple tool calls."""
        step = MemoryStep(
            step_number=1,
            tool_calls=[
                ToolCall(id="tc1", name="tool_a", arguments={"a": 1}),
                ToolCall(id="tc2", name="tool_b", arguments={"b": 2}),
            ],
            tool_results=[
                ToolResult(tool_call_id="tc1", name="tool_a", content="result_a"),
                ToolResult(tool_call_id="tc2", name="tool_b", content="result_b"),
            ],
        )

        messages = step.to_messages()

        assert len(messages) == 2
        assert len(messages[0]["content"]) == 2
        assert len(messages[1]["content"]) == 2

    def test_to_messages_text_only(self):
        """Test that text-only step returns assistant message with string content."""
        step = MemoryStep(step_number=1, text="Final answer here.")

        messages = step.to_messages()

        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"] == "Final answer here."

    def test_to_messages_empty_step(self):
        """Test that empty step returns no messages."""
        step = MemoryStep(step_number=1)

        messages = step.to_messages()

        assert messages == []

    def test_to_messages_tool_result_includes_error_flag(self):
        """Test that tool result includes is_error flag."""
        step = MemoryStep(
            step_number=1,
            tool_calls=[ToolCall(id="tc1", name="failing_tool", arguments={})],
            tool_results=[ToolResult(tool_call_id="tc1", name="failing_tool", content="Error", is_error=True)],
        )

        messages = step.to_messages()

        assert messages[1]["content"][0]["is_error"] is True


class TestMemoryStepSerialization:
    """Test MemoryStep serialization methods."""

    def test_to_dict_simple(self):
        """Test serializing simple MemoryStep."""
        step = MemoryStep(step_number=1, text="Hello", input_tokens=10, output_tokens=5)

        result = step.to_dict()

        assert result["type"] == "memory_step"
        assert result["step_number"] == 1
        assert result["text"] == "Hello"
        assert result["tool_calls"] == []
        assert result["tool_results"] == []
        assert result["input_tokens"] == 10
        assert result["output_tokens"] == 5

    def test_to_dict_with_tool_calls(self):
        """Test serializing MemoryStep with tool calls."""
        step = MemoryStep(
            step_number=2,
            tool_calls=[ToolCall(id="tc1", name="test", arguments={"key": "val"})],
            tool_results=[ToolResult(tool_call_id="tc1", name="test", content="output")],
        )

        result = step.to_dict()

        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "tc1"
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["tool_call_id"] == "tc1"

    def test_from_dict(self):
        """Test deserializing MemoryStep."""
        data = {
            "type": "memory_step",
            "step_number": 3,
            "text": "Thinking...",
            "tool_calls": [{"id": "tc1", "name": "tool", "arguments": {}}],
            "tool_results": [{"tool_call_id": "tc1", "name": "tool", "content": "done", "is_error": False}],
            "input_tokens": 100,
            "output_tokens": 50,
        }

        step = MemoryStep.from_dict(data)

        assert step.step_number == 3
        assert step.text == "Thinking..."
        assert len(step.tool_calls) == 1
        assert step.tool_calls[0].id == "tc1"
        assert len(step.tool_results) == 1
        assert step.input_tokens == 100
        assert step.output_tokens == 50

    def test_from_dict_with_defaults(self):
        """Test deserializing MemoryStep with missing optional fields."""
        data = {"type": "memory_step"}

        step = MemoryStep.from_dict(data)

        assert step.step_number == 0
        assert step.text is None
        assert step.tool_calls == []
        assert step.tool_results == []
        assert step.input_tokens == 0
        assert step.output_tokens == 0

    def test_roundtrip(self):
        """Test serialization roundtrip preserves data."""
        original = MemoryStep(
            step_number=5,
            text="Processing",
            tool_calls=[ToolCall(id="tc1", name="complex", arguments={"nested": {"a": 1}})],
            tool_results=[ToolResult(tool_call_id="tc1", name="complex", content="result", is_error=False)],
            input_tokens=200,
            output_tokens=100,
        )

        restored = MemoryStep.from_dict(original.to_dict())

        assert restored.step_number == original.step_number
        assert restored.text == original.text
        assert len(restored.tool_calls) == len(original.tool_calls)
        assert restored.tool_calls[0].id == original.tool_calls[0].id
        assert restored.input_tokens == original.input_tokens
        assert restored.output_tokens == original.output_tokens


class TestTaskStep:
    """Test TaskStep to_messages conversion."""

    def test_to_messages_text_content(self):
        """Test TaskStep with text content."""
        step = TaskStep(task="Analyze this document")

        messages = step.to_messages()

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Analyze this document"

    def test_to_messages_multimodal_content(self):
        """Test TaskStep with multimodal content (image + text)."""
        content_blocks: list[dict] = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "abc123"}},
            {"type": "text", "text": "What is in this image?"},
        ]
        step = TaskStep(task=content_blocks)

        messages = step.to_messages()

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert isinstance(messages[0]["content"], list)
        assert len(messages[0]["content"]) == 2
        assert messages[0]["content"][0]["type"] == "image"
        assert messages[0]["content"][1]["type"] == "text"
        assert messages[0]["content"][1]["text"] == "What is in this image?"


class TestTaskStepSerialization:
    """Test TaskStep serialization methods."""

    def test_to_dict_text(self):
        """Test serializing TaskStep with text."""
        step = TaskStep(task="Process invoice")

        result = step.to_dict()

        assert result == {"type": "task_step", "task": "Process invoice"}

    def test_to_dict_multimodal(self):
        """Test serializing TaskStep with multimodal content."""
        content_blocks: list[dict] = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "xyz"}},
            {"type": "text", "text": "Extract data"},
        ]
        step = TaskStep(task=content_blocks)

        result = step.to_dict()

        assert result["type"] == "task_step"
        assert len(result["task"]) == 2
        assert result["task"][0]["type"] == "image"
        assert result["task"][1]["type"] == "text"

    def test_from_dict_text(self):
        """Test deserializing TaskStep with text."""
        data = {"type": "task_step", "task": "Hello world"}

        step = TaskStep.from_dict(data)

        assert step.task == "Hello world"

    def test_from_dict_multimodal(self):
        """Test deserializing TaskStep with multimodal content."""
        data = {
            "type": "task_step",
            "task": [
                {"type": "text", "text": "Describe this"},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "data"}},
            ],
        }

        step = TaskStep.from_dict(data)

        assert isinstance(step.task, list)
        assert len(step.task) == 2

    def test_roundtrip_text(self):
        """Test serialization roundtrip with text."""
        original = TaskStep(task="Analyze document")
        restored = TaskStep.from_dict(original.to_dict())

        assert restored.task == original.task

    def test_roundtrip_multimodal(self):
        """Test serialization roundtrip with multimodal content."""
        original = TaskStep(
            task=[
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "abc"}},
                {"type": "text", "text": "What is this?"},
            ]
        )
        restored = TaskStep.from_dict(original.to_dict())

        assert restored.task == original.task


class TestAgentMemory:
    """Test AgentMemory functionality."""

    def test_reset_clears_steps(self):
        """Test that reset clears all steps."""
        memory = AgentMemory()
        memory.add_task("Task 1")
        memory.add_step(MemoryStep(step_number=1, text="Step 1"))

        memory.reset()

        assert memory.steps == []

    def test_add_task(self):
        """Test adding a task."""
        memory = AgentMemory()
        memory.add_task("Process this document")

        assert len(memory.steps) == 1
        assert isinstance(memory.steps[0], TaskStep)
        assert memory.steps[0].task == "Process this document"

    def test_add_task_multimodal(self):
        """Test adding a multimodal task."""
        memory = AgentMemory()
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "img"}},
            {"type": "text", "text": "Analyze"},
        ]
        memory.add_task(content)

        assert len(memory.steps) == 1
        assert isinstance(memory.steps[0], TaskStep)
        assert isinstance(memory.steps[0].task, list)

    def test_add_step(self):
        """Test adding a memory step."""
        memory = AgentMemory()
        step = MemoryStep(step_number=1, text="Thinking...")
        memory.add_step(step)

        assert len(memory.steps) == 1
        assert memory.steps[0] is step

    def test_write_to_messages_empty(self):
        """Test write_to_messages with empty memory."""
        memory = AgentMemory()

        messages = memory.write_to_messages()

        assert messages == []

    def test_write_to_messages_single_task(self):
        """Test write_to_messages with single task."""
        memory = AgentMemory()
        memory.add_task("Do something")

        messages = memory.write_to_messages()

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Do something"

    def test_write_to_messages_full_conversation(self):
        """Test write_to_messages with task and steps."""
        memory = AgentMemory()
        memory.add_task("Analyze data")
        memory.add_step(
            MemoryStep(
                step_number=1,
                tool_calls=[ToolCall(id="tc1", name="fetch", arguments={})],
                tool_results=[ToolResult(tool_call_id="tc1", name="fetch", content="data")],
            )
        )
        memory.add_step(MemoryStep(step_number=2, text="Here is the analysis."))

        messages = memory.write_to_messages()

        assert len(messages) == 4
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert messages[3]["role"] == "assistant"


class TestAgentMemorySerialization:
    """Test AgentMemory serialization methods."""

    def test_to_dict_empty(self):
        """Test serializing empty memory."""
        memory = AgentMemory()

        result = memory.to_dict()

        assert result == []

    def test_to_dict_with_steps(self):
        """Test serializing memory with steps."""
        memory = AgentMemory()
        memory.add_task("Start task")
        memory.add_step(MemoryStep(step_number=1, text="Done"))

        result = memory.to_dict()

        assert len(result) == 2
        assert result[0]["type"] == "task_step"
        assert result[1]["type"] == "memory_step"

    def test_from_dict_empty(self):
        """Test deserializing empty memory."""
        memory = AgentMemory.from_dict([])

        assert memory.steps == []

    def test_from_dict_with_steps(self):
        """Test deserializing memory with steps."""
        data = [
            {"type": "task_step", "task": "Process"},
            {
                "type": "memory_step",
                "step_number": 1,
                "text": "Processed",
                "tool_calls": [],
                "tool_results": [],
                "input_tokens": 10,
                "output_tokens": 5,
            },
        ]

        memory = AgentMemory.from_dict(data)

        assert len(memory.steps) == 2
        assert isinstance(memory.steps[0], TaskStep)
        assert isinstance(memory.steps[1], MemoryStep)

    def test_from_dict_ignores_unknown_types(self):
        """Test that unknown step types are ignored."""
        data = [
            {"type": "task_step", "task": "Test"},
            {"type": "unknown_step", "data": "ignored"},
            {"type": "memory_step", "step_number": 1},
        ]

        memory = AgentMemory.from_dict(data)

        assert len(memory.steps) == 2

    def test_roundtrip(self):
        """Test serialization roundtrip preserves data."""
        original = AgentMemory()
        original.add_task("Initial task")
        original.add_step(
            MemoryStep(
                step_number=1,
                text="Thinking",
                tool_calls=[ToolCall(id="tc1", name="analyze", arguments={"x": 1})],
                tool_results=[ToolResult(tool_call_id="tc1", name="analyze", content="result")],
                input_tokens=50,
                output_tokens=25,
            )
        )
        original.add_step(MemoryStep(step_number=2, text="Final answer"))

        restored = AgentMemory.from_dict(original.to_dict())

        assert len(restored.steps) == len(original.steps)
        assert isinstance(restored.steps[0], TaskStep)
        assert isinstance(restored.steps[1], MemoryStep)
        assert isinstance(restored.steps[2], MemoryStep)
        assert restored.steps[1].tool_calls[0].name == "analyze"

    def test_roundtrip_multimodal(self):
        """Test serialization roundtrip with multimodal content."""
        original = AgentMemory()
        original.add_task(
            [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "abc"}},
                {"type": "text", "text": "Describe this image"},
            ]
        )

        restored = AgentMemory.from_dict(original.to_dict())

        assert len(restored.steps) == 1
        assert isinstance(restored.steps[0], TaskStep)
        assert isinstance(restored.steps[0].task, list)
        assert len(restored.steps[0].task) == 2
