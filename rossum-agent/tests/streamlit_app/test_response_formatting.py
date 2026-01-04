"""Additional tests for rossum_agent.streamlit_app.response_formatting module.

These tests complement the existing test_app_llm_response_formatting.py with
additional edge cases and streaming step tests.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from rossum_agent.agent import AgentStep, ToolCall, ToolResult
from rossum_agent.streamlit_app.response_formatting import ChatResponse, FinalResponse, parse_and_format_final_answer


class TestParseAndFormatFinalAnswerEdgeCases:
    """Additional edge case tests for parse_and_format_final_answer."""

    def test_handles_empty_string(self):
        """Test that empty string is returned as-is."""
        result = parse_and_format_final_answer("")
        assert result == ""

    def test_handles_whitespace_only(self):
        """Test that whitespace-only string is returned as empty."""
        result = parse_and_format_final_answer("   \n\t   ")
        assert result == ""

    def test_handles_nested_json_arrays(self):
        """Test handling of nested JSON arrays."""
        answer = '{"items": [[1, 2], [3, 4]]}'
        result = parse_and_format_final_answer(answer)
        assert "Items" in result

    def test_handles_unicode_content(self):
        """Test handling of unicode characters."""
        answer = '{"summary": "Успешно завершено 🎉"}'
        result = parse_and_format_final_answer(answer)
        assert "Успешно завершено 🎉" in result

    def test_handles_special_characters_in_values(self):
        """Test handling of special characters in JSON values."""
        answer = '{"path": "/home/user/file with spaces.txt"}'
        result = parse_and_format_final_answer(answer)
        assert "/home/user/file with spaces.txt" in result

    def test_handles_boolean_values(self):
        """Test handling of boolean values in dict."""
        answer = '{"enabled": true, "disabled": false}'
        result = parse_and_format_final_answer(answer)
        assert "True" in result or "true" in result.lower()

    def test_handles_null_values(self):
        """Test handling of null values in dict."""
        answer = '{"value": null}'
        result = parse_and_format_final_answer(answer)
        assert "None" in result or "null" in result.lower()

    def test_handles_numeric_string(self):
        """Test that numeric strings are returned as-is."""
        answer = "12345"
        result = parse_and_format_final_answer(answer)
        assert result == "12345"


class TestFinalResponseEdgeCases:
    """Additional edge case tests for FinalResponse class."""

    def test_handles_mixed_file_paths(self):
        """Test handling of mixed file paths (unix and windows)."""
        data = {"generated_files": ["/unix/path/file.txt", "C:\\windows\\path\\file.txt"]}
        response = FinalResponse(data)
        result = response.get_formatted_response()
        assert "`file.txt`" in result

    def test_handles_empty_list(self):
        """Test handling of empty list values."""
        data = {"items": []}
        response = FinalResponse(data)
        result = response.get_formatted_response()
        assert "Items" in result

    def test_handles_deeply_nested_dict(self):
        """Test handling of deeply nested dictionaries."""
        data = {
            "level1": {
                "nested_key": "nested_value",
                "another_key": 42,
            }
        }
        response = FinalResponse(data)
        result = response.get_formatted_response()
        assert "Level1" in result
        assert "Nested Key:** nested_value" in result

    def test_handles_list_with_dict_items(self):
        """Test handling of list containing dict items."""
        data = {"items": [{"name": "item1"}, {"name": "item2"}]}
        response = FinalResponse(data)
        result = response.get_formatted_response()
        assert "Items" in result

    def test_generated_keyword_case_insensitive(self):
        """Test that 'generated' keyword detection is case-insensitive."""
        data = {"GENERATED_FILES": ["file.txt"]}
        response = FinalResponse(data)
        result = response.get_formatted_response()
        assert "📁" in result

    def test_files_keyword_case_insensitive(self):
        """Test that 'files' keyword detection is case-insensitive."""
        data = {"OUTPUT_FILES": ["data.csv"]}
        response = FinalResponse(data)
        result = response.get_formatted_response()
        assert "📁" in result

    def test_status_other_values(self):
        """Test status with values other than success/failed."""
        data = {"status": "pending"}
        response = FinalResponse(data)
        result = response.get_formatted_response()
        assert "❌" in result
        assert "Pending" in result

    def test_multiple_file_lists(self):
        """Test handling of multiple file-related lists."""
        data = {
            "generated_files": ["file1.txt"],
            "output_files": ["file2.txt"],
        }
        response = FinalResponse(data)
        result = response.get_formatted_response()
        assert "Generated Files" in result
        assert "Output Files" in result


class TestChatResponseStreamingSteps:
    """Test ChatResponse streaming step handling."""

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

    def test_process_streaming_step_with_thinking(self, chat_response, mock_placeholder):
        """Test processing streaming step with thinking content."""
        step = AgentStep(
            step_number=1,
            thinking="I'm analyzing the data...",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step)

        assert "Step 1" in chat_response.current_step_markdown
        assert "I'm analyzing the data..." in chat_response.current_step_markdown
        mock_placeholder.markdown.assert_called()
        call_args = mock_placeholder.markdown.call_args[0][0]
        assert "⏳ _Processing..._" in call_args

    def test_process_streaming_step_with_tool_progress(self, chat_response, mock_placeholder):
        """Test processing streaming step with tool progress."""
        step = AgentStep(
            step_number=1,
            thinking="Running analysis",
            current_tool="list_queues",
            tool_progress=(1, 3),
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step)

        assert "Step 1" in chat_response.current_step_markdown
        assert "🔧 Running tool 1/3: **list_queues**" in chat_response.current_step_markdown

    def test_streaming_step_transitions_to_new_step(self, chat_response, mock_placeholder):
        """Test that streaming step properly transitions to new step number."""
        step1 = AgentStep(
            step_number=1,
            thinking="First step thinking",
            is_streaming=True,
            is_final=False,
        )
        step2 = AgentStep(
            step_number=2,
            thinking="Second step thinking",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step1)
        chat_response.process_step(step2)

        assert len(chat_response.completed_steps_markdown) == 1
        assert "Step 1" in chat_response.completed_steps_markdown[0]
        assert "Step 2" in chat_response.current_step_markdown

    def test_streaming_step_with_sub_agent_progress(self, chat_response, mock_placeholder):
        """Test streaming step with sub-agent progress."""
        sub_progress = Mock()
        sub_progress.tool_name = "search_knowledge_base"
        sub_progress.iteration = 2
        sub_progress.max_iterations = 10
        sub_progress.status = "searching"
        sub_progress.current_tool = None
        sub_progress.tool_calls = []

        step = AgentStep(
            step_number=1,
            current_tool="search_knowledge_base",
            tool_progress=(1, 1),
            sub_agent_progress=sub_progress,
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step)

        assert "Sub-agent (search_knowledge_base)" in chat_response.current_step_markdown
        assert "Iteration 2/10" in chat_response.current_step_markdown
        assert "🔍 _Searching Knowledge Base..._" in chat_response.current_step_markdown

    def test_completed_step_clears_current_markdown(self, chat_response, mock_placeholder):
        """Test that completed step clears current_step_markdown."""
        streaming_step = AgentStep(
            step_number=1,
            thinking="Working...",
            is_streaming=True,
            is_final=False,
        )
        completed_step = AgentStep(
            step_number=1,
            thinking="Done",
            is_streaming=False,
            is_final=False,
        )

        chat_response.process_step(streaming_step)
        assert chat_response.current_step_markdown != ""

        chat_response.process_step(completed_step)
        assert chat_response.current_step_markdown == ""
        assert len(chat_response.completed_steps_markdown) == 1

    def test_token_tracking(self, chat_response, mock_placeholder):
        """Test that tokens are properly tracked across steps."""
        step1 = AgentStep(
            step_number=1,
            thinking="First",
            input_tokens=100,
            output_tokens=50,
            is_final=False,
        )
        step2 = AgentStep(
            step_number=2,
            thinking="Second",
            input_tokens=150,
            output_tokens=75,
            is_final=False,
        )

        chat_response.process_step(step1)
        chat_response.process_step(step2)

        assert chat_response.total_input_tokens == 250
        assert chat_response.total_output_tokens == 125
        assert chat_response.total_steps == 2

    def test_tool_call_tracking(self, chat_response, mock_placeholder):
        """Test that tool calls are properly tracked."""
        tool_calls = [
            ToolCall(id="tc_1", name="list_queues", arguments={}),
            ToolCall(id="tc_2", name="get_queue", arguments={"id": 123}),
        ]
        step = AgentStep(
            step_number=1,
            tool_calls=tool_calls,
            is_final=False,
        )

        chat_response.process_step(step)

        assert chat_response.total_tool_calls == 2

    def test_streaming_step_with_tool_progress_no_thinking(self, chat_response, mock_placeholder):
        """Test streaming step with tool progress but no thinking."""
        step = AgentStep(
            step_number=1,
            current_tool="get_annotation",
            tool_progress=(2, 5),
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step)

        assert "🔧 Running tool 2/5: **get_annotation**" in chat_response.current_step_markdown
        assert "💭" not in chat_response.current_step_markdown

    def test_result_stored_for_non_streaming_steps(self, chat_response, mock_placeholder):
        """Test that result is stored for non-streaming steps."""
        step = AgentStep(
            step_number=1,
            thinking="Analysis complete",
            is_streaming=False,
            is_final=False,
        )

        chat_response.process_step(step)

        assert chat_response.result == step

    def test_result_not_stored_for_streaming_steps(self, chat_response, mock_placeholder):
        """Test that result is not stored for streaming steps."""
        step = AgentStep(
            step_number=1,
            thinking="Working...",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step)

        assert chat_response.result is None

    def test_tool_result_short_content(self, chat_response, mock_placeholder):
        """Test that short tool results are displayed inline."""
        tool_result = ToolResult(
            tool_call_id="tc_1",
            name="get_queue",
            content="Queue found",
            is_error=False,
        )
        step = AgentStep(
            step_number=1,
            tool_results=[tool_result],
            is_final=False,
        )

        chat_response.process_step(step)

        completed_md = chat_response.completed_steps_markdown[0]
        assert "Result (get_queue):** Queue found" in completed_md
        assert "<details>" not in completed_md

    def test_thinking_always_shown(self, chat_response, mock_placeholder):
        """Test that thinking is always displayed regardless of tool calls."""
        step_with_tools = AgentStep(
            step_number=1,
            thinking="I will search for queues",
            tool_calls=[ToolCall(id="tc_1", name="list_queues", arguments={})],
            is_final=False,
        )
        step_without_tools = AgentStep(
            step_number=2,
            thinking="Final answer ready",
            is_final=False,
        )

        chat_response.process_step(step_with_tools)
        chat_response.process_step(step_without_tools)

        assert "🧠 **Thinking:**" in chat_response.completed_steps_markdown[0]
        assert "🧠 **Thinking:**" in chat_response.completed_steps_markdown[1]


class TestChatResponseRenderDisplay:
    """Test ChatResponse _render_display method."""

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

    def test_render_includes_all_completed_steps(self, chat_response, mock_placeholder):
        """Test that render includes all completed step markdown."""
        chat_response.completed_steps_markdown = [
            "#### Step 1\nDone",
            "#### Step 2\nAlso done",
        ]
        step = AgentStep(step_number=3, thinking="Working", is_final=False)

        chat_response._render_display(step)

        call_args = mock_placeholder.markdown.call_args[0][0]
        assert "Step 1" in call_args
        assert "Step 2" in call_args

    def test_render_includes_current_step_markdown(self, chat_response, mock_placeholder):
        """Test that render includes current step markdown."""
        chat_response.current_step_markdown = "#### Step 1\nIn progress"
        step = AgentStep(step_number=1, thinking="Working", is_streaming=True, is_final=False)

        chat_response._render_display(step)

        call_args = mock_placeholder.markdown.call_args[0][0]
        assert "In progress" in call_args

    def test_render_shows_error_section(self, chat_response, mock_placeholder):
        """Test that error section is shown for final step with error."""
        step = AgentStep(step_number=1, error="Something failed", is_final=True)

        chat_response._render_display(step)

        call_args = mock_placeholder.markdown.call_args[0][0]
        assert "❌ Error" in call_args
        assert "Something failed" in call_args

    def test_render_uses_unsafe_allow_html(self, chat_response, mock_placeholder):
        """Test that markdown is called with unsafe_allow_html=True."""
        step = AgentStep(step_number=1, thinking="Test", is_final=False)

        chat_response._render_display(step)

        call_kwargs = mock_placeholder.markdown.call_args[1]
        assert call_kwargs.get("unsafe_allow_html") is True
