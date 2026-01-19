"""Tests for rossum_agent.tools.subagents.hook_debug module."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.tools.subagents.base import SubAgentResult
from rossum_agent.tools.subagents.hook_debug import (
    _ALLOWED_BUILTIN_NAMES,
    _EVALUATE_HOOK_TOOL,
    _GET_ANNOTATION_TOOL,
    _GET_HOOK_TOOL,
    _GET_SCHEMA_TOOL,
    _HOOK_DEBUG_SYSTEM_PROMPT,
    _OPUS_TOOLS,
    _SEARCH_KNOWLEDGE_BASE_TOOL,
    _WEB_SEARCH_NO_RESULTS,
    _call_opus_for_debug,
    _execute_opus_tool,
    _extract_and_analyze_web_search_results,
    _extract_web_search_text_from_block,
    _make_evaluate_response,
    _strip_imports,
    debug_hook,
    evaluate_python_hook,
)
from rossum_agent.tools.subagents.knowledge_base import WebSearchError


class TestConstants:
    """Test module constants."""

    def test_allowed_builtin_names_contains_expected_builtins(self):
        """Test _ALLOWED_BUILTIN_NAMES contains essential builtins."""
        assert isinstance(_ALLOWED_BUILTIN_NAMES, set)
        assert len(_ALLOWED_BUILTIN_NAMES) > 0
        key_builtins = {"len", "str", "list", "dict", "int", "print"}
        assert key_builtins.issubset(_ALLOWED_BUILTIN_NAMES)

    def test_allowed_builtin_names_contains_exceptions(self):
        """Test _ALLOWED_BUILTIN_NAMES contains common exception types."""
        expected_exceptions = {
            "Exception",
            "ValueError",
            "TypeError",
            "KeyError",
            "IndexError",
            "RuntimeError",
            "AttributeError",
        }
        assert expected_exceptions.issubset(_ALLOWED_BUILTIN_NAMES)

    def test_hook_debug_system_prompt_is_non_empty_string(self):
        """Test _HOOK_DEBUG_SYSTEM_PROMPT is a non-empty string."""
        assert isinstance(_HOOK_DEBUG_SYSTEM_PROMPT, str)
        assert len(_HOOK_DEBUG_SYSTEM_PROMPT) > 100
        assert "rossum_hook_request_handler" in _HOOK_DEBUG_SYSTEM_PROMPT

    def test_get_hook_tool_has_required_fields(self):
        """Test _GET_HOOK_TOOL has required schema fields."""
        assert _GET_HOOK_TOOL["name"] == "get_hook"
        assert "description" in _GET_HOOK_TOOL
        assert "input_schema" in _GET_HOOK_TOOL
        assert _GET_HOOK_TOOL["input_schema"]["type"] == "object"
        assert "hook_id" in _GET_HOOK_TOOL["input_schema"]["properties"]
        assert "hook_id" in _GET_HOOK_TOOL["input_schema"]["required"]

    def test_get_annotation_tool_has_required_fields(self):
        """Test _GET_ANNOTATION_TOOL has required schema fields."""
        assert _GET_ANNOTATION_TOOL["name"] == "get_annotation"
        assert "description" in _GET_ANNOTATION_TOOL
        assert "input_schema" in _GET_ANNOTATION_TOOL
        assert _GET_ANNOTATION_TOOL["input_schema"]["type"] == "object"
        assert "annotation_id" in _GET_ANNOTATION_TOOL["input_schema"]["properties"]
        assert "annotation_id" in _GET_ANNOTATION_TOOL["input_schema"]["required"]

    def test_get_schema_tool_has_required_fields(self):
        """Test _GET_SCHEMA_TOOL has required schema fields."""
        assert _GET_SCHEMA_TOOL["name"] == "get_schema"
        assert "description" in _GET_SCHEMA_TOOL
        assert "input_schema" in _GET_SCHEMA_TOOL
        assert _GET_SCHEMA_TOOL["input_schema"]["type"] == "object"
        assert "schema_id" in _GET_SCHEMA_TOOL["input_schema"]["properties"]
        assert "schema_id" in _GET_SCHEMA_TOOL["input_schema"]["required"]

    def test_evaluate_hook_tool_has_required_fields(self):
        """Test _EVALUATE_HOOK_TOOL has required schema fields."""
        assert _EVALUATE_HOOK_TOOL["name"] == "evaluate_python_hook"
        assert "description" in _EVALUATE_HOOK_TOOL
        assert "input_schema" in _EVALUATE_HOOK_TOOL
        props = _EVALUATE_HOOK_TOOL["input_schema"]["properties"]
        assert "code" in props
        assert "annotation_json" in props
        assert "schema_json" in props
        required = _EVALUATE_HOOK_TOOL["input_schema"]["required"]
        assert "code" in required
        assert "annotation_json" in required

    def test_search_knowledge_base_tool_has_required_fields(self):
        """Test _SEARCH_KNOWLEDGE_BASE_TOOL has required schema fields."""
        assert _SEARCH_KNOWLEDGE_BASE_TOOL["name"] == "search_knowledge_base"
        assert "description" in _SEARCH_KNOWLEDGE_BASE_TOOL
        assert "input_schema" in _SEARCH_KNOWLEDGE_BASE_TOOL
        assert "query" in _SEARCH_KNOWLEDGE_BASE_TOOL["input_schema"]["properties"]
        assert "query" in _SEARCH_KNOWLEDGE_BASE_TOOL["input_schema"]["required"]

    def test_opus_tools_list_contains_all_tools(self):
        """Test _OPUS_TOOLS contains all required tools."""
        tool_names = [t["name"] for t in _OPUS_TOOLS]
        assert "get_hook" in tool_names
        assert "get_annotation" in tool_names
        assert "get_schema" in tool_names
        assert "evaluate_python_hook" in tool_names
        assert "search_knowledge_base" in tool_names


class TestStripImports:
    """Test _strip_imports function."""

    def test_strips_import_statements(self):
        """Test strips 'import x' statements."""
        code = "import json\nx = 1"
        result = _strip_imports(code)
        assert "import json" not in result
        assert "x = 1" in result

    def test_strips_from_import_statements(self):
        """Test strips 'from x import y' statements."""
        code = "from decimal import Decimal\nvalue = Decimal(1)"
        result = _strip_imports(code)
        assert "from decimal import Decimal" not in result
        assert "value = Decimal(1)" in result

    def test_preserves_other_code(self):
        """Test preserves non-import code."""
        code = "def foo():\n    return 42\n\nresult = foo()"
        result = _strip_imports(code)
        assert result == code

    def test_handles_multiple_imports(self):
        """Test handles multiple import statements."""
        code = """import json
