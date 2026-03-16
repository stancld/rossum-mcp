"""Tests for rossum_agent.agent.tool_execution module."""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.agent import (
    AgentConfig,
    MemoryStep,
    RossumAgent,
    ToolCall,
    ToolResult,
)
from rossum_agent.agent.models import (
    ToolResultStep,
    ToolStartStep,
)
from rossum_agent.agent.tool_execution import (
    _parse_json_encoded_strings,
    execute_tool_with_progress,
    execute_tools_with_progress,
    serialize_tool_result,
)


class TestParseJsonEncodedStrings:
    """Test _parse_json_encoded_strings function for handling LLM double-encoded arguments."""

    def test_parses_json_encoded_list(self):
        """Test that JSON-encoded list strings are parsed to actual lists."""
        arguments = {"fields_to_keep": '["field_a", "field_b", "field_c"]'}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"fields_to_keep": ["field_a", "field_b", "field_c"]}

    def test_parses_json_encoded_dict(self):
        """Test that JSON-encoded dict strings are parsed to actual dicts."""
        arguments = {"config": '{"key": "value", "count": 5}'}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"config": {"key": "value", "count": 5}}

    def test_preserves_non_json_strings(self):
        """Test that regular strings are preserved unchanged."""
        arguments = {"name": "test_value", "path": "/some/path"}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"name": "test_value", "path": "/some/path"}

    def test_preserves_actual_lists_and_dicts(self):
        """Test that actual lists and dicts are preserved unchanged."""
        arguments = {"items": ["a", "b"], "config": {"x": 1}}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"items": ["a", "b"], "config": {"x": 1}}

    def test_handles_mixed_arguments(self):
        """Test handling mix of JSON-encoded and normal arguments."""
        arguments = {"schema_id": 123, "fields_to_keep": '["document_id", "date_issue"]', "name": "test"}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"schema_id": 123, "fields_to_keep": ["document_id", "date_issue"], "name": "test"}

    def test_handles_invalid_json_gracefully(self):
        """Test that invalid JSON strings are preserved unchanged."""
        arguments = {"value": "[invalid json"}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"value": "[invalid json"}

    def test_handles_nested_dicts(self):
        """Test that nested dicts are processed recursively."""
        arguments = {"outer": {"inner_list": '["a", "b"]'}}
        result = _parse_json_encoded_strings(arguments)
        assert result == {"outer": {"inner_list": ["a", "b"]}}

    def test_preserves_json_primitive_strings(self):
        """Test that JSON strings encoding primitives are preserved."""
        arguments = {"value": '"just a string"', "number": "42"}
        result = _parse_json_encoded_strings(arguments)
        # Only list/dict JSON should be parsed, primitives preserved
        assert result["number"] == "42"
        assert result["value"] == '"just a string"'

    def test_preserves_changes_parameter_as_string(self):
        """Test that 'changes' parameter is not parsed even if it's valid JSON.

        The 'changes' parameter should remain as a JSON string because some tools
        expect it in that format (e.g., patch_schema).
        """
        arguments = {"changes": '[{"op": "add", "path": "/fields/-", "value": {"name": "new_field"}}]'}
        result = _parse_json_encoded_strings(arguments)
        # changes should stay as a string, not be parsed to a list
        assert isinstance(result["changes"], str)
        assert result["changes"] == arguments["changes"]

    def test_parses_non_changes_json_lists(self):
        """Test that other JSON lists are parsed but 'changes' is preserved."""
        arguments = {
            "changes": '["item1", "item2"]',
            "fields_to_keep": '["field_a", "field_b"]',
        }
        result = _parse_json_encoded_strings(arguments)
        # changes stays as string
        assert isinstance(result["changes"], str)
        # fields_to_keep is parsed
        assert result["fields_to_keep"] == ["field_a", "field_b"]


