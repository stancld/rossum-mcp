"""Tests for rossum_agent.app_llm_response_formatting module."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from rossum_agent.app_llm_response_formatting import ChatResponse, FinalResponse, parse_and_format_final_answer
from smolagents.memory import ActionStep, PlanningStep
from smolagents.monitoring import Timing


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
        return ChatResponse(prompt="Test prompt", output_placeholder=mock_placeholder, start_time=0.0)

    def test_initialization(self, chat_response):
        """Test ChatResponse initialization."""
        assert chat_response.prompt == "Test prompt"
        assert chat_response.start_time == 0.0
        assert chat_response.steps_markdown == []
        assert chat_response.final_answer_text is None

    def test_process_planning_step(self, chat_response):
        """Test processing of planning step."""

        step = PlanningStep(
            plan="1. First do this\n2. Then do that",
            model_input_messages=[],
            model_output_message=Mock(),
            timing=Timing(start_time=0.0, end_time=0.5),
        )
        chat_response.process_planning_step(step)

        assert len(chat_response.steps_markdown) == 1
        assert "🧠 Plan" in chat_response.steps_markdown[0]
        assert "First do this" in chat_response.steps_markdown[0]

    def test_process_action_step_basic(self, chat_response, mock_placeholder):
        """Test processing of basic action step."""
        step = ActionStep(
            step_number=1,
            model_output="Analyzing data",
            tool_calls=[],
            observations="",
            action_output=None,
            is_final_answer=False,
            timing=Timing(start_time=0.0, end_time=0.5),
        )

        chat_response.process_action_step(step)

        assert len(chat_response.steps_markdown) == 1
        assert "Step 1" in chat_response.steps_markdown[0]
        mock_placeholder.markdown.assert_called()

    def test_process_action_step_with_tool_calls(self, chat_response):
        """Test processing of action step with tool calls."""
        tool_call = Mock()
        tool_call.name = "search_tool"

        step = ActionStep(
            step_number=1,
            model_output="Searching",
            tool_calls=[tool_call],
            observations="",
            action_output=None,
            is_final_answer=False,
            timing=Timing(start_time=0.0, end_time=0.5),
        )

        chat_response.process_action_step(step)

        assert "search_tool" in chat_response.steps_markdown[0]

    def test_process_action_step_skips_python_interpreter(self, chat_response):
        """Test that python_interpreter tool is skipped in display."""
        tool_call = Mock()
        tool_call.name = "python_interpreter"

        step = ActionStep(
            step_number=1,
            model_output="Running code",
            tool_calls=[tool_call],
            observations="",
            action_output=None,
            is_final_answer=False,
            timing=Timing(start_time=0.0, end_time=0.5),
        )

        chat_response.process_action_step(step)

        assert "python_interpreter" not in chat_response.steps_markdown[0]

    def test_process_action_step_with_code_blocks(self, chat_response):
        """Test processing of action step with code blocks."""
        step = ActionStep(
            step_number=1,
            model_output="Let me analyze <code>print('hello')</code>",
            tool_calls=[],
            observations="",
            action_output=None,
            is_final_answer=False,
            timing=Timing(start_time=0.0, end_time=0.5),
        )

        chat_response.process_action_step(step)

        markdown = chat_response.steps_markdown[0]
        assert "View code" in markdown
        assert "print('hello')" in markdown

    def test_process_action_step_extracts_thinking(self, chat_response):
        """Test extraction of thinking from model output."""
        step = ActionStep(
            step_number=1,
            model_output="Analyzing the data <code>result = 42</code>",
            tool_calls=[],
            observations="",
            action_output=None,
            is_final_answer=False,
            timing=Timing(start_time=0.0, end_time=0.5),
        )

        chat_response.process_action_step(step)

        markdown = chat_response.steps_markdown[0]
        assert "💭 Analyzing the data" in markdown

    def test_process_action_step_with_observations(self, chat_response):
        """Test processing of observations."""
        step = ActionStep(
            step_number=1,
            model_output="Processing",
            tool_calls=[],
            observations="Last output from code snippet: 42",
            action_output=None,
            is_final_answer=False,
            timing=Timing(start_time=0.0, end_time=0.5),
        )

        chat_response.process_action_step(step)

        markdown = chat_response.steps_markdown[0]
        assert "Result:** 42" in markdown

    def test_process_action_step_final_answer(self, chat_response):
        """Test processing of final answer step."""
        step = ActionStep(
            step_number=2,
            model_output="Done",
            tool_calls=[],
            observations="",
            action_output='{"status": "success"}',
            is_final_answer=True,
            timing=Timing(start_time=0.0, end_time=0.5),
        )

        chat_response.process_action_step(step)

        assert chat_response.final_answer_text is not None
        assert "Status: Success" in chat_response.final_answer_text

    def test_shows_processing_indicator(self, chat_response, mock_placeholder):
        """Test that processing indicator is shown during execution."""
        step = ActionStep(
            step_number=1,
            model_output="Working",
            tool_calls=[],
            observations="",
            action_output=None,
            is_final_answer=False,
            timing=Timing(start_time=0.0, end_time=0.5),
        )

        chat_response.process_action_step(step)

        call_args = mock_placeholder.markdown.call_args[0][0]
        assert "⏳ _Processing..._" in call_args

    def test_shows_final_answer_section(self, chat_response, mock_placeholder):
        """Test that final answer section is shown when complete."""
        step = ActionStep(
            step_number=1,
            model_output="Complete",
            tool_calls=[],
            observations="",
            action_output="Task finished",
            is_final_answer=True,
            timing=Timing(start_time=0.0, end_time=0.5),
        )

        chat_response.process_action_step(step)

        call_args = mock_placeholder.markdown.call_args[0][0]
        assert "✅ Final Answer" in call_args
        assert "Task finished" in call_args

    def test_process_step_delegates_to_specific_handlers(self, chat_response):
        """Test that process_step delegates to appropriate handler."""
        planning_step = PlanningStep(
            plan="Do something",
            model_input_messages=[],
            model_output_message=Mock(),
            timing=Timing(start_time=0.0, end_time=0.5),
        )
        chat_response.process_step(planning_step)
        assert len(chat_response.steps_markdown) == 1

        action_step = ActionStep(
            step_number=1,
            model_output="Working",
            tool_calls=[],
            observations="",
            action_output=None,
            is_final_answer=False,
            timing=Timing(start_time=0.0, end_time=0.5),
        )
        chat_response.process_step(action_step)
        assert len(chat_response.steps_markdown) == 2