from collections import defaultdict
import re
def handler(payload):
    return payload
from functools import partial"""
        result = _strip_imports(code)
        assert "import json" not in result
        assert "from collections" not in result
        assert "import re" not in result
        assert "from functools" not in result
        assert "def handler(payload):" in result
        assert "return payload" in result

    def test_handles_indented_imports(self):
        """Test handles indented import statements."""
        code = "def foo():\n    import json\n    return 1"
        result = _strip_imports(code)
        assert "import json" not in result
        assert "def foo():" in result
        assert "return 1" in result

    def test_handles_empty_code(self):
        """Test handles empty code."""
        assert _strip_imports("") == ""

    def test_handles_code_with_only_imports(self):
        """Test handles code with only imports."""
        code = "import json\nfrom collections import defaultdict"
        result = _strip_imports(code)
        assert result.strip() == ""


class TestMakeEvaluateResponse:
    """Test _make_evaluate_response function."""

    def test_success_response_structure(self):
        """Test success response has correct structure."""
        start_time = time.perf_counter()
        result = _make_evaluate_response(
            status="success",
            start_time=start_time,
            result={"operations": []},
            stdout="hello",
            stderr="",
        )
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == {"operations": []}
        assert parsed["stdout"] == "hello"
        assert parsed["stderr"] == ""
        assert parsed["exception"] is None
        assert "elapsed_ms" in parsed
        assert isinstance(parsed["elapsed_ms"], float)

    def test_error_response_with_exception(self):
        """Test error response includes exception info."""
        start_time = time.perf_counter()
        try:
            raise ValueError("Test error message")
        except ValueError as e:
            result = _make_evaluate_response(
                status="error",
                start_time=start_time,
                stderr="Error occurred",
                exc=e,
            )
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert parsed["exception"] is not None
        assert parsed["exception"]["type"] == "ValueError"
        assert parsed["exception"]["message"] == "Test error message"
        assert "traceback" in parsed["exception"]

    def test_elapsed_ms_is_calculated(self):
        """Test elapsed_ms is properly calculated."""
        start_time = time.perf_counter() - 0.1
        result = _make_evaluate_response(status="success", start_time=start_time)
        parsed = json.loads(result)

        assert parsed["elapsed_ms"] >= 100

    def test_invalid_input_response(self):
        """Test invalid_input response structure."""
        start_time = time.perf_counter()
        result = _make_evaluate_response(
            status="invalid_input",
            start_time=start_time,
            stderr="Invalid JSON",
        )
        parsed = json.loads(result)

        assert parsed["status"] == "invalid_input"
        assert parsed["stderr"] == "Invalid JSON"


class TestExecuteOpusTool:
    """Test _execute_opus_tool function."""

    def test_calls_evaluate_python_hook_for_that_tool_name(self):
        """Test calls evaluate_python_hook for evaluate_python_hook tool."""
        with patch(
            "rossum_agent.tools.subagents.hook_debug.evaluate_python_hook", return_value='{"status": "success"}'
        ) as mock:
            result = _execute_opus_tool(
                "evaluate_python_hook",
                {"code": "def foo(): pass", "annotation_json": "{}"},
            )

            mock.assert_called_once_with(
                code="def foo(): pass",
                annotation_json="{}",
                schema_json=None,
            )
            assert result == '{"status": "success"}'

    def test_calls_search_knowledge_base_for_search_tool(self):
        """Test calls search_knowledge_base for search_knowledge_base tool."""
        mock_response = json.dumps(
            {
                "status": "success",
                "query": "hooks",
                "analysis": "analyzed",
                "source_urls": ["https://kb.rossum.ai/test"],
            }
        )
        with patch(
            "rossum_agent.tools.subagents.hook_debug.search_knowledge_base", return_value=mock_response
        ) as mock:
            result = _execute_opus_tool("search_knowledge_base", {"query": "hooks"})

            mock.assert_called_once_with("hooks")
            parsed = json.loads(result)
            assert parsed["status"] == "success"

    def test_search_knowledge_base_returns_no_results(self):
        """Test search_knowledge_base returns no_results for empty search."""
        mock_response = json.dumps({"status": "no_results", "query": "nonexistent", "message": "No results"})
        with patch("rossum_agent.tools.subagents.hook_debug.search_knowledge_base", return_value=mock_response):
            result = _execute_opus_tool("search_knowledge_base", {"query": "nonexistent"})

            parsed = json.loads(result)
            assert parsed["status"] == "no_results"

    def test_search_knowledge_base_returns_error_for_empty_query(self):
        """Test search_knowledge_base returns error for empty query."""
        result = _execute_opus_tool("search_knowledge_base", {"query": ""})
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "Query is required" in parsed["message"]

    def test_calls_call_mcp_tool_for_get_hook(self):
        """Test calls call_mcp_tool for get_hook tool."""
        with patch(
            "rossum_agent.tools.subagents.hook_debug.call_mcp_tool",
            return_value={"id": "123", "config": {"code": "def handler(p): pass"}},
        ) as mock:
            result = _execute_opus_tool("get_hook", {"hook_id": "123"})

            mock.assert_called_once_with("get_hook", {"hook_id": "123"})
            parsed = json.loads(result)
            assert parsed["id"] == "123"

    def test_calls_call_mcp_tool_for_get_annotation(self):
        """Test calls call_mcp_tool for get_annotation tool."""
        with patch(
            "rossum_agent.tools.subagents.hook_debug.call_mcp_tool",
            return_value={"id": "456", "content": []},
        ) as mock:
            result = _execute_opus_tool("get_annotation", {"annotation_id": "456"})

            mock.assert_called_once_with("get_annotation", {"annotation_id": "456"})
            assert "456" in result

    def test_calls_call_mcp_tool_for_get_schema(self):
        """Test calls call_mcp_tool for get_schema tool."""
        with patch(
            "rossum_agent.tools.subagents.hook_debug.call_mcp_tool",
            return_value={"id": "789", "content": []},
        ) as mock:
            result = _execute_opus_tool("get_schema", {"schema_id": "789"})

            mock.assert_called_once_with("get_schema", {"schema_id": "789"})
            assert "789" in result

    def test_returns_no_data_when_mcp_tool_returns_none(self):
        """Test returns 'No data returned' when call_mcp_tool returns None."""
        with patch("rossum_agent.tools.subagents.hook_debug.call_mcp_tool", return_value=None):
            result = _execute_opus_tool("get_hook", {"hook_id": "123"})

            assert result == "No data returned"

    def test_returns_unknown_tool_for_unknown_tools(self):
        """Test returns 'Unknown tool' for unknown tool names."""
        result = _execute_opus_tool("unknown_tool", {})

        assert result == "Unknown tool: unknown_tool"


class TestCallOpusForDebug:
    """Test _call_opus_for_debug function."""

    def test_creates_client_and_runs_iterations(self):
        """Test creates bedrock client and runs iterations."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = "Analysis complete"
        mock_text_block.type = "text"
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_of_turn"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response

        with (
            patch("rossum_agent.tools.subagents.base.create_bedrock_client", return_value=mock_client),
            patch("rossum_agent.tools.subagents.base.report_progress"),
            patch("rossum_agent.tools.subagents.base.report_token_usage"),
            patch("rossum_agent.tools.subagents.base.save_iteration_context"),
        ):
            result = _call_opus_for_debug("hook123", "ann456", None)

            mock_client.messages.create.assert_called_once()
            assert result.analysis == "Analysis complete"
            assert result.input_tokens == 100
            assert result.output_tokens == 50

    def test_handles_end_of_turn_stop_reason(self):
        """Test handles end_of_turn stop reason and returns text."""
        mock_client = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = "Final analysis"
        mock_text_block.type = "text"
        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_of_turn"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response

        with (
            patch("rossum_agent.tools.subagents.base.create_bedrock_client", return_value=mock_client),
            patch("rossum_agent.tools.subagents.base.report_progress"),
            patch("rossum_agent.tools.subagents.base.report_token_usage"),
            patch("rossum_agent.tools.subagents.base.save_iteration_context"),
        ):
            result = _call_opus_for_debug("h1", "a1", None)

            assert result.analysis == "Final analysis"

    def test_handles_tool_use_blocks(self):
        """Test handles tool use blocks and calls tools."""
        mock_client = MagicMock()

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "get_hook"
        mock_tool_block.input = {"hook_id": "123"}
        mock_tool_block.id = "tool_use_id_1"

        first_response = MagicMock()
        first_response.content = [mock_tool_block]
        first_response.stop_reason = "tool_use"
        first_response.usage.input_tokens = 100
        first_response.usage.output_tokens = 50

        mock_text_block = MagicMock()
        mock_text_block.text = "Done"
        mock_text_block.type = "text"
        second_response = MagicMock()
        second_response.content = [mock_text_block]
        second_response.stop_reason = "end_of_turn"
        second_response.usage.input_tokens = 150
        second_response.usage.output_tokens = 75

        mock_client.messages.create.side_effect = [first_response, second_response]

        with (
            patch("rossum_agent.tools.subagents.base.create_bedrock_client", return_value=mock_client),
            patch("rossum_agent.tools.subagents.base.report_progress"),
            patch("rossum_agent.tools.subagents.base.report_token_usage"),
            patch("rossum_agent.tools.subagents.base.save_iteration_context"),
            patch("rossum_agent.tools.subagents.hook_debug._execute_opus_tool", return_value='{"id": "123"}'),
            patch(
                "rossum_agent.tools.subagents.hook_debug._extract_and_analyze_web_search_results", return_value=None
            ),
        ):
            result = _call_opus_for_debug("h1", "a1", None)

            assert result.analysis == "Done"
            assert result.input_tokens == 250
            assert result.output_tokens == 125
            assert mock_client.messages.create.call_count == 2

    def test_handles_tool_execution_failure(self):
        """Test handles tool execution failure gracefully."""
        mock_client = MagicMock()

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "get_hook"
        mock_tool_block.input = {"hook_id": "123"}
        mock_tool_block.id = "tool_use_id_1"

        first_response = MagicMock()
        first_response.content = [mock_tool_block]
        first_response.stop_reason = "tool_use"
        first_response.usage.input_tokens = 100
        first_response.usage.output_tokens = 50

        mock_text_block = MagicMock()
        mock_text_block.text = "Handled error"
        mock_text_block.type = "text"
        second_response = MagicMock()
        second_response.content = [mock_text_block]
        second_response.stop_reason = "end_of_turn"
        second_response.usage.input_tokens = 150
        second_response.usage.output_tokens = 75

        mock_client.messages.create.side_effect = [first_response, second_response]

        with (
            patch("rossum_agent.tools.subagents.base.create_bedrock_client", return_value=mock_client),
            patch("rossum_agent.tools.subagents.base.report_progress"),
            patch("rossum_agent.tools.subagents.base.report_token_usage"),
            patch("rossum_agent.tools.subagents.base.save_iteration_context"),
            patch(
                "rossum_agent.tools.subagents.hook_debug._execute_opus_tool", side_effect=RuntimeError("Tool failed")
            ),
            patch(
                "rossum_agent.tools.subagents.hook_debug._extract_and_analyze_web_search_results", return_value=None
            ),
        ):
            result = _call_opus_for_debug("h1", "a1", None)

            assert result.analysis == "Handled error"

    def test_returns_error_on_exception(self):
        """Test returns error message on exception."""
        with patch(
            "rossum_agent.tools.subagents.base.create_bedrock_client",
            side_effect=RuntimeError("Connection failed"),
        ):
            result = _call_opus_for_debug("h1", "a1", None)

            assert "Error calling Opus sub-agent" in result.analysis
            assert "Connection failed" in result.analysis
            assert result.input_tokens == 0
            assert result.output_tokens == 0

    def test_returns_no_analysis_when_no_text_blocks(self):
        """Test returns 'No analysis provided' when no text blocks."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = []
        mock_response.stop_reason = "end_of_turn"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response

        with (
            patch("rossum_agent.tools.subagents.base.create_bedrock_client", return_value=mock_client),
            patch("rossum_agent.tools.subagents.base.report_progress"),
            patch("rossum_agent.tools.subagents.base.report_token_usage"),
            patch("rossum_agent.tools.subagents.base.save_iteration_context"),
        ):
            result = _call_opus_for_debug("h1", "a1", None)

            assert result.analysis == "No analysis provided"

    def test_includes_schema_id_in_prompt_when_provided(self):
        """Test includes schema_id in user content when provided."""
        mock_client = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = "Done"
        mock_text_block.type = "text"
        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_of_turn"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response

        with (
            patch("rossum_agent.tools.subagents.base.create_bedrock_client", return_value=mock_client),
            patch("rossum_agent.tools.subagents.base.report_progress"),
            patch("rossum_agent.tools.subagents.base.report_token_usage"),
            patch("rossum_agent.tools.subagents.base.save_iteration_context"),
        ):
            _call_opus_for_debug("h1", "a1", "schema999")

            call_args = mock_client.messages.create.call_args
            messages = call_args.kwargs["messages"]
            user_content = messages[0]["content"]
            assert "schema999" in user_content

    def test_handles_evaluate_python_hook_result_logging(self):
        """Test logs evaluate_python_hook results properly."""
        mock_client = MagicMock()

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "evaluate_python_hook"
        mock_tool_block.input = {"code": "def handler(p): pass", "annotation_json": "{}"}
        mock_tool_block.id = "tool_use_id_1"

        first_response = MagicMock()
        first_response.content = [mock_tool_block]
        first_response.stop_reason = "tool_use"
        first_response.usage.input_tokens = 100
        first_response.usage.output_tokens = 50

        mock_text_block = MagicMock()
        mock_text_block.text = "Done"
        mock_text_block.type = "text"
        second_response = MagicMock()
        second_response.content = [mock_text_block]
        second_response.stop_reason = "end_of_turn"
        second_response.usage.input_tokens = 150
        second_response.usage.output_tokens = 75

        mock_client.messages.create.side_effect = [first_response, second_response]

        eval_result = json.dumps({"status": "success", "exception": None})

        with (
            patch("rossum_agent.tools.subagents.base.create_bedrock_client", return_value=mock_client),
            patch("rossum_agent.tools.subagents.base.report_progress"),
            patch("rossum_agent.tools.subagents.base.report_token_usage"),
            patch("rossum_agent.tools.subagents.base.save_iteration_context"),
            patch("rossum_agent.tools.subagents.hook_debug._execute_opus_tool", return_value=eval_result),
            patch(
                "rossum_agent.tools.subagents.hook_debug._extract_and_analyze_web_search_results", return_value=None
            ),
        ):
            result = _call_opus_for_debug("h1", "a1", None)

            assert result.analysis == "Done"


class TestEvaluatePythonHook:
    """Test evaluate_python_hook tool function."""

    def test_with_helper_functions_defined_in_code(self):
        """Test execution with helper functions defined in code."""
        code = """
