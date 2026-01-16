"""Tests for rossum_agent.tools.subagents.schema_patching module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from rossum_agent.tools.subagents.schema_patching import (
    _GET_SCHEMA_TOOL,
    _OPUS_TOOLS,
    _SCHEMA_PATCHING_SYSTEM_PROMPT,
    _UPDATE_SCHEMA_CONTENT_TOOL,
    _call_opus_for_patching,
    _execute_opus_tool,
    patch_schema_with_subagent,
)


class TestConstants:
    """Test module constants."""

    def test_system_prompt_is_concise(self):
        """Test that system prompt follows Opus best practices (goal-oriented, uses tables)."""
        assert "Goal:" in _SCHEMA_PATCHING_SYSTEM_PROMPT
        assert "| Property |" in _SCHEMA_PATCHING_SYSTEM_PROMPT or "| Type |" in _SCHEMA_PATCHING_SYSTEM_PROMPT

    def test_system_prompt_describes_bulk_workflow(self):
        """Test that system prompt describes efficient bulk update workflow."""
        assert "update_schema_content" in _SCHEMA_PATCHING_SYSTEM_PROMPT
        assert "one" in _SCHEMA_PATCHING_SYSTEM_PROMPT.lower() or "ONE" in _SCHEMA_PATCHING_SYSTEM_PROMPT

    def test_get_schema_tool_has_required_fields(self):
        """Test _GET_SCHEMA_TOOL has required schema fields."""
        assert _GET_SCHEMA_TOOL["name"] == "get_schema"
        assert "description" in _GET_SCHEMA_TOOL
        assert "input_schema" in _GET_SCHEMA_TOOL
        assert _GET_SCHEMA_TOOL["input_schema"]["type"] == "object"
        assert "schema_id" in _GET_SCHEMA_TOOL["input_schema"]["properties"]
        assert "schema_id" in _GET_SCHEMA_TOOL["input_schema"]["required"]

    def test_update_schema_content_tool_has_required_fields(self):
        """Test _UPDATE_SCHEMA_CONTENT_TOOL has required schema fields."""
        assert _UPDATE_SCHEMA_CONTENT_TOOL["name"] == "update_schema_content"
        assert "description" in _UPDATE_SCHEMA_CONTENT_TOOL
        assert "input_schema" in _UPDATE_SCHEMA_CONTENT_TOOL
        props = _UPDATE_SCHEMA_CONTENT_TOOL["input_schema"]["properties"]
        assert "schema_id" in props
        assert "content" in props
        required = _UPDATE_SCHEMA_CONTENT_TOOL["input_schema"]["required"]
        assert "schema_id" in required
        assert "content" in required

    def test_opus_tools_list_contains_required_tools(self):
        """Test _OPUS_TOOLS contains get_schema and update_schema_content."""
        tool_names = [t["name"] for t in _OPUS_TOOLS]
        assert "get_schema" in tool_names
        assert "update_schema_content" in tool_names


class TestExecuteOpusTool:
    """Test _execute_opus_tool function."""

    def test_unknown_tool_returns_error(self):
        """Test that unknown tool returns error message."""
        result = _execute_opus_tool("unknown_tool", {})
        assert "Unknown tool" in result

    def test_get_schema_calls_mcp(self):
        """Test get_schema tool calls MCP."""
        with patch("rossum_agent.tools.subagents.schema_patching._call_mcp_tool") as mock_mcp:
            mock_mcp.return_value = {"id": "123", "content": []}
            result = _execute_opus_tool("get_schema", {"schema_id": "123"})

            mock_mcp.assert_called_once_with("get_schema", {"schema_id": "123"})
            parsed = json.loads(result)
            assert parsed["id"] == "123"

    def test_update_schema_content_calls_mcp_update_schema(self):
        """Test update_schema_content tool calls MCP update_schema with content wrapper."""
        with patch("rossum_agent.tools.subagents.schema_patching._call_mcp_tool") as mock_mcp:
            mock_mcp.return_value = {"id": 123, "content": [{"category": "section", "id": "s1"}]}
            new_content = [{"category": "section", "id": "header", "children": []}]
            result = _execute_opus_tool("update_schema_content", {"schema_id": 123, "content": new_content})

            mock_mcp.assert_called_once_with(
                "update_schema", {"schema_id": 123, "schema_data": {"content": new_content}}
            )
            parsed = json.loads(result)
            assert parsed["id"] == 123


class TestPatchSchemaWithSubagent:
    """Test patch_schema_with_subagent tool function."""

    def test_empty_schema_id_returns_error(self):
        """Test that empty schema_id returns error."""
        result = patch_schema_with_subagent(schema_id="", changes="[]")
        parsed = json.loads(result)

        assert "error" in parsed
        assert "schema_id" in parsed["error"]

    def test_invalid_changes_json_returns_error(self):
        """Test that invalid changes JSON returns error."""
        result = patch_schema_with_subagent(schema_id="123", changes="not valid json")
        parsed = json.loads(result)

        assert "error" in parsed
        assert "Invalid changes JSON" in parsed["error"]

    def test_empty_changes_returns_error(self):
        """Test that empty changes list returns error."""
        result = patch_schema_with_subagent(schema_id="123", changes="[]")
        parsed = json.loads(result)

        assert "error" in parsed
        assert "No changes" in parsed["error"]

    def test_valid_request_calls_opus(self):
        """Test that valid request calls Opus sub-agent."""
        changes = [{"action": "add", "id": "new_field", "parent_section": "header", "type": "string"}]
        with patch(
            "rossum_agent.tools.subagents.schema_patching._call_opus_for_patching",
            return_value="Added field new_field to header section",
        ) as mock_opus:
            result = patch_schema_with_subagent(schema_id="123", changes=json.dumps(changes))
            parsed = json.loads(result)

            mock_opus.assert_called_once_with("123", changes)
            assert parsed["schema_id"] == "123"
            assert parsed["changes_requested"] == 1
            assert "Added field" in parsed["analysis"]

    def test_timing_is_measured(self):
        """Test that elapsed_ms is properly measured."""
        changes = [{"id": "f1", "parent_section": "s1", "type": "string"}]
        with patch(
            "rossum_agent.tools.subagents.schema_patching._call_opus_for_patching",
            return_value="Done",
        ):
            result = patch_schema_with_subagent(schema_id="123", changes=json.dumps(changes))
            parsed = json.loads(result)

            assert "elapsed_ms" in parsed
            assert isinstance(parsed["elapsed_ms"], float)
            assert parsed["elapsed_ms"] >= 0


class TestCallOpusForPatching:
    """Test _call_opus_for_patching function."""

    def test_reports_progress(self):
        """Test that progress is reported during patching."""
        progress_calls: list = []

        def capture_progress(progress):
            progress_calls.append(progress)

        mock_response = MagicMock()
        mock_response.stop_reason = "end_of_turn"
        mock_response.content = [MagicMock(text="Patching complete", type="text")]
        mock_response.content[0].text = "Patching complete"

        with (
            patch("rossum_agent.tools.subagents.schema_patching.create_bedrock_client") as mock_client,
            patch("rossum_agent.tools.subagents.schema_patching.report_progress", side_effect=capture_progress),
            patch("rossum_agent.tools.subagents.schema_patching._save_patching_context"),
        ):
            mock_client.return_value.messages.create.return_value = mock_response

            changes = [{"id": "field1", "parent_section": "header", "type": "string"}]
            _call_opus_for_patching("123", changes)

            assert len(progress_calls) >= 1
            assert progress_calls[0].tool_name == "patch_schema"

    def test_iterates_with_tool_use(self):
        """Test that sub-agent iterates when tools are used."""
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.name = "get_schema"
        tool_use_block.input = {"schema_id": "123"}
        tool_use_block.id = "tool_1"

        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_use_block]

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Schema updated successfully"

        second_response = MagicMock()
        second_response.stop_reason = "end_of_turn"
        second_response.content = [text_block]

        with (
            patch("rossum_agent.tools.subagents.schema_patching.create_bedrock_client") as mock_client,
            patch("rossum_agent.tools.subagents.schema_patching.report_progress"),
            patch("rossum_agent.tools.subagents.schema_patching._save_patching_context"),
            patch("rossum_agent.tools.subagents.schema_patching._execute_opus_tool", return_value='{"id": "123"}'),
        ):
            mock_client.return_value.messages.create.side_effect = [first_response, second_response]

            changes = [{"id": "field1", "parent_section": "header", "type": "string"}]
            result = _call_opus_for_patching("123", changes)

            assert "Schema updated successfully" in result
            assert mock_client.return_value.messages.create.call_count == 2

    def test_max_iterations_reduced(self):
        """Test that max iterations is reasonable for bulk update approach."""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_of_turn"
        mock_response.content = [MagicMock(text="Done", type="text")]
        mock_response.content[0].text = "Done"

        with (
            patch("rossum_agent.tools.subagents.schema_patching.create_bedrock_client") as mock_client,
            patch("rossum_agent.tools.subagents.schema_patching.report_progress"),
            patch("rossum_agent.tools.subagents.schema_patching._save_patching_context") as mock_save,
        ):
            mock_client.return_value.messages.create.return_value = mock_response

            changes = [{"id": "field1", "parent_section": "header", "type": "string"}]
            _call_opus_for_patching("123", changes)

            saved_context = mock_save.call_args[0]
            assert saved_context[1] <= 10