class TestToolCallFingerprint:
    """Test _tool_call_fingerprint function."""

    def test_same_call_same_fingerprint(self):
        """Identical tool calls produce the same fingerprint."""
        from rossum_agent.agent.tool_execution import _tool_call_fingerprint

        tc1 = ToolCall(id="tc_1", name="search", arguments={"entity": "workspace"})
        tc2 = ToolCall(id="tc_2", name="search", arguments={"entity": "workspace"})

        assert _tool_call_fingerprint(tc1) == _tool_call_fingerprint(tc2)

    def test_different_args_different_fingerprint(self):
        """Tool calls with different arguments produce different fingerprints."""
        from rossum_agent.agent.tool_execution import _tool_call_fingerprint

        tc1 = ToolCall(id="tc_1", name="search", arguments={"entity": "workspace"})
        tc2 = ToolCall(id="tc_2", name="search", arguments={"entity": "queue"})

        assert _tool_call_fingerprint(tc1) != _tool_call_fingerprint(tc2)

    def test_different_name_different_fingerprint(self):
        """Tool calls with different names produce different fingerprints."""
        from rossum_agent.agent.tool_execution import _tool_call_fingerprint

        tc1 = ToolCall(id="tc_1", name="search", arguments={})
        tc2 = ToolCall(id="tc_2", name="list_queues", arguments={})

        assert _tool_call_fingerprint(tc1) != _tool_call_fingerprint(tc2)

    def test_fingerprint_ignores_id(self):
        """Fingerprint does not include the tool call ID."""
        from rossum_agent.agent.tool_execution import _tool_call_fingerprint

        tc1 = ToolCall(id="different_id_1", name="tool", arguments={"x": 1})
        tc2 = ToolCall(id="different_id_2", name="tool", arguments={"x": 1})

        assert _tool_call_fingerprint(tc1) == _tool_call_fingerprint(tc2)


class TestDeduplicateToolCalls:
    """Test _deduplicate_tool_calls function."""

    def test_no_duplicates(self):
        """All unique calls are preserved."""
        from rossum_agent.agent.tool_execution import _deduplicate_tool_calls

        tool_calls = [
            ToolCall(id="tc_1", name="tool_a", arguments={"x": 1}),
            ToolCall(id="tc_2", name="tool_b", arguments={"y": 2}),
        ]

        deduped, dupes_map = _deduplicate_tool_calls(tool_calls, step_num=1)

        assert len(deduped) == 2
        assert dupes_map["tc_1"] == []
        assert dupes_map["tc_2"] == []

    def test_removes_duplicates(self):
        """Duplicate calls are removed; primary call kept."""
        from rossum_agent.agent.tool_execution import _deduplicate_tool_calls

        tool_calls = [
            ToolCall(id="tc_1", name="search", arguments={"q": "test"}),
            ToolCall(id="tc_2", name="search", arguments={"q": "test"}),
            ToolCall(id="tc_3", name="search", arguments={"q": "test"}),
        ]

        deduped, dupes_map = _deduplicate_tool_calls(tool_calls, step_num=1)

        assert len(deduped) == 1
        assert deduped[0].id == "tc_1"
        assert len(dupes_map["tc_1"]) == 2
        assert dupes_map["tc_1"][0].id == "tc_2"
        assert dupes_map["tc_1"][1].id == "tc_3"

    def test_mixed_unique_and_duplicates(self):
        """Mix of unique and duplicate calls is handled correctly."""
        from rossum_agent.agent.tool_execution import _deduplicate_tool_calls

        tool_calls = [
            ToolCall(id="tc_1", name="search", arguments={"q": "a"}),
            ToolCall(id="tc_2", name="list_queues", arguments={}),
            ToolCall(id="tc_3", name="search", arguments={"q": "a"}),
        ]

        deduped, _dupes_map = _deduplicate_tool_calls(tool_calls, step_num=1)

        assert len(deduped) == 2
        assert {tc.name for tc in deduped} == {"search", "list_queues"}