def helper(x):
    return x * 2

def rossum_hook_request_handler(payload):
    value = payload["annotation"]["value"]
    return {"result": helper(value)}
"""
        annotation_json = json.dumps({"value": 21})
        result = evaluate_python_hook(code, annotation_json)
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == {"result": 42}

    def test_available_modules_datetime(self):
        """Test datetime module is available."""
        code = """
def rossum_hook_request_handler(payload):
    return {"year": datetime.datetime.now().year}
"""
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert "year" in parsed["result"]

    def test_available_modules_re(self):
        """Test re module is available."""
        code = """
def rossum_hook_request_handler(payload):
    match = re.search(r'\\d+', 'abc123')
    return {"match": match.group()}
"""
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"]["match"] == "123"

    def test_available_modules_collections(self):
        """Test collections module is available."""
        code = """
def rossum_hook_request_handler(payload):
    d = collections.defaultdict(list)
    d['key'].append(1)
    return {"result": dict(d)}
"""
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"]["result"] == {"key": [1]}

    def test_available_modules_decimal(self):
        """Test Decimal is available."""
        code = """
def rossum_hook_request_handler(payload):
    return {"value": str(Decimal("10.5") + Decimal("2.5"))}
"""
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"]["value"] == "13.0"

    def test_available_modules_json(self):
        """Test json module is available."""
        code = """
