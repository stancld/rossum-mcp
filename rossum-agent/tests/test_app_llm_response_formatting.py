"""Tests for rossum_agent.app_llm_response_formatting module."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from rossum_agent.agent import AgentStep, ToolCall, ToolResult
from rossum_agent.streamlit_app.response_formatting import ChatResponse, FinalResponse, parse_and_format_final_answer


class TestParseAndFormatFinalAnswer:
    """Test parse_and_format_final_answer function."""

    def test_returns_plain_text_unchanged(self):
        """Test that plain text is returned as-is."""
        answer = "This is a plain text answer."
        result = parse_and_format_final_answer(answer)
        assert result == answer

    def test_parses_json_dict(self):
        """Test that JSON dictionary is parsed and formatted."""
        answer = '{"status": "success", "summary": "Task completed"}'
        result = parse_and_format_final_answer(answer)

        assert "Status: Success" in result
        assert "Summary" in result
        assert "Task completed" in result

    def test_parses_python_dict_literal(self):
        """Test that Python dict literal is parsed and formatted."""
        answer = "{'status': 'success', 'summary': 'Task completed'}"
        result = parse_and_format_final_answer(answer)

        assert "Status: Success" in result
        assert "Summary" in result
        assert "Task completed" in result

    def test_handles_json_list(self):
        """Test that JSON list is returned as-is."""
        answer = '["item1", "item2", "item3"]'
        result = parse_and_format_final_answer(answer)
        assert result == answer

    def test_handles_invalid_json(self):
        """Test that invalid JSON is returned as-is."""
        answer = '{"incomplete": '
        result = parse_and_format_final_answer(answer)
        assert result == answer.strip()

    def test_handles_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        answer = '  \n  {"status": "success"}  \n  '
        result = parse_and_format_final_answer(answer)
        assert "Status: Success" in result

    def test_handles_complex_nested_dict(self):
        """Test that complex nested dictionaries are formatted."""
        answer = json.dumps(
            {
                "status": "success",
                "summary": "Analysis complete",
                "details": {
                    "count": 10,
                    "average": 5.5,
                },
                "files": ["report.pdf", "chart.png"],
            }
        )
        result = parse_and_format_final_answer(answer)

        assert "Status: Success" in result
        assert "Summary" in result
        assert "Details" in result
        assert "count" in result.lower()
        assert "Files" in result


class TestFinalResponse:
    """Test FinalResponse class."""

    def test_formats_status_success(self):
        """Test formatting of success status."""
        data = {"status": "success"}
        response = FinalResponse(data)
        result = response.get_formatted_response()

        assert "✅" in result
        assert "Status: Success" in result

    def test_formats_status_failure(self):
        """Test formatting of failure status."""
        data = {"status": "failed"}
        response = FinalResponse(data)
        result = response.get_formatted_response()

        assert "❌" in result
        assert "Status: Failed" in result

    def test_formats_summary(self):
        """Test formatting of summary section."""
        data = {"summary": "Task completed successfully"}
        response = FinalResponse(data)
        result = response.get_formatted_response()

        assert "📝 Summary" in result
        assert "Task completed successfully" in result

    def test_formats_generated_files(self):
        """Test formatting of generated files."""
        data = {"generated_files": ["report.pdf", "/path/to/chart.png"]}
        response = FinalResponse(data)
        result = response.get_formatted_response()

        assert "📁 Generated Files" in result
        assert "`report.pdf`" in result
        assert "`chart.png`" in result

    def test_formats_files_with_keyword(self):
        """Test that fields with 'files' keyword are detected."""
        data = {"output_files": ["data.csv", "summary.txt"]}
        response = FinalResponse(data)
        result = response.get_formatted_response()

        assert "📁 Output Files" in result
        assert "`data.csv`" in result
        assert "`summary.txt`" in result

    def test_formats_nested_dict(self):
        """Test formatting of nested dictionary."""
        data = {
            "details": {
                "processed": 100,
                "failed": 5,
                "success_rate": 95,
            }
        }
        response = FinalResponse(data)
        result = response.get_formatted_response()

        assert "Details" in result
        assert "Processed:** 100" in result
        assert "Failed:** 5" in result
        assert "Success Rate:** 95" in result

    def test_formats_list_values(self):
        """Test formatting of list values."""
        data = {"items": ["apple", "banana", "cherry"]}
        response = FinalResponse(data)
        result = response.get_formatted_response()

        assert "Items" in result
        assert "- apple" in result
        assert "- banana" in result
        assert "- cherry" in result

    def test_formats_simple_key_value(self):
        """Test formatting of simple key-value pairs."""
        data = {"count": 42, "average": 3.14}
        response = FinalResponse(data)
        result = response.get_formatted_response()

        assert "Count:** 42" in result
        assert "Average:** 3.14" in result

    def test_caches_result(self):
        """Test that get_formatted_response can be called multiple times."""
        data = {"status": "success", "summary": "Done"}
        response = FinalResponse(data)

        result1 = response.get_formatted_response()
        result2 = response.get_formatted_response()

        assert result1 == result2

    def test_processes_keys_only_once(self):
        """Test that keys are not duplicated in output."""
        data = {"status": "success", "summary": "Done"}
        response = FinalResponse(data)
        result = response.get_formatted_response()

        status_count = result.count("Status:")
        summary_count = result.count("Summary")

        assert status_count == 1
        assert summary_count == 1

    def test_handles_empty_dict(self):
        """Test handling of empty dictionary."""
        data = {}
        response = FinalResponse(data)
        result = response.get_formatted_response()

        assert isinstance(result, str)
        assert len(result) == 0

    def test_handles_non_string_list_items(self):
        """Test handling of non-string items in lists."""
        data = {"items": [1, 2.5, True, None]}
        response = FinalResponse(data)
        result = response.get_formatted_response()

        assert "- 1" in result
        assert "- 2.5" in result
        assert "- True" in result
        assert "- None" in result

    def test_title_case_conversion(self):
        """Test that underscored keys are converted to title case."""
        data = {"processing_status": "complete", "total_items_processed": 100}
        response = FinalResponse(data)
        result = response.get_formatted_response()

        assert "Processing Status:** complete" in result
        assert "Total Items Processed:** 100" in result


class TestChatResponse:
    """Test ChatResponse class."""

    @pytest.fixture
    def mock_placeholder(self):
        """Create a mock Streamlit placeholder."""
        placeholder = Mock()
        placeholder.markdown = Mock()
        return placeholder

    @pytest.fixture
    def chat_response(self, mock_placeholder):
        """Create a ChatResponse instance for testing."""
        return ChatResponse(prompt="Test prompt", output_placeholder=mock_placeholder)

    def test_initialization(self, chat_response):
        """Test ChatResponse initialization."""
        assert chat_response.prompt == "Test prompt"
        assert chat_response.completed_steps_markdown == []
        assert chat_response.final_answer_text is None

    def test_process_step_basic(self, chat_response, mock_placeholder):
        """Test processing of basic step."""
        step = AgentStep(
            step_number=1,
            thinking="Analyzing data",
            is_final=False,
        )

        chat_response.process_step(step)

        assert len(chat_response.completed_steps_markdown) == 1
        assert "Step 1" in chat_response.completed_steps_markdown[0]
        mock_placeholder.markdown.assert_called()

    def test_process_step_with_tool_calls(self, chat_response):
        """Test processing of step with tool calls."""
        tool_call = ToolCall(id="tc_1", name="list_queues", arguments={})

        step = AgentStep(
            step_number=1,
            thinking="Let me search",
            tool_calls=[tool_call],
            is_final=False,
        )

        chat_response.process_step(step)

        assert "list_queues" in chat_response.completed_steps_markdown[0]

    def test_process_step_with_tool_results(self, chat_response):
        """Test processing of step with tool results."""
        tool_result = ToolResult(
            tool_call_id="tc_1",
            name="list_queues",
            content='{"queues": []}',
            is_error=False,
        )

        step = AgentStep(
            step_number=1,
            tool_results=[tool_result],
            is_final=False,
        )

        chat_response.process_step(step)

        assert "list_queues" in chat_response.completed_steps_markdown[0]

    def test_process_step_with_error_result(self, chat_response):
        """Test processing of step with error in tool result."""
        tool_result = ToolResult(
            tool_call_id="tc_1",
            name="list_queues",
            content="Connection failed",
            is_error=True,
        )

        step = AgentStep(
            step_number=1,
            tool_results=[tool_result],
            is_final=False,
        )

        chat_response.process_step(step)

        assert "❌" in chat_response.completed_steps_markdown[0]
        assert "Error" in chat_response.completed_steps_markdown[0]

    def test_process_step_final_answer(self, chat_response):
        """Test processing of final answer step."""
        step = AgentStep(
            step_number=2,
            thinking="Done",
            final_answer='{"status": "success"}',
            is_final=True,
        )

        chat_response.process_step(step)

        assert chat_response.final_answer_text is not None
        assert "Status: Success" in chat_response.final_answer_text

    def test_shows_processing_indicator(self, chat_response, mock_placeholder):
        """Test that processing indicator is shown during execution."""
        step = AgentStep(
            step_number=1,
            thinking="Working",
            is_final=False,
        )

        chat_response.process_step(step)

        call_args = mock_placeholder.markdown.call_args[0][0]
        assert "⏳ _Processing..._" in call_args

    def test_shows_final_answer_section(self, chat_response, mock_placeholder):
        """Test that final answer section is shown when complete."""
        step = AgentStep(
            step_number=1,
            thinking="Complete",
            final_answer="Task finished",
            is_final=True,
        )

        chat_response.process_step(step)

        call_args = mock_placeholder.markdown.call_args[0][0]
        assert "✅ Final Answer" in call_args
        assert "Task finished" in call_args

    def test_shows_error_section(self, chat_response, mock_placeholder):
        """Test that error section is shown when step has error."""
        step = AgentStep(
            step_number=1,
            error="Something went wrong",
            is_final=True,
        )

        chat_response.process_step(step)

        call_args = mock_placeholder.markdown.call_args[0][0]
        assert "❌ Error" in call_args
        assert "Something went wrong" in call_args

    def test_multiple_steps(self, chat_response, mock_placeholder):
        """Test processing multiple steps."""
        step1 = AgentStep(step_number=1, thinking="Step 1", is_final=False)
        step2 = AgentStep(step_number=2, thinking="Step 2", is_final=False)
        step3 = AgentStep(step_number=3, final_answer="Done", is_final=True)

        chat_response.process_step(step1)
        chat_response.process_step(step2)
        chat_response.process_step(step3)

        assert len(chat_response.completed_steps_markdown) == 3
        assert chat_response.final_answer_text is not None

    def test_long_tool_result_uses_details(self, chat_response):
        """Test that long tool results use details/summary HTML."""
        long_content = "x" * 300
        tool_result = ToolResult(
            tool_call_id="tc_1",
            name="get_data",
            content=long_content,
            is_error=False,
        )

        step = AgentStep(
            step_number=1,
            tool_results=[tool_result],
            is_final=False,
        )

        chat_response.process_step(step)

        assert "<details>" in chat_response.completed_steps_markdown[0]
        assert "<summary>" in chat_response.completed_steps_markdown[0]


class TestFormatSubAgentProgress:
    """Test _format_sub_agent_progress method."""

    @pytest.fixture
    def mock_placeholder(self):
        """Create a mock Streamlit placeholder."""
        placeholder = Mock()
        placeholder.markdown = Mock()
        return placeholder

    @pytest.fixture
    def chat_response(self, mock_placeholder):
        """Create a ChatResponse instance for testing."""
        return ChatResponse(prompt="Test prompt", output_placeholder=mock_placeholder)

    def _make_progress(
        self,
        tool_name: str = "search_knowledge_base",
        iteration: int = 0,
        max_iterations: int = 0,
        status: str = "running",
        current_tool: str | None = None,
        tool_calls: list | None = None,
    ):
        """Create a mock progress object."""
        progress = Mock()
        progress.tool_name = tool_name
        progress.iteration = iteration
        progress.max_iterations = max_iterations
        progress.status = status
        progress.current_tool = current_tool
        progress.tool_calls = tool_calls or []
        return progress

    def test_format_thinking_status(self, chat_response):
        """Test formatting of thinking status."""
        progress = self._make_progress(status="thinking")
        result = chat_response._format_sub_agent_progress(progress)

        assert "⏳ _Thinking..._" in result
        assert "Sub-agent (search_knowledge_base)" in result

    def test_format_searching_status(self, chat_response):
        """Test formatting of searching status."""
        progress = self._make_progress(status="searching")
        result = chat_response._format_sub_agent_progress(progress)

        assert "🔍 _Searching Knowledge Base..._" in result
        assert "Sub-agent (search_knowledge_base)" in result

    def test_format_analyzing_status(self, chat_response):
        """Test formatting of analyzing status."""
        progress = self._make_progress(status="analyzing")
        result = chat_response._format_sub_agent_progress(progress)

        assert "🧠 _Analyzing results..._" in result
        assert "Sub-agent (search_knowledge_base)" in result

    def test_format_running_tool_status(self, chat_response):
        """Test formatting of running_tool status."""
        progress = self._make_progress(
            tool_name="debug_hook",
            status="running_tool",
            current_tool="list_hooks",
            tool_calls=["list_hooks", "get_hook"],
        )
        result = chat_response._format_sub_agent_progress(progress)

        assert "🔧 Running: `list_hooks`" in result
        assert "`list_hooks`" in result
        assert "`get_hook`" in result

    def test_format_completed_status(self, chat_response):
        """Test formatting of completed status."""
        progress = self._make_progress(status="completed")
        result = chat_response._format_sub_agent_progress(progress)

        assert "✅ _Completed_" in result

    def test_format_with_iterations(self, chat_response):
        """Test formatting with iteration count."""
        progress = self._make_progress(tool_name="debug_hook", iteration=3, max_iterations=15, status="thinking")
        result = chat_response._format_sub_agent_progress(progress)

        assert "Iteration 3/15" in result
        assert "Sub-agent (debug_hook)" in result

    def test_format_without_iterations(self, chat_response):
        """Test formatting without iteration count (max_iterations=0)."""
        progress = self._make_progress(max_iterations=0, status="searching")
        result = chat_response._format_sub_agent_progress(progress)

        assert "Iteration" not in result
        assert "Sub-agent (search_knowledge_base)" in result