class TestSchemaStagger:
    """Test _SchemaStagger class."""

    @pytest.mark.asyncio
    async def test_no_delay_for_non_schema_tools(self):
        """Non-schema tools get no delay."""
        from rossum_agent.agent.tool_execution import _SchemaStagger

        stagger = _SchemaStagger()
        start = time.monotonic()
        await stagger.maybe_delay("list_queues")
        elapsed = time.monotonic() - start

        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_first_schema_call_has_no_delay(self):
        """First schema call gets no stagger delay."""
        from rossum_agent.agent.tool_execution import _SchemaStagger

        stagger = _SchemaStagger()
        start = time.monotonic()
        await stagger.maybe_delay("patch_schema")
        elapsed = time.monotonic() - start

        assert elapsed < 0.1
        assert stagger._counter == 1

    @pytest.mark.asyncio
    async def test_second_schema_call_has_delay(self):
        """Second schema call gets 0.5s delay."""
        from rossum_agent.agent.tool_execution import _SchemaStagger

        stagger = _SchemaStagger()
        await stagger.maybe_delay("patch_schema")

        start = time.monotonic()
        await stagger.maybe_delay("patch_schema_with_subagent")
        elapsed = time.monotonic() - start

        assert elapsed >= 0.4  # Allow small timing tolerance
        assert stagger._counter == 2

    @pytest.mark.asyncio
    async def test_counter_increments_only_for_schema_tools(self):
        """Counter only increments for schema tools."""
        from rossum_agent.agent.tool_execution import _SchemaStagger

        stagger = _SchemaStagger()
        await stagger.maybe_delay("list_queues")
        await stagger.maybe_delay("list_queues")

        assert stagger._counter == 0


class TestDrainTokenQueue:
    """Test drain_token_queue function."""

    def test_drains_all_pending_tokens(self):
        """All token usage entries are drained and accumulated."""
        import queue as queue_mod

        from rossum_agent.agent.tool_execution import drain_token_queue
        from rossum_agent.tools.core import SubAgentTokenUsage

        mock_tokens = MagicMock()
        mock_tokens.total_input = 0
        mock_tokens.total_output = 0

        token_queue: queue_mod.Queue[SubAgentTokenUsage] = queue_mod.Queue()
        token_queue.put(SubAgentTokenUsage(tool_name="tool_a", iteration=1, input_tokens=100, output_tokens=50))
        token_queue.put(SubAgentTokenUsage(tool_name="tool_b", iteration=1, input_tokens=200, output_tokens=100))

        drain_token_queue(mock_tokens, token_queue)

        assert mock_tokens.accumulate_sub.call_count == 2
        assert token_queue.empty()

    def test_handles_empty_queue(self):
        """Does not error on empty queue."""
        import queue as queue_mod

        from rossum_agent.agent.tool_execution import drain_token_queue

        mock_tokens = MagicMock()
        token_queue: queue_mod.Queue = queue_mod.Queue()

        drain_token_queue(mock_tokens, token_queue)

        mock_tokens.accumulate_sub.assert_not_called()