def rossum_hook_request_handler(payload):
    return json.loads('{"nested": "value"}')
"""
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"]["nested"] == "value"

    def test_available_modules_math(self):
        """Test math module is available."""
        code = """
def rossum_hook_request_handler(payload):
    return {"sqrt": math.sqrt(16)}
"""
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"]["sqrt"] == 4.0

    def test_available_modules_itertools(self):
        """Test itertools module is available."""
        code = """
def rossum_hook_request_handler(payload):
    return {"chain": list(itertools.chain([1, 2], [3, 4]))}
"""
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"]["chain"] == [1, 2, 3, 4]

    def test_available_modules_functools(self):
        """Test functools module is available."""
        code = """
def rossum_hook_request_handler(payload):
    add = lambda x, y: x + y
    add_5 = functools.partial(add, 5)
    return {"result": add_5(3)}
"""
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"]["result"] == 8

    def test_available_modules_string(self):
        """Test string module is available."""
        code = """
def rossum_hook_request_handler(payload):
    return {"digits": string.digits}
"""
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"]["digits"] == "0123456789"

    def test_empty_code_returns_invalid_input(self):
        """Test empty code returns invalid_input status."""
        result = evaluate_python_hook("", "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "invalid_input"
        assert "No code provided" in parsed["stderr"]

    def test_invalid_annotation_json_returns_error(self):
        """Test invalid annotation JSON returns error."""
        code = "def rossum_hook_request_handler(payload): pass"
        result = evaluate_python_hook(code, "not valid json")
        parsed = json.loads(result)

        assert parsed["status"] == "invalid_input"
        assert "Invalid annotation_json" in parsed["stderr"]

    def test_invalid_schema_json_returns_error(self):
        """Test invalid schema JSON returns error."""
        code = "def rossum_hook_request_handler(payload): pass"
        result = evaluate_python_hook(code, "{}", "not valid json")
        parsed = json.loads(result)

        assert parsed["status"] == "invalid_input"
        assert "Invalid schema_json" in parsed["stderr"]

    def test_missing_handler_returns_error(self):
        """Test missing rossum_hook_request_handler returns error."""
        code = "def other_function(x): return x"
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "rossum_hook_request_handler" in parsed["exception"]["message"]

    def test_captures_stdout(self):
        """Test captures stdout from print statements."""
        code = """
