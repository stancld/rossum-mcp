"""Tests for rossum_agent.tools.subagents.schema_patching module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from rossum_agent.tools.subagents.schema_patching import (
    _APPLY_SCHEMA_CHANGES_TOOL,
    _GET_FULL_SCHEMA_TOOL,
    _GET_SCHEMA_TREE_STRUCTURE_TOOL,
    _OPUS_TOOLS,
    _SCHEMA_PATCHING_SYSTEM_PROMPT,
    _add_fields_to_content,
    _apply_schema_changes,
    _build_field_node,
    _call_opus_for_patching,
    _collect_field_ids,
    _execute_opus_tool,
    _filter_content,
    _save_patching_context,
    _schema_content_cache,
    patch_schema_with_subagent,
)


class TestConstants:
    """Test module constants."""

    def test_system_prompt_is_goal_oriented(self):
        """Test that system prompt follows Opus best practices."""
        assert "Goal:" in _SCHEMA_PATCHING_SYSTEM_PROMPT

    def test_system_prompt_describes_programmatic_workflow(self):
        """Test that system prompt describes deterministic workflow."""
        assert "get_schema_tree_structure" in _SCHEMA_PATCHING_SYSTEM_PROMPT
        assert "get_full_schema" in _SCHEMA_PATCHING_SYSTEM_PROMPT
        assert "apply_schema_changes" in _SCHEMA_PATCHING_SYSTEM_PROMPT

    def test_opus_tools_contains_all_required_tools(self):
        """Test that _OPUS_TOOLS contains all three tools."""
        tool_names = [t["name"] for t in _OPUS_TOOLS]
        assert "get_schema_tree_structure" in tool_names
        assert "get_full_schema" in tool_names
        assert "apply_schema_changes" in tool_names

    def test_get_schema_tree_structure_tool_schema(self):
        """Test get_schema_tree_structure tool has correct schema."""
        assert _GET_SCHEMA_TREE_STRUCTURE_TOOL["name"] == "get_schema_tree_structure"
        assert "schema_id" in _GET_SCHEMA_TREE_STRUCTURE_TOOL["input_schema"]["required"]

    def test_get_full_schema_tool_schema(self):
        """Test get_full_schema tool has correct schema."""
        assert _GET_FULL_SCHEMA_TOOL["name"] == "get_full_schema"
        assert "schema_id" in _GET_FULL_SCHEMA_TOOL["input_schema"]["required"]

    def test_apply_schema_changes_tool_schema(self):
        """Test apply_schema_changes tool has correct schema."""
        assert _APPLY_SCHEMA_CHANGES_TOOL["name"] == "apply_schema_changes"
        props = _APPLY_SCHEMA_CHANGES_TOOL["input_schema"]["properties"]
        assert "schema_id" in props
        assert "fields_to_keep" in props
        assert "fields_to_add" in props


class TestCollectFieldIds:
    """Test _collect_field_ids function."""

    def test_empty_content(self):
        """Test with empty content."""
        assert _collect_field_ids([]) == set()

    def test_flat_datapoints(self):
        """Test with flat datapoints."""
        content = [
            {"id": "field1", "category": "datapoint"},
            {"id": "field2", "category": "datapoint"},
        ]
        assert _collect_field_ids(content) == {"field1", "field2"}

    def test_section_with_children(self):
        """Test section with children."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint"},
                    {"id": "field2", "category": "datapoint"},
                ],
            }
        ]
        assert _collect_field_ids(content) == {"section1", "field1", "field2"}

    def test_multivalue_with_tuple(self):
        """Test multivalue (table) with tuple children."""
        content = [
            {
                "id": "table1",
                "category": "multivalue",
                "children": {
                    "id": "row1",
                    "category": "tuple",
                    "children": [
                        {"id": "col1", "category": "datapoint"},
                        {"id": "col2", "category": "datapoint"},
                    ],
                },
            }
        ]
        assert _collect_field_ids(content) == {"table1", "row1", "col1", "col2"}

    def test_nested_structure(self):
        """Test deeply nested structure."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint"},
                    {
                        "id": "table1",
                        "category": "multivalue",
                        "children": {
                            "id": "row1",
                            "category": "tuple",
                            "children": [{"id": "col1", "category": "datapoint"}],
                        },
                    },
                ],
            }
        ]
        ids = _collect_field_ids(content)
        assert ids == {"section1", "field1", "table1", "row1", "col1"}


class TestFilterContent:
    """Test _filter_content function."""

    def test_keep_all_fields(self):
        """Test keeping all fields."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [{"id": "field1", "category": "datapoint"}],
            }
        ]
        filtered, removed = _filter_content(content, {"section1", "field1"})
        assert len(filtered) == 1
        assert filtered[0]["children"][0]["id"] == "field1"
        assert removed == []

    def test_remove_datapoint(self):
        """Test removing a datapoint."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint"},
                    {"id": "field2", "category": "datapoint"},
                ],
            }
        ]
        filtered, removed = _filter_content(content, {"field1"})
        assert len(filtered[0]["children"]) == 1
        assert filtered[0]["children"][0]["id"] == "field1"
        assert "field2" in removed

    def test_sections_always_preserved(self):
        """Test that sections are always preserved even if not in keep set."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [{"id": "field1", "category": "datapoint"}],
            }
        ]
        filtered, _removed = _filter_content(content, {"field1"})
        assert len(filtered) == 1
        assert filtered[0]["id"] == "section1"

    def test_remove_multivalue(self):
        """Test removing a multivalue."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint"},
                    {
                        "id": "table1",
                        "category": "multivalue",
                        "children": {"id": "row1", "category": "tuple", "children": []},
                    },
                ],
            }
        ]
        filtered, removed = _filter_content(content, {"field1"})
        assert len(filtered[0]["children"]) == 1
        assert "table1" in removed

    def test_keep_multivalue_filter_columns(self):
        """Test keeping multivalue but filtering its columns."""
        content = [
            {
                "id": "table1",
                "category": "multivalue",
                "children": {
                    "id": "row1",
                    "category": "tuple",
                    "children": [
                        {"id": "col1", "category": "datapoint"},
                        {"id": "col2", "category": "datapoint"},
                    ],
                },
            }
        ]
        filtered, removed = _filter_content(content, {"table1", "col1"})
        tuple_children = filtered[0]["children"]["children"]
        assert len(tuple_children) == 1
        assert tuple_children[0]["id"] == "col1"
        assert "col2" in removed

    def test_multivalue_preserved_when_children_kept(self):
        """Test that multivalue is preserved when its children are in fields_to_keep.

        Regression test: when user specifies table columns (e.g., Code, Description)
        in fields_to_keep, the parent multivalue (line_items) should be preserved
        even if not explicitly listed.
        """
        content = [
            {
                "id": "line_items_section",
                "category": "section",
                "children": [
                    {
                        "id": "line_items",
                        "category": "multivalue",
                        "children": {
                            "id": "line_item",
                            "category": "tuple",
                            "children": [
                                {"id": "item_code", "category": "datapoint", "type": "string"},
                                {"id": "item_description", "category": "datapoint", "type": "string"},
                                {"id": "item_quantity", "category": "datapoint", "type": "number"},
                                {"id": "item_unit_price", "category": "datapoint", "type": "number"},
                                {"id": "item_total", "category": "datapoint", "type": "number"},
                            ],
                        },
                    },
                ],
            }
        ]
        filtered, removed = _filter_content(content, {"item_code", "item_description", "item_quantity"})

        assert len(filtered) == 1
        assert filtered[0]["id"] == "line_items_section"

        section_children = filtered[0]["children"]
        assert len(section_children) == 1
        assert section_children[0]["id"] == "line_items"
        assert section_children[0]["category"] == "multivalue"

        tuple_children = section_children[0]["children"]["children"]
        assert len(tuple_children) == 3
        kept_ids = {c["id"] for c in tuple_children}
        assert kept_ids == {"item_code", "item_description", "item_quantity"}

        assert "item_unit_price" in removed
        assert "item_total" in removed
        assert "line_items" not in removed


class TestBuildFieldNode:
    """Test _build_field_node function."""

    def test_basic_string_field(self):
        """Test building basic string field."""
        spec = {"id": "my_field", "label": "My Field", "type": "string"}
        node = _build_field_node(spec)

        assert node["id"] == "my_field"
        assert node["label"] == "My Field"
        assert node["category"] == "datapoint"
        assert node["type"] == "string"

    def test_multiline_field(self):
        """Test building multiline string field."""
        spec = {"id": "my_field", "label": "My Field", "type": "string", "multiline": True}
        node = _build_field_node(spec)

        assert node["type"] == "string"
        assert node["ui_configuration"] == {"type": "captured-multiline"}

    def test_number_field(self):
        """Test building number field."""
        spec = {"id": "amount", "label": "Amount", "type": "number"}
        node = _build_field_node(spec)

        assert node["type"] == "number"

    def test_integer_field(self):
        """Test building integer field with format."""
        spec = {"id": "qty", "label": "Quantity", "type": "number", "format": "#"}
        node = _build_field_node(spec)

        assert node["type"] == "number"
        assert node["format"] == "#"

    def test_enum_field(self):
        """Test building enum field with options."""
        spec = {
            "id": "status",
            "label": "Status",
            "type": "enum",
            "options": [{"value": "active", "label": "Active"}, {"value": "inactive", "label": "Inactive"}],
        }
        node = _build_field_node(spec)

        assert node["type"] == "enum"
        assert len(node["options"]) == 2

    def test_hidden_field(self):
        """Test building hidden field."""
        spec = {"id": "internal", "label": "Internal", "type": "string", "hidden": True}
        node = _build_field_node(spec)

        assert node["hidden"] is True

    def test_rir_field_names(self):
        """Test building field with rir_field_names."""
        spec = {"id": "invoice_id", "label": "Invoice ID", "type": "string", "rir_field_names": ["invoice_number"]}
        node = _build_field_node(spec)

        assert node["rir_field_names"] == ["invoice_number"]


class TestAddFieldsToContent:
    """Test _add_fields_to_content function."""

    def test_add_field_to_section(self):
        """Test adding field to a section."""
        content = [{"id": "header", "category": "section", "children": []}]
        fields_to_add = [{"id": "new_field", "label": "New Field", "parent_section": "header", "type": "string"}]

        modified, added = _add_fields_to_content(content, fields_to_add)

        assert len(modified[0]["children"]) == 1
        assert modified[0]["children"][0]["id"] == "new_field"
        assert "new_field" in added

    def test_add_field_to_nonexistent_section(self):
        """Test adding field to nonexistent section."""
        content = [{"id": "header", "category": "section", "children": []}]
        fields_to_add = [{"id": "new_field", "label": "New Field", "parent_section": "footer", "type": "string"}]

        modified, added = _add_fields_to_content(content, fields_to_add)

        assert len(modified[0]["children"]) == 0
        assert added == []

    def test_add_field_to_table(self):
        """Test adding column to a table."""
        content = [
            {
                "id": "items_section",
                "category": "section",
                "children": [
                    {
                        "id": "line_items",
                        "category": "multivalue",
                        "children": {"id": "row", "category": "tuple", "children": []},
                    }
                ],
            }
        ]
        fields_to_add = [
            {
                "id": "new_col",
                "label": "New Column",
                "parent_section": "items_section",
                "table_id": "line_items",
                "type": "string",
            }
        ]

        modified, added = _add_fields_to_content(content, fields_to_add)

        tuple_children = modified[0]["children"][0]["children"]["children"]
        assert len(tuple_children) == 1
        assert tuple_children[0]["id"] == "new_col"
        assert "new_col" in added

    def test_add_multiple_fields(self):
        """Test adding multiple fields."""
        content = [{"id": "header", "category": "section", "children": []}]
        fields_to_add = [
            {"id": "field1", "label": "Field 1", "parent_section": "header", "type": "string"},
            {"id": "field2", "label": "Field 2", "parent_section": "header", "type": "number"},
        ]

        modified, added = _add_fields_to_content(content, fields_to_add)

        assert len(modified[0]["children"]) == 2
        assert set(added) == {"field1", "field2"}


class TestExecuteOpusTool:
    """Test _execute_opus_tool function."""

    def test_unknown_tool_returns_error(self):
        """Test that unknown tool returns error message."""
        result = _execute_opus_tool("unknown_tool", {})
        assert "Unknown tool" in result

    def test_get_schema_tree_structure_calls_mcp(self):
        """Test get_schema_tree_structure tool calls MCP."""
        with patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool") as mock_mcp:
            mock_mcp.return_value = [{"id": "section1", "category": "section"}]
            result = _execute_opus_tool("get_schema_tree_structure", {"schema_id": 123})

            mock_mcp.assert_called_once_with("get_schema_tree_structure", {"schema_id": 123})
            parsed = json.loads(result)
            assert parsed[0]["id"] == "section1"

    def test_get_full_schema_caches_content(self):
        """Test get_full_schema caches content for later use."""
        _schema_content_cache.clear()

        with patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool") as mock_mcp:
            mock_mcp.return_value = {
                "id": 123,
                "content": [{"id": "section1", "category": "section", "children": []}],
            }
            _execute_opus_tool("get_full_schema", {"schema_id": 123})

            assert 123 in _schema_content_cache
            assert _schema_content_cache[123][0]["id"] == "section1"

        _schema_content_cache.clear()

    def test_apply_schema_changes_requires_cached_content(self):
        """Test apply_schema_changes requires get_full_schema to be called first."""
        _schema_content_cache.clear()

        result = _execute_opus_tool("apply_schema_changes", {"schema_id": 999})
        parsed = json.loads(result)

        assert "error" in parsed
        assert "get_full_schema first" in parsed["error"]

    def test_apply_schema_changes_uses_cached_content(self):
        """Test apply_schema_changes uses cached content."""
        _schema_content_cache[123] = [
            {
                "id": "section1",
                "category": "section",
                "children": [{"id": "field1", "category": "datapoint"}],
            }
        ]

        with patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool") as mock_mcp:
            mock_mcp.return_value = {"id": 123}
            result = _execute_opus_tool(
                "apply_schema_changes",
                {
                    "schema_id": 123,
                    "fields_to_keep": ["field1"],
                    "fields_to_add": [
                        {"id": "field2", "label": "Field 2", "parent_section": "section1", "type": "string"}
                    ],
                },
            )

            mock_mcp.assert_called_once()
            parsed = json.loads(result)
            assert "field2" in parsed["fields_added"]
            assert 123 not in _schema_content_cache

        _schema_content_cache.clear()


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
            return_value=("Added field new_field", 1000, 500),
        ) as mock_opus:
            result = patch_schema_with_subagent(schema_id="123", changes=json.dumps(changes))
            parsed = json.loads(result)

            mock_opus.assert_called_once_with("123", changes)
            assert parsed["schema_id"] == "123"
            assert parsed["changes_requested"] == 1
            assert "Added field" in parsed["analysis"]
            assert parsed["input_tokens"] == 1000
            assert parsed["output_tokens"] == 500

    def test_timing_is_measured(self):
        """Test that elapsed_ms is properly measured."""
        changes = [{"id": "f1", "parent_section": "s1", "type": "string"}]
        with patch(
            "rossum_agent.tools.subagents.schema_patching._call_opus_for_patching",
            return_value=("Done", 100, 50),
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
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        with (
            patch("rossum_agent.tools.subagents.schema_patching.create_bedrock_client") as mock_client,
            patch("rossum_agent.tools.subagents.schema_patching.report_progress", side_effect=capture_progress),
            patch("rossum_agent.tools.subagents.schema_patching.report_token_usage"),
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
        tool_use_block.name = "get_schema_tree_structure"
        tool_use_block.input = {"schema_id": 123}
        tool_use_block.id = "tool_1"

        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_use_block]
        first_response.usage.input_tokens = 100
        first_response.usage.output_tokens = 50

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Schema updated successfully"

        second_response = MagicMock()
        second_response.stop_reason = "end_of_turn"
        second_response.content = [text_block]
        second_response.usage.input_tokens = 200
        second_response.usage.output_tokens = 100

        with (
            patch("rossum_agent.tools.subagents.schema_patching.create_bedrock_client") as mock_client,
            patch("rossum_agent.tools.subagents.schema_patching.report_progress"),
            patch("rossum_agent.tools.subagents.schema_patching.report_token_usage"),
            patch("rossum_agent.tools.subagents.schema_patching._save_patching_context"),
            patch(
                "rossum_agent.tools.subagents.schema_patching._execute_opus_tool",
                return_value='[{"id": "section1"}]',
            ),
        ):
            mock_client.return_value.messages.create.side_effect = [first_response, second_response]

            changes = [{"id": "field1", "parent_section": "header", "type": "string"}]
            result, input_tokens, output_tokens = _call_opus_for_patching("123", changes)

            assert "Schema updated successfully" in result
            assert input_tokens == 300
            assert output_tokens == 150
            assert mock_client.return_value.messages.create.call_count == 2

    def test_max_iterations_is_5(self):
        """Test that max iterations is reduced to 5 for deterministic workflow."""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_of_turn"
        mock_response.content = [MagicMock(text="Done", type="text")]
        mock_response.content[0].text = "Done"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        with (
            patch("rossum_agent.tools.subagents.schema_patching.create_bedrock_client") as mock_client,
            patch("rossum_agent.tools.subagents.schema_patching.report_progress"),
            patch("rossum_agent.tools.subagents.schema_patching.report_token_usage"),
            patch("rossum_agent.tools.subagents.schema_patching._save_patching_context") as mock_save,
        ):
            mock_client.return_value.messages.create.return_value = mock_response

            changes = [{"id": "field1", "parent_section": "header", "type": "string"}]
            _call_opus_for_patching("123", changes)

            saved_context = mock_save.call_args[0]
            assert saved_context[1] == 5

    def test_bedrock_client_exception_returns_error(self):
        """Test that create_bedrock_client exception returns error message."""
        with (
            patch(
                "rossum_agent.tools.subagents.schema_patching.create_bedrock_client",
                side_effect=Exception("AWS error"),
            ),
            patch("rossum_agent.tools.subagents.schema_patching.logger") as mock_logger,
        ):
            result, input_tokens, output_tokens = _call_opus_for_patching("123", [{"id": "f1"}])

            assert "Error calling Opus sub-agent" in result
            assert "AWS error" in result
            mock_logger.exception.assert_called_once()
            assert input_tokens == 0
            assert output_tokens == 0


class TestSaveContext:
    """Test _save_patching_context function."""

    def test_saves_context_file_with_expected_structure(self, tmp_path):
        """Test that context file is saved with expected structure."""
        messages = [{"role": "user", "content": "test"}]

        with patch("rossum_agent.tools.subagents.schema_patching.get_output_dir", return_value=tmp_path):
            _save_patching_context(iteration=1, max_iterations=5, messages=messages)

        context_file = tmp_path / "patch_schema_context_iter_1.json"
        assert context_file.exists()

        context_data = json.loads(context_file.read_text())
        assert context_data["iteration"] == 1
        assert context_data["max_iterations"] == 5
        assert context_data["messages"] == messages
        assert context_data["max_tokens"] == 4096
        assert len(context_data["tools"]) == 3

    def test_logs_warning_when_save_fails(self):
        """Test that warning is logged when save fails."""
        with (
            patch("rossum_agent.tools.subagents.schema_patching.get_output_dir", side_effect=Exception("Test error")),
            patch("rossum_agent.tools.subagents.schema_patching.logger") as mock_logger,
        ):
            _save_patching_context(iteration=1, max_iterations=5, messages=[])

            mock_logger.warning.assert_called_once()
            assert "Failed to save patch_schema context" in mock_logger.warning.call_args[0][0]


class TestApplySchemaChanges:
    """Test _apply_schema_changes function."""

    def test_keeps_only_specified_fields(self):
        """Test that only specified fields are kept."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint"},
                    {"id": "field2", "category": "datapoint"},
                ],
            }
        ]

        with patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool") as mock_mcp:
            mock_mcp.return_value = {"id": 123}
            result = _apply_schema_changes(123, content, ["field1"], None)

            assert "field2" in result["fields_removed"]
            assert "field1" in result["fields_kept"]
            mock_mcp.assert_called_once()

    def test_adds_new_fields(self):
        """Test that new fields are added."""
        content = [{"id": "section1", "category": "section", "children": []}]

        with patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool") as mock_mcp:
            mock_mcp.return_value = {"id": 123}
            result = _apply_schema_changes(
                123,
                content,
                None,
                [{"id": "new_field", "label": "New", "parent_section": "section1", "type": "string"}],
            )

            assert "new_field" in result["fields_added"]

    def test_combines_keep_and_add(self):
        """Test that keep and add can be combined."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [{"id": "field1", "category": "datapoint"}],
            }
        ]

        with patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool") as mock_mcp:
            mock_mcp.return_value = {"id": 123}
            result = _apply_schema_changes(
                123,
                content,
                ["field1"],
                [{"id": "field2", "label": "Field 2", "parent_section": "section1", "type": "string"}],
            )

            assert "field1" in result["fields_kept"]
            assert "field2" in result["fields_added"]
            assert "field2" in result["fields_kept"]