class TestExecuteTool:
    """Test RossumAgent._execute_tool_with_progress method."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent with mocked dependencies."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        mock_mcp_connection.get_tools.return_value = []
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    async def _get_final_result(self, agent: RossumAgent, tool_call: ToolCall) -> ToolResult:
        """Helper to get the final ToolResult from execute_tool_with_progress."""
        result = None
        async for item in execute_tool_with_progress(
            tool_call, 1, [tool_call], (1, 1), agent.mcp_connection, agent.tokens
        ):
            if isinstance(item, ToolResult):
                result = item
        assert result is not None
        return result

    @pytest.mark.asyncio
    async def test_executes_internal_tool(self):
        """Test that internal tools are executed locally."""
        agent = self._create_agent()

        tool_call = ToolCall(
            id="tc_1",
            name="write_file",
            arguments={"filename": "test.txt", "content": "Hello"},
        )

        with patch("rossum_agent.agent.tool_execution.execute_internal_tool", return_value="Success") as mock_execute:
            result = await self._get_final_result(agent, tool_call)

        mock_execute.assert_called_once()
        assert result.content == "Success"
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_executes_mcp_tool(self):
        """Test that MCP tools are called via MCP connection."""
        agent = self._create_agent()
        agent.mcp_connection.call_tool.return_value = {"queues": ["q1", "q2"]}

        tool_call = ToolCall(
            id="tc_1",
            name="list_queues",
            arguments={"workspace_url": "https://example.com"},
        )

        result = await self._get_final_result(agent, tool_call)

        agent.mcp_connection.call_tool.assert_called_once_with("list_queues", {"workspace_url": "https://example.com"})
        assert "queues" in result.content
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_handles_tool_execution_error(self):
        """Test that tool execution errors are handled gracefully."""
        agent = self._create_agent()
        agent.mcp_connection.call_tool.side_effect = Exception("Connection failed")

        tool_call = ToolCall(
            id="tc_1",
            name="failing_tool",
            arguments={},
        )

        result = await self._get_final_result(agent, tool_call)

        assert result.is_error is True
        assert "Connection failed" in result.content

    @pytest.mark.asyncio
    async def test_spills_long_content_to_file(self):
        """Test that long tool output is spilled to a workspace file."""
        agent = self._create_agent()
        long_output = "A" * 50000
        agent.mcp_connection.call_tool.return_value = long_output

        tool_call = ToolCall(id="tc_1", name="verbose_tool", arguments={})

        result = await self._get_final_result(agent, tool_call)

        assert len(result.content) < 50000
        assert "result saved to" in result.content.lower()
        assert "workspace" in result.content.lower()


class TestExecuteToolsInParallel:
    """Test RossumAgent._execute_tools_with_progress parallel execution."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent with mocked dependencies."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        mock_mcp_connection.get_tools.return_value = []
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    @pytest.mark.asyncio
    async def test_executes_multiple_tools_in_parallel(self):
        """Test that multiple tools are executed concurrently."""
        agent = self._create_agent()

        execution_times: list[float] = []

        async def slow_tool(*args, **kwargs):
            execution_times.append(time.monotonic())
            await asyncio.sleep(0.1)
            return "result"

        agent.mcp_connection.call_tool = slow_tool

        tool_calls = [
            ToolCall(id="tc_1", name="tool_a", arguments={}),
            ToolCall(id="tc_2", name="tool_b", arguments={}),
            ToolCall(id="tc_3", name="tool_c", arguments={}),
        ]

        steps = []
        async for s in execute_tools_with_progress(
            agent.mcp_connection,
            agent.tokens,
            agent.memory,
            step_num=1,
            response_text="",
            tool_calls=tool_calls,
            input_tokens=100,
            output_tokens=50,
        ):
            steps.append(s)

        # All tools should have started at nearly the same time (parallel execution)
        assert len(execution_times) == 3
        time_spread = max(execution_times) - min(execution_times)
        # If parallel, all should start within 50ms of each other
        assert time_spread < 0.05

    @pytest.mark.asyncio
    async def test_preserves_tool_result_order(self):
        """Test that tool results are returned in the same order as tool calls."""
        agent = self._create_agent()

        async def varying_delay_tool(name, args):
            # Make each tool take different time to complete
            delays = {"fast_tool": 0.01, "medium_tool": 0.05, "slow_tool": 0.1}
            await asyncio.sleep(delays.get(name, 0.01))
            return f"result_{name}"

        agent.mcp_connection.call_tool = varying_delay_tool

        tool_calls = [
            ToolCall(id="tc_1", name="slow_tool", arguments={}),
            ToolCall(id="tc_2", name="fast_tool", arguments={}),
            ToolCall(id="tc_3", name="medium_tool", arguments={}),
        ]

        final_step = None
        async for s in execute_tools_with_progress(
            agent.mcp_connection,
            agent.tokens,
            agent.memory,
            step_num=1,
            response_text="",
            tool_calls=tool_calls,
            input_tokens=100,
            output_tokens=50,
        ):
            final_step = s

        # Results should be in same order as tool_calls, regardless of completion order
        assert final_step is not None
        assert len(final_step.tool_results) == 3
        assert final_step.tool_results[0].tool_call_id == "tc_1"
        assert final_step.tool_results[1].tool_call_id == "tc_2"
        assert final_step.tool_results[2].tool_call_id == "tc_3"

    @pytest.mark.asyncio
    async def test_handles_tool_error_in_parallel_execution(self):
        """Test that errors in one tool don't affect other parallel tools."""
        agent = self._create_agent()

        async def mixed_tool(name, args):
            if name == "failing_tool":
                raise Exception("Tool failed")
            return f"success_{name}"

        agent.mcp_connection.call_tool = mixed_tool

        tool_calls = [
            ToolCall(id="tc_1", name="good_tool", arguments={}),
            ToolCall(id="tc_2", name="failing_tool", arguments={}),
            ToolCall(id="tc_3", name="another_good_tool", arguments={}),
        ]

        final_step = None
        async for s in execute_tools_with_progress(
            agent.mcp_connection,
            agent.tokens,
            agent.memory,
            step_num=1,
            response_text="",
            tool_calls=tool_calls,
            input_tokens=100,
            output_tokens=50,
        ):
            final_step = s

        assert final_step is not None
        assert len(final_step.tool_results) == 3
        # First tool succeeded
        assert final_step.tool_results[0].is_error is False
        # Second tool failed
        assert final_step.tool_results[1].is_error is True
        assert "Tool failed" in final_step.tool_results[1].content
        # Third tool succeeded
        assert final_step.tool_results[2].is_error is False

    @pytest.mark.asyncio
    async def test_yields_progress_steps_during_parallel_execution(self):
        """Test that progress updates are yielded during parallel tool execution."""
        agent = self._create_agent()

        tool_calls = [
            ToolCall(id="tc_1", name="tool_a", arguments={}),
            ToolCall(id="tc_2", name="tool_b", arguments={}),
        ]

        agent.mcp_connection.call_tool.return_value = "result"

        steps = []
        async for s in execute_tools_with_progress(
            agent.mcp_connection,
            agent.tokens,
            agent.memory,
            step_num=1,
            response_text="Test thinking",
            tool_calls=tool_calls,
            input_tokens=100,
            output_tokens=50,
        ):
            steps.append(s)

        # Should have at least the initial progress step and final step
        assert len(steps) >= 2
        # First step should be progress indicator
        assert isinstance(steps[0], ToolStartStep)
        assert steps[0].tool_progress == (0, 2)

    @pytest.mark.asyncio
    async def test_deduplicates_identical_tool_calls_within_step(self):
        """Test that identical tool calls execute once but keep per-call memory results."""
        agent = self._create_agent()

        execution_count = 0

        async def counting_tool(name, args):
            nonlocal execution_count
            execution_count += 1
            return f"result_{name}"

        agent.mcp_connection.call_tool = counting_tool

        tool_calls = [
            ToolCall(id="tc_1", name="search", arguments={"entity": "workspace"}),
            ToolCall(id="tc_2", name="search", arguments={"entity": "workspace"}),
        ]

        steps = []
        async for step in execute_tools_with_progress(
            agent.mcp_connection,
            agent.tokens,
            agent.memory,
            step_num=1,
            response_text="",
            tool_calls=tool_calls,
            input_tokens=100,
            output_tokens=50,
        ):
            steps.append(step)

        assert execution_count == 1
        assert isinstance(steps[0], ToolStartStep)
        assert len(steps[0].tool_calls) == 1
        assert steps[0].tool_progress == (0, 1)

        final_step = steps[-1]
        assert isinstance(final_step, ToolResultStep)
        assert len(final_step.tool_results) == 1
        assert final_step.tool_results[0].tool_call_id == "tc_1"

        memory_step = agent.memory.steps[-1]
        assert isinstance(memory_step, MemoryStep)
        assert len(memory_step.tool_calls) == 2
        assert len(memory_step.tool_results) == 2
        assert memory_step.tool_results[0].tool_call_id == "tc_1"
        assert memory_step.tool_results[1].tool_call_id == "tc_2"
        assert memory_step.tool_results[0].content == memory_step.tool_results[1].content

    @pytest.mark.asyncio
    async def test_cancellation_cancels_child_tasks_and_reraises(self):
        """Test that CancelledError cancels all child tool tasks and propagates."""
        agent = self._create_agent()

        child_task_cancelled = asyncio.Event()
        tools_started = asyncio.Event()

        async def slow_tool(name, args):
            tools_started.set()
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                child_task_cancelled.set()
                raise
            return "result"

        agent.mcp_connection.call_tool = slow_tool

        tool_calls = [
            ToolCall(id="tc_1", name="tool_a", arguments={}),
            ToolCall(id="tc_2", name="tool_b", arguments={}),
        ]

        async def consume_generator():
            async for _ in execute_tools_with_progress(
                agent.mcp_connection,
                agent.tokens,
                agent.memory,
                step_num=1,
                response_text="",
                tool_calls=tool_calls,
                input_tokens=100,
                output_tokens=50,
            ):
                pass

        task = asyncio.create_task(consume_generator())
        # Wait for child tools to start executing
        await tools_started.wait()
        # Cancel the parent task
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Child tasks should have been cancelled
        await asyncio.sleep(0.05)
        assert child_task_cancelled.is_set()


