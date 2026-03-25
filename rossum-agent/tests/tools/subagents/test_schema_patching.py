"""Tests for rossum_agent.tools.subagents.schema_patching module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.tools.core import AgentContext, set_context
from rossum_agent.tools.subagents.base import SubAgentResult
from rossum_agent.tools.subagents.schema_patching import (
    _APPLY_SCHEMA_CHANGES_TOOL,
    _GET_FULL_SCHEMA_TOOL,
    _GET_SCHEMA_TREE_STRUCTURE_TOOL,
    _OPUS_TOOLS,
    _SCHEMA_PATCHING_SYSTEM_PROMPT,
    SchemaFieldType,
    _add_fields_to_content,
    _apply_schema_changes,
    _build_field_node,
    _call_opus_for_patching,
    _coerce_field_type,
    _collect_field_ids,
    _execute_opus_tool,
    _extract_schema_content,
    _filter_content,
    _find_or_create_section,
    _schema_content_cache,
    _section_label_from_id,
    _strip_invalid_rir_fields,
    _update_fields_in_content,
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
        assert "fields_to_update" in props


class TestExtractSchemaContent:
    """Test _extract_schema_content function."""

    def test_returns_empty_for_none(self):
        assert _extract_schema_content(None) == []

    def test_extracts_from_dict_with_result_wrapper(self):
        """Regression: FastMCP structured_content wraps data in {"result": {...}}."""
        schema_content = [{"id": "invoice_id", "category": "datapoint", "type": "string"}]
        mcp_result = {"result": {"id": 123, "name": "Test", "content": schema_content}}
        assert _extract_schema_content(mcp_result) == schema_content

    def test_extracts_from_dict_without_wrapper(self):
        schema_content = [{"id": "invoice_id", "category": "datapoint", "type": "string"}]
        mcp_result = {"id": 123, "name": "Test", "content": schema_content}
        assert _extract_schema_content(mcp_result) == schema_content

    def test_returns_empty_when_content_missing(self):
        mcp_result = {"result": {"id": 123, "name": "Test"}}
        assert _extract_schema_content(mcp_result) == []

    def test_extracts_from_object_with_result_attr(self):
        inner = MagicMock()
        inner.content = [{"id": "field_1", "category": "datapoint"}]
        outer = MagicMock(spec=["result"])
        outer.result = inner
        # Ensure outer doesn't have 'content' attr to avoid ambiguity
        del outer.content
        assert _extract_schema_content(outer) == [{"id": "field_1", "category": "datapoint"}]


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


class TestSectionLabelFromId:
    """Test _section_label_from_id function."""

    def test_basic_info_section(self):
        assert _section_label_from_id("basic_info_section") == "Basic Info"

    def test_amounts_section(self):
        assert _section_label_from_id("amounts_section") == "Amounts"

    def test_no_section_suffix(self):
        assert _section_label_from_id("line_items") == "Line Items"

    def test_single_word(self):
        assert _section_label_from_id("header") == "Header"


class TestFindOrCreateSection:
    """Test _find_or_create_section function."""

    def test_finds_existing_section(self):
        content = [{"id": "header", "category": "section", "children": [], "label": "Header"}]
        section = _find_or_create_section(content, "header")
        assert section is content[0]
        assert len(content) == 1

    def test_creates_missing_section(self):
        content = []
        section = _find_or_create_section(content, "basic_info_section")
        assert len(content) == 1
        assert section["id"] == "basic_info_section"
        assert section["category"] == "section"
        assert section["label"] == "Basic Info"
        assert section["children"] == []
        assert "icon" not in section

    def test_does_not_duplicate_existing(self):
        content = [{"id": "foo_section", "category": "section", "children": [], "label": "Foo"}]
        _find_or_create_section(content, "foo_section")
        _find_or_create_section(content, "foo_section")
        assert len(content) == 1

    def test_returns_none_for_empty_section_id(self):
        content = []
        assert _find_or_create_section(content, "") is None
        assert _find_or_create_section(content, None) is None
        assert len(content) == 0


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

    def test_formula_field(self):
        """Test that formula is included in built node."""
        spec = {"id": "calc_field", "label": "Calculated", "type": "string", "formula": "field.a + field.b"}
        node = _build_field_node(spec)

        assert node["formula"] == "field.a + field.b"

    def test_lookup_field_strips_rir_field_names(self):
        """Lookup fields must never have rir_field_names -- it causes engine restriction errors."""
        spec = {
            "id": "vendor_match",
            "label": "Vendor Match",
            "type": "enum",
            "ui_configuration": {"type": "lookup", "edit": "disabled"},
            "matching": {"type": "master_data_hub", "configuration": {}},
            "rir_field_names": ["vendor_match"],
        }
        node = _build_field_node(spec)

        assert "rir_field_names" not in node

    def test_lookup_field_with_matching(self):
        """Test that matching config is included in built node for lookup fields."""
        matching = {
            "type": "master_data_hub",
            "configuration": {
                "dataset": "Vendors",
                "queries": '[{"//": "Exact match", "aggregate": []}]',
                "placeholders": {"vat": {"__formula": "field.sender_vat_id"}},
            },
        }
        spec = {
            "id": "vendor_match",
            "label": "Vendor Match",
            "type": "enum",
            "ui_configuration": {"type": "lookup", "edit": "disabled"},
            "matching": matching,
        }
        node = _build_field_node(spec)

        assert node["matching"] == matching
        assert node["ui_configuration"] == {"type": "lookup", "edit": "disabled"}
        assert node["type"] == "enum"

    def test_lookup_field_gets_empty_options(self):
        """Regression: lookup fields are type=enum but have no static options.

        The API requires `options` to be present for enum fields, so it must default to [].
        """
        spec = {
            "id": "vendor_match",
            "label": "Vendor Match",
            "type": "enum",
            "ui_configuration": {"type": "lookup", "edit": "disabled"},
            "matching": {"type": "master_data_hub", "configuration": {}},
        }
        node = _build_field_node(spec)

        assert node["options"] == []

    def test_matching_not_included_when_absent(self):
        """Test that matching key is not set when not provided."""
        spec = {"id": "plain_field", "label": "Plain", "type": "string"}
        node = _build_field_node(spec)

        assert "matching" not in node


class TestCoerceTypeToString:
    """Test _coerce_field_type function."""

    def test_string_passes_through(self):
        assert _coerce_field_type("number") == SchemaFieldType.NUMBER

    def test_enum_passes_through(self):
        assert _coerce_field_type(SchemaFieldType.DATE) == SchemaFieldType.DATE

    def test_dict_with_type_key_extracts_value(self):
        assert _coerce_field_type({"type": "number"}) == SchemaFieldType.NUMBER

    def test_dict_without_type_key_falls_back_to_string(self):
        assert _coerce_field_type({"foo": "bar"}) == SchemaFieldType.STRING

    def test_none_falls_back_to_string(self):
        assert _coerce_field_type(None) == SchemaFieldType.STRING

    def test_invalid_string_falls_back_to_string(self):
        assert _coerce_field_type("bogus") == SchemaFieldType.STRING

    def test_returns_schema_field_type_instance(self):
        result = _coerce_field_type("number")
        assert isinstance(result, SchemaFieldType)

    def test_build_field_node_coerces_dict_type(self):
        spec = {"id": "amount", "label": "Amount", "type": {"type": "number"}}
        node = _build_field_node(spec)
        assert node["type"] == SchemaFieldType.NUMBER

    def test_update_fields_coerces_dict_type(self):
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [{"id": "field1", "category": "datapoint", "type": "string"}],
            }
        ]
        updates = [{"id": "field1", "type": {"type": "number"}}]
        modified, updated_ids = _update_fields_in_content(content, updates)
        assert "field1" in updated_ids
        assert modified[0]["children"][0]["type"] == SchemaFieldType.NUMBER


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

    def test_add_field_to_nonexistent_section_creates_it(self):
        """Test adding field to nonexistent section auto-creates the section."""
        content = [{"id": "header", "category": "section", "children": []}]
        fields_to_add = [
            {"id": "new_field", "label": "New Field", "parent_section": "footer_section", "type": "string"}
        ]

        modified, added = _add_fields_to_content(content, fields_to_add)

        assert len(modified) == 2
        assert modified[1]["id"] == "footer_section"
        assert modified[1]["category"] == "section"
        assert modified[1]["children"][0]["id"] == "new_field"
        assert "new_field" in added

    def test_add_field_to_empty_schema(self):
        """Test adding field to completely empty schema creates section and field."""
        content = []
        fields_to_add = [
            {
                "id": "we_love_rossum",
                "label": "We Love Rossum",
                "parent_section": "basic_info_section",
                "type": "string",
                "ui_configuration": {"type": "formula"},
                "formula": '"We love Rossum"',
            }
        ]

        modified, added = _add_fields_to_content(content, fields_to_add)

        assert len(modified) == 1
        section = modified[0]
        assert section["id"] == "basic_info_section"
        assert section["category"] == "section"
        assert section["label"] == "Basic Info"
        assert len(section["children"]) == 1
        assert section["children"][0]["id"] == "we_love_rossum"
        assert section["children"][0]["formula"] == '"We love Rossum"'
        assert "we_love_rossum" in added

    def test_add_multiple_fields_to_empty_schema_same_section(self):
        """Test adding multiple fields to the same auto-created section."""
        content = []
        fields_to_add = [
            {"id": "field1", "label": "Field 1", "parent_section": "header_section", "type": "string"},
            {"id": "field2", "label": "Field 2", "parent_section": "header_section", "type": "number"},
        ]

        modified, added = _add_fields_to_content(content, fields_to_add)

        assert len(modified) == 1
        assert len(modified[0]["children"]) == 2
        assert set(added) == {"field1", "field2"}

    def test_add_field_with_no_parent_section_is_skipped(self):
        """Test that fields with empty/None parent_section are skipped."""
        content = [{"id": "header", "category": "section", "children": []}]
        fields_to_add = [
            {"id": "orphan", "label": "Orphan", "parent_section": "", "type": "string"},
            {"id": "valid", "label": "Valid", "parent_section": "header", "type": "string"},
        ]

        modified, added = _add_fields_to_content(content, fields_to_add)

        assert len(modified) == 1
        assert added == ["valid"]
        assert len(modified[0]["children"]) == 1

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

    def test_add_lookup_field_preserves_matching(self):
        """Test that adding a lookup field preserves the matching config."""
        content = [{"id": "vendor_section", "category": "section", "children": []}]
        matching = {
            "type": "master_data_hub",
            "configuration": {
                "dataset": "Vendors",
                "queries": '[{"//": "Exact match", "aggregate": []}]',
                "placeholders": {"vat": {"__formula": "field.sender_vat_id"}},
            },
        }
        fields_to_add = [
            {
                "id": "vendor_match",
                "label": "Vendor Match",
                "parent_section": "vendor_section",
                "type": "enum",
                "ui_configuration": {"type": "lookup", "edit": "disabled"},
                "matching": matching,
            }
        ]

        modified, added = _add_fields_to_content(content, fields_to_add)

        assert "vendor_match" in added
        field = modified[0]["children"][0]
        assert field["matching"] == matching
        assert field["ui_configuration"] == {"type": "lookup", "edit": "disabled"}
        assert field["type"] == "enum"

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


class TestAddFieldsPositioning:
    """Test _add_fields_to_content with after_field and before_field positioning."""

    def test_add_field_after_existing_field(self):
        """Test adding field after a specific field in a section."""
        content = [
            {
                "id": "header",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint", "type": "string", "label": "F1"},
                    {"id": "field3", "category": "datapoint", "type": "string", "label": "F3"},
                ],
            }
        ]
        fields_to_add = [
            {
                "id": "field2",
                "label": "Field 2",
                "parent_section": "header",
                "type": "string",
                "after_field": "field1",
            }
        ]

        modified, added = _add_fields_to_content(content, fields_to_add)

        assert [c["id"] for c in modified[0]["children"]] == ["field1", "field2", "field3"]
        assert "field2" in added

    def test_add_field_before_existing_field(self):
        """Test adding field before a specific field in a section."""
        content = [
            {
                "id": "header",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint", "type": "string", "label": "F1"},
                    {"id": "field3", "category": "datapoint", "type": "string", "label": "F3"},
                ],
            }
        ]
        fields_to_add = [
            {
                "id": "field2",
                "label": "Field 2",
                "parent_section": "header",
                "type": "string",
                "before_field": "field3",
            }
        ]

        modified, added = _add_fields_to_content(content, fields_to_add)

        assert [c["id"] for c in modified[0]["children"]] == ["field1", "field2", "field3"]
        assert "field2" in added

    def test_add_field_after_nonexistent_field_appends(self):
        """Test that after_field with nonexistent ID falls back to append."""
        content = [
            {
                "id": "header",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint", "type": "string", "label": "F1"},
                ],
            }
        ]
        fields_to_add = [
            {
                "id": "field2",
                "label": "Field 2",
                "parent_section": "header",
                "type": "string",
                "after_field": "nonexistent",
            }
        ]

        modified, added = _add_fields_to_content(content, fields_to_add)

        assert [c["id"] for c in modified[0]["children"]] == ["field1", "field2"]
        assert "field2" in added

    def test_add_field_after_in_table(self):
        """Test adding a table column after a specific column."""
        content = [
            {
                "id": "items_section",
                "category": "section",
                "children": [
                    {
                        "id": "line_items",
                        "category": "multivalue",
                        "children": {
                            "id": "row",
                            "category": "tuple",
                            "children": [
                                {"id": "col1", "category": "datapoint", "type": "string", "label": "C1"},
                                {"id": "col3", "category": "datapoint", "type": "string", "label": "C3"},
                            ],
                        },
                    }
                ],
            }
        ]
        fields_to_add = [
            {
                "id": "col2",
                "label": "Column 2",
                "parent_section": "items_section",
                "table_id": "line_items",
                "type": "string",
                "after_field": "col1",
            }
        ]

        modified, added = _add_fields_to_content(content, fields_to_add)

        tuple_children = modified[0]["children"][0]["children"]["children"]
        assert [c["id"] for c in tuple_children] == ["col1", "col2", "col3"]
        assert "col2" in added

    def test_add_field_before_in_table(self):
        """Test adding a table column before a specific column."""
        content = [
            {
                "id": "items_section",
                "category": "section",
                "children": [
                    {
                        "id": "line_items",
                        "category": "multivalue",
                        "children": {
                            "id": "row",
                            "category": "tuple",
                            "children": [
                                {"id": "col1", "category": "datapoint", "type": "string", "label": "C1"},
                                {"id": "col3", "category": "datapoint", "type": "string", "label": "C3"},
                            ],
                        },
                    }
                ],
            }
        ]
        fields_to_add = [
            {
                "id": "col2",
                "label": "Column 2",
                "parent_section": "items_section",
                "table_id": "line_items",
                "type": "string",
                "before_field": "col3",
            }
        ]

        modified, added = _add_fields_to_content(content, fields_to_add)

        tuple_children = modified[0]["children"][0]["children"]["children"]
        assert [c["id"] for c in tuple_children] == ["col1", "col2", "col3"]
        assert "col2" in added


class TestUpdateFieldsInContent:
    """Test _update_fields_in_content function."""

    def test_update_formula_on_existing_field(self):
        """Test updating formula text on an existing field."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "qr_code_iban",
                        "category": "datapoint",
                        "type": "string",
                        "formula": 'field.qr_code.split("\\n")[3]',
                    },
                ],
            }
        ]
        updates = [{"id": "qr_code_iban", "formula": 'lines[3] if len(lines) > 3 else ""'}]
        modified, updated_ids = _update_fields_in_content(content, updates)

        assert "qr_code_iban" in updated_ids
        assert modified[0]["children"][0]["formula"] == 'lines[3] if len(lines) > 3 else ""'

    def test_update_multiple_fields(self):
        """Test updating multiple fields at once."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint", "formula": "old1"},
                    {"id": "field2", "category": "datapoint", "formula": "old2"},
                ],
            }
        ]
        updates = [
            {"id": "field1", "formula": "new1"},
            {"id": "field2", "formula": "new2"},
        ]
        modified, updated_ids = _update_fields_in_content(content, updates)

        assert set(updated_ids) == {"field1", "field2"}
        assert modified[0]["children"][0]["formula"] == "new1"
        assert modified[0]["children"][1]["formula"] == "new2"

    def test_update_label(self):
        """Test updating field label."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [{"id": "field1", "category": "datapoint", "label": "Old Label"}],
            }
        ]
        updates = [{"id": "field1", "label": "New Label"}]
        modified, updated_ids = _update_fields_in_content(content, updates)

        assert "field1" in updated_ids
        assert modified[0]["children"][0]["label"] == "New Label"

    def test_update_field_in_table(self):
        """Test updating a field inside a multivalue/tuple structure."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "table1",
                        "category": "multivalue",
                        "children": {
                            "id": "row1",
                            "category": "tuple",
                            "children": [
                                {"id": "col1", "category": "datapoint", "formula": "old"},
                            ],
                        },
                    },
                ],
            }
        ]
        updates = [{"id": "col1", "formula": "new"}]
        modified, updated_ids = _update_fields_in_content(content, updates)

        assert "col1" in updated_ids
        tuple_children = modified[0]["children"][0]["children"]["children"]
        assert tuple_children[0]["formula"] == "new"

    def test_update_nonexistent_field_returns_empty(self):
        """Test that updating a nonexistent field doesn't crash."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [{"id": "field1", "category": "datapoint"}],
            }
        ]
        updates = [{"id": "nonexistent", "formula": "code"}]
        modified, updated_ids = _update_fields_in_content(content, updates)

        assert updated_ids == []
        assert modified[0]["children"][0]["id"] == "field1"

    def test_does_not_modify_original(self):
        """Test that original content is not modified."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [{"id": "field1", "category": "datapoint", "formula": "old"}],
            }
        ]
        updates = [{"id": "field1", "formula": "new"}]
        _update_fields_in_content(content, updates)

        assert content[0]["children"][0]["formula"] == "old"


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
                "result": {
                    "id": 123,
                    "content": [{"id": "section1", "category": "section", "children": []}],
                }
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

        with patch("rossum_agent.tools.subagents.schema_patching._update_schema_via_api"):
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

            parsed = json.loads(result)
            assert "field2" in parsed["fields_added"]
            assert 123 not in _schema_content_cache

        _schema_content_cache.clear()

    def test_apply_schema_changes_passes_fields_to_update(self):
        """Test apply_schema_changes forwards fields_to_update to _apply_schema_changes."""
        _schema_content_cache[123] = [
            {
                "id": "section1",
                "category": "section",
                "children": [{"id": "field1", "category": "datapoint", "formula": "old"}],
            }
        ]

        with patch("rossum_agent.tools.subagents.schema_patching._update_schema_via_api") as mock_api:
            result = _execute_opus_tool(
                "apply_schema_changes",
                {
                    "schema_id": 123,
                    "fields_to_update": [{"id": "field1", "formula": "new"}],
                },
            )

            parsed = json.loads(result)
            assert "field1" in parsed["fields_updated"]
            updated_content = mock_api.call_args[0][1]
            assert updated_content[0]["children"][0]["formula"] == "new"
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
        mock_result = SubAgentResult(
            analysis="Added field new_field",
            input_tokens=1000,
            output_tokens=500,
            iterations_used=2,
        )
        with patch(
            "rossum_agent.tools.subagents.schema_patching._call_opus_for_patching",
            return_value=mock_result,
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
        mock_result = SubAgentResult(
            analysis="Done",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )
        with patch(
            "rossum_agent.tools.subagents.schema_patching._call_opus_for_patching",
            return_value=mock_result,
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

        mock_response = MagicMock()
        mock_response.stop_reason = "end_of_turn"
        mock_response.content = [MagicMock(text="Patching complete", type="text")]
        mock_response.content[0].text = "Patching complete"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        set_context(
            AgentContext(
                progress_callback=lambda p: progress_calls.append(p),
                token_callback=MagicMock(),
            )
        )
        try:
            with (
                patch("rossum_agent.tools.subagents.base.create_bedrock_client") as mock_client,
                patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool", return_value=None),
            ):
                mock_client.return_value.messages.create.return_value = mock_response

                changes = [{"id": "field1", "parent_section": "header", "type": "string"}]
                _call_opus_for_patching("123", changes)

                assert len(progress_calls) >= 1
                assert progress_calls[0].tool_name == "patch_schema"
        finally:
            set_context(AgentContext())

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

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with (
                patch("rossum_agent.tools.subagents.base.create_bedrock_client") as mock_client,
                patch(
                    "rossum_agent.tools.subagents.schema_patching._execute_opus_tool",
                    return_value='[{"id": "section1"}]',
                ),
                patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool", return_value=None),
            ):
                mock_client.return_value.messages.create.side_effect = [first_response, second_response]

                changes = [{"id": "field1", "parent_section": "header", "type": "string"}]
                result = _call_opus_for_patching("123", changes)

                assert "Schema updated successfully" in result.analysis
                assert result.input_tokens == 300
                assert result.output_tokens == 150
                assert mock_client.return_value.messages.create.call_count == 2
        finally:
            set_context(AgentContext())

    def test_max_iterations_is_3(self):
        """Test that max iterations is 3 for deterministic workflow."""
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "get_schema_tree_structure"
        mock_tool_block.input = {"schema_id": 123}
        mock_tool_block.id = "tool_1"

        mock_response = MagicMock()
        mock_response.stop_reason = "tool_use"
        mock_response.content = [mock_tool_block]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with (
                patch("rossum_agent.tools.subagents.base.create_bedrock_client") as mock_client,
                patch(
                    "rossum_agent.tools.subagents.schema_patching._execute_opus_tool",
                    return_value='[{"id": "section1"}]',
                ),
                patch("rossum_agent.tools.subagents.base.logger"),
                patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool", return_value=None),
            ):
                mock_client.return_value.messages.create.return_value = mock_response

                changes = [{"id": "field1", "parent_section": "header", "type": "string"}]
                result = _call_opus_for_patching("123", changes)

                assert result.iterations_used == 3
                assert mock_client.return_value.messages.create.call_count == 3
        finally:
            set_context(AgentContext())

    def test_bedrock_client_exception_returns_error(self):
        """Test that create_bedrock_client exception returns error message."""
        with (
            patch(
                "rossum_agent.tools.subagents.base.create_bedrock_client",
                side_effect=Exception("AWS error"),
            ),
            patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool", return_value=None),
        ):
            result = _call_opus_for_patching("123", [{"id": "f1"}])

            assert "Error calling Opus sub-agent" in result.analysis
            assert "AWS error" in result.analysis
            assert result.input_tokens == 0
            assert result.output_tokens == 0

    def test_update_only_changes_uses_keep_all_intro(self):
        """Test that update-only changes produce 'keep all other fields' intro."""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_of_turn"
        mock_response.content = [MagicMock(text="Done", type="text")]
        mock_response.content[0].text = "Done"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with (
                patch("rossum_agent.tools.subagents.base.create_bedrock_client") as mock_client,
                patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool", return_value=None),
            ):
                mock_client.return_value.messages.create.return_value = mock_response

                changes = [{"action": "update", "id": "field1", "formula": "new_code"}]
                _call_opus_for_patching("123", changes)

                call_args = mock_client.return_value.messages.create.call_args
                user_content = call_args[1]["messages"][0]["content"]
                user_text = user_content[0]["text"] if isinstance(user_content, list) else user_content
                assert "keep all other fields unchanged" in user_text
                assert "EXACTLY" not in user_text
        finally:
            set_context(AgentContext())

    def test_mixed_actions_uses_exactly_intro(self):
        """Test that mixed add+update changes use 'EXACTLY' intro."""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_of_turn"
        mock_response.content = [MagicMock(text="Done", type="text")]
        mock_response.content[0].text = "Done"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with (
                patch("rossum_agent.tools.subagents.base.create_bedrock_client") as mock_client,
                patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool", return_value=None),
            ):
                mock_client.return_value.messages.create.return_value = mock_response

                changes = [
                    {"action": "add", "id": "new_f", "parent_section": "s1", "type": "string"},
                    {"action": "update", "id": "old_f", "formula": "code"},
                ]
                _call_opus_for_patching("123", changes)

                call_args = mock_client.return_value.messages.create.call_args
                user_content = call_args[1]["messages"][0]["content"]
                user_text = user_content[0]["text"] if isinstance(user_content, list) else user_content
                assert "EXACTLY" in user_text
        finally:
            set_context(AgentContext())

    def test_lookup_matching_included_in_user_prompt(self):
        """Test that lookup field matching config is included in the user prompt."""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_of_turn"
        mock_response.content = [MagicMock(text="Done", type="text")]
        mock_response.content[0].text = "Done"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with (
                patch("rossum_agent.tools.subagents.base.create_bedrock_client") as mock_client,
                patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool", return_value=None),
            ):
                mock_client.return_value.messages.create.return_value = mock_response

                matching = {
                    "type": "master_data_hub",
                    "configuration": {"dataset": "Vendors", "queries": "[]", "placeholders": {}},
                }
                changes = [
                    {
                        "action": "add",
                        "id": "vendor_match",
                        "type": "enum",
                        "parent_section": "vendor_section",
                        "ui_configuration": {"type": "lookup", "edit": "disabled"},
                        "matching": matching,
                    }
                ]
                _call_opus_for_patching("123", changes)

                call_args = mock_client.return_value.messages.create.call_args
                user_content = call_args[1]["messages"][0]["content"]
                user_text = user_content[0]["text"] if isinstance(user_content, list) else user_content
                assert "[LOOKUP]" in user_text
                assert "Lookup Field Specs" in user_text
                assert "master_data_hub" in user_text
                assert "matching" in user_text
        finally:
            set_context(AgentContext())

    def test_no_lookup_section_without_matching(self):
        """Test that no lookup section is added for non-lookup fields."""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_of_turn"
        mock_response.content = [MagicMock(text="Done", type="text")]
        mock_response.content[0].text = "Done"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with (
                patch("rossum_agent.tools.subagents.base.create_bedrock_client") as mock_client,
                patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool", return_value=None),
            ):
                mock_client.return_value.messages.create.return_value = mock_response

                changes = [{"action": "add", "id": "plain", "type": "string", "parent_section": "s1"}]
                _call_opus_for_patching("123", changes)

                call_args = mock_client.return_value.messages.create.call_args
                user_content = call_args[1]["messages"][0]["content"]
                user_text = user_content[0]["text"] if isinstance(user_content, list) else user_content
                assert "Lookup Field Specs" not in user_text
        finally:
            set_context(AgentContext())

    def test_formula_included_in_changes_text(self):
        """Test that formula code appears in the user prompt sent to the sub-agent."""
        mock_response = MagicMock()
        mock_response.stop_reason = "end_of_turn"
        mock_response.content = [MagicMock(text="Done", type="text")]
        mock_response.content[0].text = "Done"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with (
                patch("rossum_agent.tools.subagents.base.create_bedrock_client") as mock_client,
                patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool", return_value=None),
            ):
                mock_client.return_value.messages.create.return_value = mock_response

                changes = [{"action": "update", "id": "calc", "formula": "field.a + field.b"}]
                _call_opus_for_patching("123", changes)

                call_args = mock_client.return_value.messages.create.call_args
                user_content = call_args[1]["messages"][0]["content"]
                user_text = user_content[0]["text"] if isinstance(user_content, list) else user_content
                assert "formula='field.a + field.b'" in user_text
        finally:
            set_context(AgentContext())

    def test_cache_cleaned_up_on_sub_agent_failure(self):
        """Regression: cache must be cleared even if sub-agent run() raises."""
        _schema_content_cache[123] = [{"id": "section1", "category": "section", "children": []}]

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with (
                patch("rossum_agent.tools.subagents.schema_patching.call_mcp_tool", return_value=None),
                patch(
                    "rossum_agent.tools.subagents.schema_patching.SchemaPatchingSubAgent.run",
                    side_effect=RuntimeError("sub-agent crashed"),
                ),
                pytest.raises(RuntimeError, match="sub-agent crashed"),
            ):
                _call_opus_for_patching("123", [{"id": "f1", "parent_section": "s1", "type": "string"}])

            assert 123 not in _schema_content_cache
        finally:
            _schema_content_cache.clear()
            set_context(AgentContext())


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

        with patch("rossum_agent.tools.subagents.schema_patching._update_schema_via_api") as mock_api:
            result = _apply_schema_changes(123, content, ["field1"], None)

            assert "field2" in result["fields_removed"]
            assert "field1" in result["fields_kept"]
            mock_api.assert_called_once()

    def test_adds_new_fields(self):
        """Test that new fields are added."""
        content = [{"id": "section1", "category": "section", "children": []}]

        with patch("rossum_agent.tools.subagents.schema_patching._update_schema_via_api"):
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

        with patch("rossum_agent.tools.subagents.schema_patching._update_schema_via_api"):
            result = _apply_schema_changes(
                123,
                content,
                ["field1"],
                [{"id": "field2", "label": "Field 2", "parent_section": "section1", "type": "string"}],
            )

            assert "field1" in result["fields_kept"]
            assert "field2" in result["fields_added"]
            assert "field2" in result["fields_kept"]

    def test_updates_existing_fields(self):
        """Test that existing fields are updated."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint", "formula": "old_code"},
                ],
            }
        ]

        with patch("rossum_agent.tools.subagents.schema_patching._update_schema_via_api") as mock_api:
            result = _apply_schema_changes(
                123,
                content,
                None,
                None,
                [{"id": "field1", "formula": "new_code"}],
            )

            assert "field1" in result["fields_updated"]
            updated_content = mock_api.call_args[0][1]
            assert updated_content[0]["children"][0]["formula"] == "new_code"


