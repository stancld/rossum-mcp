"""Tests for schema patching functions."""

from __future__ import annotations

import pytest
from rossum_mcp.tools.update.schemas.patching import (
    _apply_add_operation,
    _apply_remove_operation,
    _apply_update_operation,
    _find_node_anywhere,
    _find_node_in_children,
    _find_parent_children_list,
    _get_section_children_as_list,
    apply_schema_patch,
)


@pytest.mark.unit
class TestApplySchemaPatch:
    """Tests for apply_schema_patch helper function."""

    def test_add_datapoint_to_section(self) -> None:
        """Test adding a datapoint to a section."""
        content = [{"id": "section1", "category": "section", "children": []}]

        result = apply_schema_patch(
            content=content,
            operation="add",
            node_id="new_field",
            node_data={"label": "New Field", "type": "string", "category": "datapoint"},
            parent_id="section1",
        )

        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["id"] == "new_field"
        assert result[0]["children"][0]["label"] == "New Field"

    def test_add_with_position(self) -> None:
        """Test adding a datapoint at a specific position."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint"},
                    {"id": "field3", "category": "datapoint"},
                ],
            }
        ]

        result = apply_schema_patch(
            content=content,
            operation="add",
            node_id="field2",
            node_data={"label": "Field 2", "category": "datapoint"},
            parent_id="section1",
            position=1,
        )

        assert result[0]["children"][1]["id"] == "field2"

    def test_add_with_after_field(self) -> None:
        """Test adding a datapoint after a specific field by ID."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint"},
                    {"id": "field3", "category": "datapoint"},
                ],
            }
        ]

        result = apply_schema_patch(
            content=content,
            operation="add",
            node_id="field2",
            node_data={"label": "Field 2", "category": "datapoint"},
            parent_id="section1",
            after_field="field1",
        )

        assert len(result[0]["children"]) == 3
        assert result[0]["children"][0]["id"] == "field1"
        assert result[0]["children"][1]["id"] == "field2"
        assert result[0]["children"][2]["id"] == "field3"

    def test_add_with_after_field_last(self) -> None:
        """Test adding after the last field appends correctly."""
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

        result = apply_schema_patch(
            content=content,
            operation="add",
            node_id="field3",
            node_data={"label": "Field 3", "category": "datapoint"},
            parent_id="section1",
            after_field="field2",
        )

        assert len(result[0]["children"]) == 3
        assert result[0]["children"][2]["id"] == "field3"

    def test_add_with_after_field_not_found_appends(self) -> None:
        """Test that after_field with nonexistent ID falls back to append."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint"},
                ],
            }
        ]

        result = apply_schema_patch(
            content=content,
            operation="add",
            node_id="field2",
            node_data={"label": "Field 2", "category": "datapoint"},
            parent_id="section1",
            after_field="nonexistent",
        )

        assert len(result[0]["children"]) == 2
        assert result[0]["children"][1]["id"] == "field2"

    def test_add_with_before_field(self) -> None:
        """Test adding a datapoint before a specific field by ID."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint"},
                    {"id": "field3", "category": "datapoint"},
                ],
            }
        ]

        result = apply_schema_patch(
            content=content,
            operation="add",
            node_id="field2",
            node_data={"label": "Field 2", "category": "datapoint"},
            parent_id="section1",
            before_field="field3",
        )

        assert len(result[0]["children"]) == 3
        assert result[0]["children"][0]["id"] == "field1"
        assert result[0]["children"][1]["id"] == "field2"
        assert result[0]["children"][2]["id"] == "field3"

    def test_add_with_before_field_first(self) -> None:
        """Test adding before the first field inserts at position 0."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field2", "category": "datapoint"},
                ],
            }
        ]

        result = apply_schema_patch(
            content=content,
            operation="add",
            node_id="field1",
            node_data={"label": "Field 1", "category": "datapoint"},
            parent_id="section1",
            before_field="field2",
        )

        assert len(result[0]["children"]) == 2
        assert result[0]["children"][0]["id"] == "field1"
        assert result[0]["children"][1]["id"] == "field2"

    def test_add_with_before_field_not_found_appends(self) -> None:
        """Test that before_field with nonexistent ID falls back to append."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint"},
                ],
            }
        ]

        result = apply_schema_patch(
            content=content,
            operation="add",
            node_id="field2",
            node_data={"label": "Field 2", "category": "datapoint"},
            parent_id="section1",
            before_field="nonexistent",
        )

        assert len(result[0]["children"]) == 2
        assert result[0]["children"][1]["id"] == "field2"

    def test_add_with_conflicting_position_params_raises(self) -> None:
        """Test that providing both position and after_field raises ValueError."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint"},
                ],
            }
        ]

        with pytest.raises(ValueError, match="at most one"):
            apply_schema_patch(
                content=content,
                operation="add",
                node_id="field0",
                node_data={"label": "Field 0", "category": "datapoint"},
                parent_id="section1",
                position=0,
                after_field="field1",
            )

    def test_update_existing_node(self) -> None:
        """Test updating an existing node's properties."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [{"id": "field1", "label": "Old Label", "category": "datapoint"}],
            }
        ]

        result = apply_schema_patch(
            content=content,
            operation="update",
            node_id="field1",
            node_data={"label": "New Label", "score_threshold": 0.8},
        )

        assert result[0]["children"][0]["label"] == "New Label"
        assert result[0]["children"][0]["score_threshold"] == 0.8

    def test_remove_node(self) -> None:
        """Test removing a node from the schema."""
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

        result = apply_schema_patch(
            content=content,
            operation="remove",
            node_id="field1",
        )

        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["id"] == "field2"

    def test_add_missing_parent_raises_error(self) -> None:
        """Test that adding to a non-existent parent raises error."""
        content = [{"id": "section1", "category": "section", "children": []}]

        with pytest.raises(ValueError, match="not found"):
            apply_schema_patch(
                content=content,
                operation="add",
                node_id="new_field",
                node_data={"label": "New"},
                parent_id="nonexistent_section",
            )

    def test_update_nonexistent_node_raises_error(self) -> None:
        """Test that updating a non-existent node raises error."""
        content = [{"id": "section1", "category": "section", "children": []}]

        with pytest.raises(ValueError, match="not found"):
            apply_schema_patch(
                content=content,
                operation="update",
                node_id="nonexistent",
                node_data={"label": "Updated"},
            )

    def test_remove_nonexistent_node_raises_error(self) -> None:
        """Test that removing a non-existent node raises error."""
        content = [{"id": "section1", "category": "section", "children": []}]

        with pytest.raises(ValueError, match="not found"):
            apply_schema_patch(
                content=content,
                operation="remove",
                node_id="nonexistent",
            )

    def test_original_content_not_modified(self) -> None:
        """Test that the original content is not modified."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [{"id": "field1", "label": "Original", "category": "datapoint"}],
            }
        ]

        apply_schema_patch(
            content=content,
            operation="update",
            node_id="field1",
            node_data={"label": "Modified"},
        )

        assert content[0]["children"][0]["label"] == "Original"

    def test_add_node_at_position(self) -> None:
        """Test adding a node at a specific position."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "field1", "category": "datapoint"},
                    {"id": "field3", "category": "datapoint"},
                ],
            }
        ]

        result = apply_schema_patch(
            content=content,
            operation="add",
            node_id="field2",
            node_data={"label": "Field 2", "category": "datapoint"},
            parent_id="section1",
            position=1,
        )

        assert len(result[0]["children"]) == 3
        assert result[0]["children"][0]["id"] == "field1"
        assert result[0]["children"][1]["id"] == "field2"
        assert result[0]["children"][2]["id"] == "field3"

    def test_update_section_directly(self) -> None:
        """Test updating a section node directly (not a child)."""
        content = [
            {
                "id": "section1",
                "label": "Original Section",
                "category": "section",
                "children": [],
            }
        ]

        result = apply_schema_patch(
            content=content,
            operation="update",
            node_id="section1",
            node_data={"label": "Updated Section"},
        )

        assert result[0]["id"] == "section1"
        assert result[0]["label"] == "Updated Section"

    def test_remove_section_raises_error(self) -> None:
        """Test that attempting to remove a section raises ValueError."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [{"id": "field1", "category": "datapoint"}],
            }
        ]

        with pytest.raises(ValueError, match="Cannot remove a section"):
            apply_schema_patch(
                content=content,
                operation="remove",
                node_id="section1",
            )

    def test_remove_tuple_from_multivalue_raises_error(self) -> None:
        """Test that attempting to remove a tuple from multivalue raises ValueError."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "line_items",
                        "category": "multivalue",
                        "children": {
                            "id": "line_item_tuple",
                            "category": "tuple",
                            "children": [{"id": "description", "category": "datapoint"}],
                        },
                    }
                ],
            }
        ]

        with pytest.raises(ValueError, match=r"Cannot remove .* from multivalue"):
            apply_schema_patch(
                content=content,
                operation="remove",
                node_id="line_item_tuple",
            )

    def test_find_node_in_multivalue_dict_children(self) -> None:
        """Test operations on nodes inside multivalue with dict children."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "line_items",
                        "category": "multivalue",
                        "children": {
                            "id": "line_item_tuple",
                            "category": "tuple",
                            "children": [
                                {"id": "description", "label": "Description", "category": "datapoint"},
                            ],
                        },
                    }
                ],
            }
        ]

        result = apply_schema_patch(
            content=content,
            operation="update",
            node_id="description",
            node_data={"label": "Updated Description"},
        )

        tuple_children = result[0]["children"][0]["children"]["children"]
        assert tuple_children[0]["label"] == "Updated Description"

    def test_find_parent_with_dict_children(self) -> None:
        """Test _find_parent_children_list when parent node has dict children (multivalue case)."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "line_items",
                        "category": "multivalue",
                        "children": {
                            "id": "line_item_tuple",
                            "category": "tuple",
                            "children": [],
                        },
                    }
                ],
            }
        ]

        result = apply_schema_patch(
            content=content,
            operation="add",
            node_id="new_column",
            node_data={"label": "New Column", "category": "datapoint"},
            parent_id="line_item_tuple",
        )

        tuple_children = result[0]["children"][0]["children"]["children"]
        assert len(tuple_children) == 1
        assert tuple_children[0]["id"] == "new_column"

    def test_unknown_operation_passthrough(self) -> None:
        """Test that unknown operation returns content unchanged."""
        content = [{"id": "section1", "category": "section", "children": []}]

        result = apply_schema_patch(
            content=content,
            operation="unknown",  # type: ignore[arg-type]
            node_id="any_node",
        )

        assert result == content

    def test_add_to_parent_without_children(self) -> None:
        """Test adding to a parent node that doesn't have children yet."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {"id": "empty_tuple", "category": "tuple"},
                ],
            }
        ]

        result = apply_schema_patch(
            content=content,
            operation="add",
            node_id="new_field",
            node_data={"label": "New Field", "category": "datapoint"},
            parent_id="empty_tuple",
        )

        assert len(result[0]["children"][0]["children"]) == 1
        assert result[0]["children"][0]["children"][0]["id"] == "new_field"


@pytest.mark.unit
class TestRemoveOperation:
    """Tests for _apply_remove_operation edge cases."""

    def test_apply_update_operation_raises_when_node_data_none(self) -> None:
        """Test _apply_update_operation raises ValueError when node_data is None."""
        content = [
            {
                "id": "header_section",
                "category": "section",
                "children": [{"id": "field1", "category": "datapoint"}],
            }
        ]

        with pytest.raises(ValueError, match="node_data is required"):
            _apply_update_operation(content, "field1", None)

    def test_apply_remove_operation_cannot_remove_multivalue_child(self) -> None:
        """Test removing a multivalue's inner tuple directly raises error."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "line_items",
                        "category": "multivalue",
                        "children": {
                            "id": "line_item",
                            "category": "tuple",
                            "children": [{"id": "desc", "category": "datapoint"}],
                        },
                    }
                ],
            }
        ]

        with pytest.raises(ValueError, match="remove the multivalue instead"):
            _apply_remove_operation(content, "line_item")

    def test_apply_remove_operation_unexpected_parent_structure(self) -> None:
        """Test removing node with unexpected parent structure raises error."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "weird_node",
                        "category": "tuple",
                        "children": {
                            "id": "child_node",
                            "category": "datapoint",
                        },
                    }
                ],
            }
        ]

        with pytest.raises(ValueError, match="unexpected parent structure"):
            _apply_remove_operation(content, "child_node")

    def test_apply_remove_operation_top_level_node_without_section_category(self) -> None:
        """Test removing a top-level node without 'section' category (lines 394-397)."""
        content = [
            {"id": "top_level_node", "category": "datapoint", "label": "Top Level"},
            {"id": "section1", "category": "section", "children": []},
        ]

        with pytest.raises(ValueError, match="Cannot determine how to remove"):
            _apply_remove_operation(content, "top_level_node")

    def test_apply_remove_operation_top_level_section_without_category(self) -> None:
        """Test removing a top-level node with implicit section category (lines 395-396)."""
        content = [
            {"id": "implicit_section", "category": "section", "children": []},
        ]

        with pytest.raises(ValueError, match="Cannot remove a section"):
            _apply_remove_operation(content, "implicit_section")


@pytest.mark.unit
class TestNodeSearching:
    """Tests for node searching helper functions."""

    def test_find_node_in_children_finds_node_in_multivalue_dict(self) -> None:
        """Test finding a node directly inside multivalue's dict children."""
        multivalue_node = {
            "id": "line_items",
            "category": "multivalue",
            "children": {"id": "line_item", "category": "tuple", "children": []},
        }
        children = [multivalue_node]

        node, index, parent_list, parent_node = _find_node_in_children(children, "line_item", None)

        assert node is not None
        assert node["id"] == "line_item"
        assert index == 0
        assert parent_list is None
        assert parent_node == multivalue_node

    def test_find_node_in_children_finds_node_nested_in_tuple_within_multivalue(self) -> None:
        """Test finding a node nested inside tuple within multivalue."""
        tuple_node = {
            "id": "line_item",
            "category": "tuple",
            "children": [{"id": "description", "category": "datapoint"}],
        }
        multivalue_node = {
            "id": "line_items",
            "category": "multivalue",
            "children": tuple_node,
        }
        children = [multivalue_node]

        node, index, parent_list, parent_node = _find_node_in_children(children, "description", None)

        assert node is not None
        assert node["id"] == "description"
        assert index == 0
        assert parent_list == tuple_node["children"]
        assert parent_node == tuple_node

    def test_find_parent_children_list_returns_none_true_for_multivalue(self) -> None:
        """Test _find_parent_children_list returns (None, True) for multivalue parent."""
        content = [
            {
                "id": "section",
                "category": "section",
                "children": [{"id": "multivalue_node", "category": "multivalue", "children": {"id": "tuple"}}],
            }
        ]

        result, is_multivalue = _find_parent_children_list(content, "multivalue_node")

        assert result is None
        assert is_multivalue is True

    def test_find_parent_children_list_handles_none_section_children(self) -> None:
        """Test _find_parent_children_list skips sections with None children."""
        content = [
            {"id": "empty_section", "category": "section", "children": None},
            {"id": "target_section", "category": "section", "children": []},
        ]

        result, is_multivalue = _find_parent_children_list(content, "target_section")

        assert result == []
        assert is_multivalue is False

    def test_find_parent_children_list_handles_dict_children_in_section(self) -> None:
        """Test _find_parent_children_list handles dict children inside section."""
        content = [
            {
                "id": "section",
                "category": "section",
                "children": {"id": "tuple_child", "category": "tuple", "children": []},
            }
        ]

        result, is_multivalue = _find_parent_children_list(content, "tuple_child")

        assert result == []
        assert is_multivalue is False

    def test_find_parent_children_list_finds_parent_in_section_dict_children(self) -> None:
        """Test finding parent when node is inside section_children dict (multivalue case)."""
        content = [
            {
                "id": "section",
                "category": "section",
                "children": {
                    "id": "multivalue_child",
                    "category": "multivalue",
                    "children": {"id": "inner_tuple"},
                },
            }
        ]

        result, is_multivalue = _find_parent_children_list(content, "multivalue_child")

        assert result is None
        assert is_multivalue is True

    def test_apply_add_operation_error_for_multivalue_parent(self) -> None:
        """Test _apply_add_operation raises error when trying to add to multivalue parent."""
        content = [
            {
                "id": "section",
                "category": "section",
                "children": [{"id": "multivalue_node", "category": "multivalue", "children": {"id": "tuple"}}],
            }
        ]

        with pytest.raises(ValueError, match="Cannot add children to multivalue"):
            _apply_add_operation(
                content,
                node_id="new_node",
                node_data={"label": "New Node"},
                parent_id="multivalue_node",
                position=None,
            )

    def test_get_section_children_as_list_returns_empty_for_none(self) -> None:
        """Test _get_section_children_as_list returns [] when children is None."""
        section = {"id": "section", "children": None}

        result = _get_section_children_as_list(section)

        assert result == []

    def test_get_section_children_as_list_returns_list_when_list(self) -> None:
        """Test _get_section_children_as_list returns list when children is list."""
        children_list = [{"id": "child1"}, {"id": "child2"}]
        section = {"id": "section", "children": children_list}

        result = _get_section_children_as_list(section)

        assert result == children_list

    def test_get_section_children_as_list_returns_wrapped_dict(self) -> None:
        """Test _get_section_children_as_list returns [children] when children is dict."""
        child_dict = {"id": "child"}
        section = {"id": "section", "children": child_dict}

        result = _get_section_children_as_list(section)

        assert result == [child_dict]

    def test_find_node_anywhere_finds_section_by_id(self) -> None:
        """Test _find_node_anywhere finds section by ID and returns (section, None, None, None)."""
        content = [
            {"id": "section1", "category": "section", "children": []},
            {"id": "section2", "category": "section", "children": []},
        ]

        node, index, parent_list, parent_node = _find_node_anywhere(content, "section1")

        assert node is not None
        assert node["id"] == "section1"
        assert index is None
        assert parent_list is None
        assert parent_node is None

    def test_find_node_anywhere_finds_node_inside_multivalue(self) -> None:
        """Test _find_node_anywhere finds node inside multivalue structure."""
        content = [
            {
                "id": "section",
                "category": "section",
                "children": [
                    {
                        "id": "line_items",
                        "category": "multivalue",
                        "children": {
                            "id": "line_item",
                            "category": "tuple",
                            "children": [{"id": "amount", "category": "datapoint"}],
                        },
                    }
                ],
            }
        ]

        node, index, parent_list, parent_node = _find_node_anywhere(content, "amount")

        assert node is not None
        assert node["id"] == "amount"
        assert index == 0
        assert parent_list is not None
        assert parent_node["id"] == "line_item"

    def test_find_node_in_children_finds_nested_node_in_list_children(self) -> None:
        """Test finding a node nested in list children (line 251-253)."""
        tuple_node = {
            "id": "parent_tuple",
            "category": "tuple",
            "children": [{"id": "nested_field", "category": "datapoint"}],
        }
        children = [tuple_node]

        node, _index, _parent_list, parent_node = _find_node_in_children(children, "nested_field", None)

        assert node is not None
        assert node["id"] == "nested_field"
        assert parent_node == tuple_node

    def test_find_parent_children_list_section_is_multivalue(self) -> None:
        """Test _find_parent_children_list returns (None, True) for top-level multivalue section (line 279)."""
        content = [{"id": "multivalue_section", "category": "multivalue", "children": {"id": "inner"}}]

        result, is_multivalue = _find_parent_children_list(content, "multivalue_section")

        assert result is None
        assert is_multivalue is True

    def test_find_parent_children_list_dict_children_with_nested_search(self) -> None:
        """Test finding parent inside dict children's children list (lines 292-295)."""
        content = [
            {
                "id": "section",
                "category": "section",
                "children": {
                    "id": "outer_tuple",
                    "category": "tuple",
                    "children": [{"id": "target_tuple", "category": "tuple", "children": []}],
                },
            }
        ]

        result, is_multivalue = _find_parent_children_list(content, "target_tuple")

        assert result == []
        assert is_multivalue is False

    def test_find_parent_children_list_dict_children_no_nested_children(self) -> None:
        """Test dict children with no 'children' key returns None (line 294-295)."""
        content = [
            {
                "id": "section",
                "category": "section",
                "children": {"id": "simple_child", "category": "datapoint"},
            }
        ]

        result, is_multivalue = _find_parent_children_list(content, "nonexistent")

        assert result is None
        assert is_multivalue is False

    def test_apply_add_operation_missing_node_data_raises_error(self) -> None:
        """Test _apply_add_operation raises ValueError when node_data is None (line 316)."""
        content = [{"id": "section", "children": []}]

        with pytest.raises(ValueError, match="node_data is required"):
            _apply_add_operation(content, "new_id", None, "section", None)

    def test_apply_add_operation_missing_parent_id_raises_error(self) -> None:
        """Test _apply_add_operation raises ValueError when parent_id is None (line 318)."""
        content = [{"id": "section", "children": []}]

        with pytest.raises(ValueError, match="parent_id is required"):
            _apply_add_operation(content, "new_id", {"label": "New"}, None, None)

    def test_get_section_children_as_list_returns_empty_for_invalid_type(self) -> None:
        """Test _get_section_children_as_list returns [] for non-list/dict children (line 349)."""
        section = {"id": "section", "children": "invalid_string"}

        result = _get_section_children_as_list(section)

        assert result == []

    def test_apply_remove_operation_multivalue_child_raises_error(self) -> None:
        """Test removing a multivalue's direct child raises appropriate error (lines 395-397, 402-404)."""
        content = [
            {
                "id": "section",
                "category": "section",
                "children": [
                    {
                        "id": "mv",
                        "category": "multivalue",
                        "children": {"id": "inner_tuple", "category": "tuple", "children": []},
                    }
                ],
            }
        ]

        with pytest.raises(ValueError, match="Cannot remove 'inner_tuple' from multivalue"):
            _apply_remove_operation(content, "inner_tuple")