class TestSerializeToolResult:
    """Test RossumAgent._serialize_tool_result method."""

    def test_serialize_none_result(self):
        """Test that None result returns success message."""
        result = serialize_tool_result(None)
        assert result == "Tool executed successfully (no output)"

    def test_serialize_dataclass(self):
        """Test that dataclass is serialized to JSON."""
        from dataclasses import dataclass

        @dataclass
        class TestData:
            name: str
            value: int

        data = TestData(name="test", value=42)
        result = serialize_tool_result(data)

        parsed = json.loads(result)
        assert parsed == {"name": "test", "value": 42}

    def test_serialize_list_of_dataclasses(self):
        """Test that list of dataclasses is serialized to JSON."""
        from dataclasses import dataclass

        @dataclass
        class Item:
            id: int

        items = [Item(id=1), Item(id=2)]
        result = serialize_tool_result(items)

        parsed = json.loads(result)
        assert parsed == [{"id": 1}, {"id": 2}]

    def test_serialize_pydantic_model(self):
        """Test that pydantic model is serialized to JSON."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            field: str

        model = TestModel(field="value")
        result = serialize_tool_result(model)

        parsed = json.loads(result)
        assert parsed == {"field": "value"}

    def test_serialize_list_of_pydantic_models(self):
        """Test that list of pydantic models is serialized to JSON."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            id: int

        models = [TestModel(id=1), TestModel(id=2)]
        result = serialize_tool_result(models)

        parsed = json.loads(result)
        assert parsed == [{"id": 1}, {"id": 2}]

    def test_serialize_dict(self):
        """Test that dict is serialized to JSON."""
        result = serialize_tool_result({"key": "value"})

        parsed = json.loads(result)
        assert parsed == {"key": "value"}

    def test_serialize_list(self):
        """Test that list is serialized to JSON."""
        result = serialize_tool_result([1, 2, 3])

        parsed = json.loads(result)
        assert parsed == [1, 2, 3]

    def test_serialize_string(self):
        """Test that string is returned as-is."""
        result = serialize_tool_result("plain text")

        assert result == "plain text"

    def test_serialize_number(self):
        """Test that number is converted to string."""
        result = serialize_tool_result(42)

        assert result == "42"