class TestStripInvalidRirFields:
    """Test _strip_invalid_rir_fields helper."""

    def test_strips_bad_rir_field_names(self):
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint", "rir_field_names": ["month_in_spanish"]},
                    {"id": "field2", "category": "datapoint", "rir_field_names": ["date_issue"]},
                ],
            }
        ]
        fixed = _strip_invalid_rir_fields(content, {"month_in_spanish"})
        assert fixed == ["field1"]
        assert "rir_field_names" not in content[0]["children"][0]
        assert content[0]["children"][1]["rir_field_names"] == ["date_issue"]

    def test_keeps_valid_entries_in_mixed_list(self):
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "f1", "category": "datapoint", "rir_field_names": ["good_name", "bad_name"]},
                ],
            }
        ]
        _strip_invalid_rir_fields(content, {"bad_name"})
        assert content[0]["children"][0]["rir_field_names"] == ["good_name"]

    def test_walks_nested_children(self):
        """Handles multivalue/tuple nesting."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "mv1",
                        "category": "multivalue",
                        "children": {
                            "id": "tuple1",
                            "category": "tuple",
                            "children": [
                                {"id": "col1", "category": "datapoint", "rir_field_names": ["bad_col"]},
                            ],
                        },
                    },
                ],
            }
        ]
        fixed = _strip_invalid_rir_fields(content, {"bad_col"})
        assert "col1" in fixed

    def test_noop_when_no_bad_names(self):
        content = [
            {
                "id": "s1",
                "category": "section",
                "children": [{"id": "f1", "rir_field_names": ["ok"]}],
            }
        ]
        fixed = _strip_invalid_rir_fields(content, {"other"})
        assert fixed == []
        assert content[0]["children"][0]["rir_field_names"] == ["ok"]


class TestApplySchemaChangesEngineRestrictionRecovery:
    """Test auto-recovery when API rejects schema due to engine field restrictions."""

    def test_retries_after_stripping_bad_rir_fields(self):
        """When API rejects with engine restriction, strip rir_field_names and retry."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "existing", "category": "datapoint"},
                ],
            }
        ]
        engine_error = Exception(
            "[PATCH] https://example.com/api/v1/schemas/123 "
            '- HTTP 400 - {"content":[{"children":{"1":{"id":["Engine (id: 44371) restriction: '
            "extracted field 'month_in_spanish' is not present among names of engine fields\"]}}}]}"
        )
        call_count = 0

        def mock_update(schema_id, modified_content):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise engine_error

        with patch("rossum_agent.tools.subagents.schema_patching._update_schema_via_api", side_effect=mock_update):
            result = _apply_schema_changes(
                123,
                content,
                None,
                [
                    {
                        "id": "month_in_spanish",
                        "label": "Month",
                        "parent_section": "section1",
                        "type": "string",
                        "rir_field_names": ["month_in_spanish"],
                    }
                ],
            )

        assert result["update_result"] == "success"
        assert call_count == 2

    def test_raises_non_engine_restriction_errors(self):
        """Non-engine-restriction errors propagate normally."""
        content = [{"id": "s1", "category": "section", "children": []}]

        with patch("rossum_agent.tools.subagents.schema_patching._update_schema_via_api") as mock_api:
            mock_api.side_effect = Exception("Some other API error")
            raised = False
            try:
                _apply_schema_changes(123, content, None, None)
            except Exception as e:
                raised = True
                assert "Some other API error" in str(e)
            assert raised
