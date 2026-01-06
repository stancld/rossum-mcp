"""Additional tests for rossum_agent.streamlit_app.response_formatting module.

These tests complement the existing test_app_llm_response_formatting.py with
additional edge cases and streaming step tests.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from rossum_agent.agent import AgentStep, ToolCall, ToolResult
from rossum_agent.agent.models import StepType
from rossum_agent.streamlit_app.response_formatting import (
    ChatResponse,
    FinalResponse,
    get_display_tool_name,
    parse_and_format_final_answer,
)

SANDBOX_ORG_ID = 729505


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


class TestChatResponseStepTypes:
    """Test ChatResponse handling of different StepType values (matching API's agent_service.py)."""

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

    def test_process_thinking_step_type(self, chat_response, mock_placeholder):
        """Test processing step with StepType.THINKING."""
        step = AgentStep(
            step_number=1,
            step_type=StepType.THINKING,
            thinking="I'm analyzing the data...",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step)

        assert "🧠 **Thinking:**" in chat_response.current_step_markdown
        assert "I'm analyzing the data..." in chat_response.current_step_markdown

    def test_process_intermediate_step_type_with_accumulated_text(self, chat_response, mock_placeholder):
        """Test processing step with StepType.INTERMEDIATE and accumulated_text."""
        step = AgentStep(
            step_number=1,
            step_type=StepType.INTERMEDIATE,
            accumulated_text="Here is some intermediate text before tool calls",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step)

        assert "Step 1" in chat_response.current_step_markdown
        assert "💬 **Response:**" in chat_response.current_step_markdown
        assert "Here is some intermediate text before tool calls" in chat_response.current_step_markdown

    def test_process_final_answer_step_type_with_accumulated_text(self, chat_response, mock_placeholder):
        """Test processing step with StepType.FINAL_ANSWER and accumulated_text."""
        step = AgentStep(
            step_number=1,
            step_type=StepType.FINAL_ANSWER,
            accumulated_text="Here is the final answer text",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step)

        assert "Step 1" in chat_response.current_step_markdown
        assert "💬 **Response:**" in chat_response.current_step_markdown
        assert "Here is the final answer text" in chat_response.current_step_markdown

    def test_process_completed_final_answer_step(self, chat_response, mock_placeholder):
        """Test processing completed step with final_answer."""
        step = AgentStep(
            step_number=1,
            step_type=StepType.FINAL_ANSWER,
            final_answer="The analysis is complete.",
            is_streaming=False,
            is_final=True,
        )

        chat_response.process_step(step)

        assert chat_response.final_answer_text is not None
        assert "The analysis is complete." in chat_response.final_answer_text

    def test_step_type_transitions_thinking_to_intermediate(self, chat_response, mock_placeholder):
        """Test transition from thinking to intermediate within same step."""
        thinking_step = AgentStep(
            step_number=1,
            step_type=StepType.THINKING,
            thinking="Let me analyze...",
            is_streaming=True,
            is_final=False,
        )
        intermediate_step = AgentStep(
            step_number=1,
            step_type=StepType.INTERMEDIATE,
            accumulated_text="Based on my analysis",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(thinking_step)
        chat_response.process_step(intermediate_step)

        assert len(chat_response.completed_steps_markdown) == 0
        assert "Step 1" in chat_response.current_step_markdown

    def test_sandbox_org_id_constant(self):
        """Test that SANDBOX_ORG_ID is properly defined for test configuration."""
        assert SANDBOX_ORG_ID == 729505


class TestChatResponseTextStreaming:
    """Test ChatResponse handling of text streaming (matching API's agent_service.py behavior)."""

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

    def test_streaming_text_with_thinking_and_accumulated_text(self, chat_response, mock_placeholder):
        """Test streaming step with both thinking and accumulated_text."""
        step = AgentStep(
            step_number=1,
            thinking="Let me analyze this...",
            accumulated_text="Based on my analysis, the result is...",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step)

        assert "🧠 **Thinking:**" in chat_response.current_step_markdown
        assert "Let me analyze this..." in chat_response.current_step_markdown
        assert "💬 **Response:**" in chat_response.current_step_markdown
        assert "Based on my analysis, the result is..." in chat_response.current_step_markdown

    def test_streaming_text_incremental_updates(self, chat_response, mock_placeholder):
        """Test that accumulated_text updates incrementally during streaming."""
        step1 = AgentStep(
            step_number=1,
            accumulated_text="Hello",
            is_streaming=True,
            is_final=False,
        )
        step2 = AgentStep(
            step_number=1,
            accumulated_text="Hello, I am analyzing",
            is_streaming=True,
            is_final=False,
        )
        step3 = AgentStep(
            step_number=1,
            accumulated_text="Hello, I am analyzing your request.",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step1)
        assert "Hello" in chat_response.current_step_markdown

        chat_response.process_step(step2)
        assert "Hello, I am analyzing" in chat_response.current_step_markdown

        chat_response.process_step(step3)
        assert "Hello, I am analyzing your request." in chat_response.current_step_markdown

    def test_streaming_text_renders_to_placeholder(self, chat_response, mock_placeholder):
        """Test that streaming text is rendered to the placeholder."""
        step = AgentStep(
            step_number=1,
            step_type=StepType.INTERMEDIATE,
            accumulated_text="Streaming response text",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step)

        mock_placeholder.markdown.assert_called()
        call_args = mock_placeholder.markdown.call_args[0][0]
        assert "Streaming response text" in call_args

    def test_streaming_final_answer_text(self, chat_response, mock_placeholder):
        """Test streaming final answer via accumulated_text before completion."""
        streaming_step = AgentStep(
            step_number=1,
            step_type=StepType.FINAL_ANSWER,
            accumulated_text="The answer is 42",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(streaming_step)

        assert "💬 **Response:**" in chat_response.current_step_markdown
        assert "The answer is 42" in chat_response.current_step_markdown
        assert chat_response.final_answer_text is None

    def test_streaming_text_does_not_show_extended_thinking_message(self, chat_response, mock_placeholder):
        """Test that streaming text doesn't show 'Extended thinking in progress' message."""
        step = AgentStep(
            step_number=1,
            accumulated_text="I'm providing a response...",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step)

        call_args = mock_placeholder.markdown.call_args[0][0]
        assert "Extended thinking in progress" not in call_args

    def test_text_delta_field_present(self, chat_response, mock_placeholder):
        """Test step with text_delta field (used for incremental text updates)."""
        step = AgentStep(
            step_number=1,
            text_delta="new chunk",
            accumulated_text="previous text new chunk",
            is_streaming=True,
            is_final=False,
        )

        chat_response.process_step(step)

        assert "previous text new chunk" in chat_response.current_step_markdown


class TestGetDisplayToolName:
    """Tests for get_display_tool_name function."""

    def test_regular_tool_returns_unchanged(self):
        """Regular tools return their name unchanged."""
        assert get_display_tool_name("get_queues") == "get_queues"
        assert get_display_tool_name("update_schema", {"schema_id": 123}) == "update_schema"

    def test_call_on_connection_with_full_args(self):
        """call_on_connection with full args returns expanded format."""
        args = {"connection_id": "sandbox", "tool_name": "get_queues", "arguments": "{}"}
        result = get_display_tool_name("call_on_connection", args)
        assert result == "call_on_connection[sandbox.get_queues]"

    def test_call_on_connection_missing_connection_id(self):
        """call_on_connection without connection_id returns unchanged."""
        args = {"tool_name": "get_queues"}
        result = get_display_tool_name("call_on_connection", args)
        assert result == "call_on_connection"

    def test_call_on_connection_missing_tool_name(self):
        """call_on_connection without tool_name returns unchanged."""
        args = {"connection_id": "sandbox"}
        result = get_display_tool_name("call_on_connection", args)
        assert result == "call_on_connection"

    def test_call_on_connection_no_args(self):
        """call_on_connection without args returns unchanged."""
        assert get_display_tool_name("call_on_connection") == "call_on_connection"
        assert get_display_tool_name("call_on_connection", None) == "call_on_connection"
        assert get_display_tool_name("call_on_connection", {}) == "call_on_connection"


class TestChatResponseCallOnConnectionDisplay:
    """Tests for ChatResponse displaying call_on_connection with expanded tool names."""

    @pytest.fixture
    def mock_placeholder(self):
        placeholder = Mock()
        placeholder.markdown = Mock()
        return placeholder

    @pytest.fixture
    def chat_response(self, mock_placeholder):
        return ChatResponse(prompt="Test prompt", output_placeholder=mock_placeholder)

    def test_streaming_step_shows_expanded_call_on_connection(self, chat_response, mock_placeholder):
        """Streaming step shows call_on_connection[connection.tool] format."""
        tool_call = ToolCall(
            id="tc_1",
            name="call_on_connection",
            arguments={"connection_id": "sandbox", "tool_name": "get_queues", "arguments": "{}"},
        )
        step = AgentStep(
            step_number=1,
            tool_calls=[tool_call],
            is_streaming=True,
            is_final=False,
            current_tool="call_on_connection",
            tool_progress=(1, 1),
        )

        chat_response.process_step(step)

        assert "call_on_connection[sandbox.get_queues]" in chat_response.current_step_markdown

    def test_completed_step_shows_expanded_call_on_connection(self, chat_response, mock_placeholder):
        """Completed step shows call_on_connection[connection.tool] in Tools list."""
        tool_call = ToolCall(
            id="tc_1",
            name="call_on_connection",
            arguments={"connection_id": "sandbox", "tool_name": "get_queues", "arguments": "{}"},
        )
        tool_result = ToolResult(
            tool_call_id="tc_1",
            name="call_on_connection",
            content='[get_queues] {"queues": []}',
        )
        step = AgentStep(
            step_number=1,
            tool_calls=[tool_call],
            tool_results=[tool_result],
            is_streaming=False,
            is_final=False,
        )

        chat_response.process_step(step)

        assert "call_on_connection[sandbox.get_queues]" in "\n".join(chat_response.completed_steps_markdown)