def rossum_hook_request_handler(payload):
    print("Hello, world!")
    return None
"""
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert "Hello, world!" in parsed["stdout"]

    def test_handler_exception_returns_error(self):
        """Test handler exception returns error status."""
        code = """
def rossum_hook_request_handler(payload):
    raise ValueError("Something went wrong")
"""
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert parsed["exception"]["type"] == "ValueError"
        assert "Something went wrong" in parsed["exception"]["message"]

    def test_schema_passed_to_handler(self):
        """Test schema is passed to handler when provided."""
        code = """
def rossum_hook_request_handler(payload):
    return {"has_schema": "schema" in payload}
"""
        result = evaluate_python_hook(code, "{}", '{"content": []}')
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"]["has_schema"] is True

    def test_imports_are_stripped(self):
        """Test import statements are stripped from code."""
        code = """
import json
from decimal import Decimal

def rossum_hook_request_handler(payload):
    return {"value": str(Decimal("1.5"))}
"""
        result = evaluate_python_hook(code, "{}")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"]["value"] == "1.5"


class TestDebugHook:
    """Test debug_hook tool function."""

    def test_with_both_hook_id_and_annotation_id(self):
        """Test debug_hook with required hook_id and annotation_id."""
        mock_result = SubAgentResult(
            analysis="Analysis: The hook is working correctly.",
            input_tokens=100,
            output_tokens=50,
            iterations_used=2,
        )
        with patch(
            "rossum_agent.tools.subagents.hook_debug._call_opus_for_debug",
            return_value=mock_result,
        ):
            result = debug_hook(hook_id="123", annotation_id="456")
            parsed = json.loads(result)

            assert parsed["hook_id"] == "123"
            assert parsed["annotation_id"] == "456"
            assert "Analysis" in parsed["analysis"]
            assert "elapsed_ms" in parsed
            assert parsed["input_tokens"] == 100
            assert parsed["output_tokens"] == 50

    def test_with_schema_id(self):
        """Test debug_hook with optional schema_id."""
        mock_result = SubAgentResult(
            analysis="Analysis with schema",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )
        with patch(
            "rossum_agent.tools.subagents.hook_debug._call_opus_for_debug",
            return_value=mock_result,
        ) as mock:
            result = debug_hook(hook_id="123", annotation_id="456", schema_id="789")
            parsed = json.loads(result)

            mock.assert_called_once_with("123", "456", "789")
            assert "elapsed_ms" in parsed

    def test_timing_is_measured(self):
        """Test that elapsed_ms is properly measured."""
        mock_result = SubAgentResult(
            analysis="Analysis",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )
        with patch(
            "rossum_agent.tools.subagents.hook_debug._call_opus_for_debug",
            return_value=mock_result,
        ):
            result = debug_hook(hook_id="h1", annotation_id="a1")
            parsed = json.loads(result)

            assert "elapsed_ms" in parsed
            assert isinstance(parsed["elapsed_ms"], float)
            assert parsed["elapsed_ms"] >= 0

    def test_missing_hook_id_returns_error(self):
        """Test missing hook_id returns error."""
        result = debug_hook(hook_id="", annotation_id="456")
        parsed = json.loads(result)

        assert "error" in parsed
        assert "hook_id" in parsed["error"]

    def test_missing_annotation_id_returns_error(self):
        """Test missing annotation_id returns error."""
        result = debug_hook(hook_id="123", annotation_id="")
        parsed = json.loads(result)

        assert "error" in parsed
        assert "annotation_id" in parsed["error"]


class TestExtractWebSearchTextFromBlock:
    """Test _extract_web_search_text_from_block function."""

    def test_non_web_search_block_returns_none(self):
        """Test that non-web_search_tool_result block returns None."""
        block = MagicMock()
        block.type = "text"

        result = _extract_web_search_text_from_block(block)

        assert result is None

    def test_block_without_type_returns_none(self):
        """Test that block without type attribute returns None."""
        block = MagicMock(spec=[])

        result = _extract_web_search_text_from_block(block)

        assert result is None

    def test_web_search_result_error_raises_web_search_error(self):
        """Test that web_search_result_error raises WebSearchError."""
        error_result = MagicMock()
        error_result.type = "web_search_result_error"
        error_result.error_code = "rate_limited"
        error_result.message = "Too many requests"

        block = MagicMock()
        block.type = "web_search_tool_result"
        block.content = [error_result]

        with pytest.raises(WebSearchError, match="rate_limited - Too many requests"):
            _extract_web_search_text_from_block(block)

    def test_empty_results_returns_no_results_marker(self):
        """Test that empty results returns _WEB_SEARCH_NO_RESULTS."""
        block = MagicMock()
        block.type = "web_search_tool_result"
        block.content = []

        result = _extract_web_search_text_from_block(block)

        assert result == _WEB_SEARCH_NO_RESULTS

    def test_valid_results_returns_formatted_text(self):
        """Test that valid results return formatted text."""
        search_result = MagicMock()
        search_result.type = "web_search_result"
        search_result.title = "Rossum Hooks Guide"
        search_result.url = "https://knowledge-base.rossum.ai/docs/hooks"
        search_result.page_content = "This is the hook documentation content."

        block = MagicMock()
        block.type = "web_search_tool_result"
        block.content = [search_result]

        result = _extract_web_search_text_from_block(block)

        assert "## Rossum Hooks Guide" in result
        assert "URL: https://knowledge-base.rossum.ai/docs/hooks" in result
        assert "This is the hook documentation content." in result

    def test_multiple_results_are_joined(self):
        """Test that multiple results are joined with separator."""
        result1 = MagicMock()
        result1.type = "web_search_result"
        result1.title = "Page 1"
        result1.url = "https://example.com/1"
        result1.page_content = "Content 1"

        result2 = MagicMock()
        result2.type = "web_search_result"
        result2.title = "Page 2"
        result2.url = "https://example.com/2"
        result2.page_content = "Content 2"

        block = MagicMock()
        block.type = "web_search_tool_result"
        block.content = [result1, result2]

        result = _extract_web_search_text_from_block(block)

        assert "## Page 1" in result
        assert "## Page 2" in result
        assert "\n---\n" in result


class TestExtractAndAnalyzeWebSearchResults:
    """Test _extract_and_analyze_web_search_results function."""

    def test_non_web_search_block_returns_none(self):
        """Test that non-web_search block returns None."""
        block = MagicMock()
        block.type = "text"

        result = _extract_and_analyze_web_search_results(block, iteration=1, max_iterations=5)

        assert result is None

    def test_no_results_returns_appropriate_dict(self):
        """Test that no results returns appropriate tool_result dict."""
        block = MagicMock()
        block.type = "web_search_tool_result"
        block.id = "tool_use_123"
        block.content = []

        result = _extract_and_analyze_web_search_results(block, iteration=1, max_iterations=5)

        assert result is not None
        assert result["type"] == "tool_result"
        assert result["tool_use_id"] == "tool_use_123"
        assert "no results" in result["content"]

    def test_results_with_opus_analysis(self):
        """Test results are analyzed with Opus."""
        search_result = MagicMock()
        search_result.type = "web_search_result"
        search_result.title = "Test Page"
        search_result.url = "https://example.com"
        search_result.page_content = "Test content"

        block = MagicMock()
        block.type = "web_search_tool_result"
        block.id = "tool_use_456"
        block.search_query = "test query"
        block.content = [search_result]

        with patch(
            "rossum_agent.tools.subagents.hook_debug._call_opus_for_web_search_analysis",
            return_value="Opus analyzed this content",
        ) as mock_opus:
            result = _extract_and_analyze_web_search_results(block, iteration=2, max_iterations=10)

            assert result is not None
            assert result["type"] == "tool_result"
            assert result["tool_use_id"] == "tool_use_456"
            assert "Analyzed Rossum Knowledge Base" in result["content"]
            assert "Opus analyzed this content" in result["content"]
            mock_opus.assert_called_once_with("test query", "## Test Page\nURL: https://example.com\n\nTest content\n")

    def test_uses_default_query_when_search_query_missing(self):
        """Test that default query is used when block.search_query is missing."""
        search_result = MagicMock()
        search_result.type = "web_search_result"
        search_result.title = "Page"
        search_result.url = "https://example.com"
        search_result.page_content = "Content"

        block = MagicMock()
        block.type = "web_search_tool_result"
        block.id = "tool_id"
        block.content = [search_result]
        del block.search_query

        with patch(
            "rossum_agent.tools.subagents.hook_debug._call_opus_for_web_search_analysis",
            return_value="Analysis",
        ) as mock_opus:
            _extract_and_analyze_web_search_results(block, iteration=1, max_iterations=5)

            mock_opus.assert_called_once()
            assert mock_opus.call_args[0][0] == "Rossum documentation"
