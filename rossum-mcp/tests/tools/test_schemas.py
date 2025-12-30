"""Tests for rossum_mcp.tools.schemas module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.schema import Schema
from rossum_mcp.tools import base, schemas
from rossum_mcp.tools.schemas import (
    SchemaDatapoint,
    SchemaMultivalue,
    SchemaNodeUpdate,
    SchemaTuple,
    apply_schema_patch,
    register_schema_tools,
)

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def create_mock_schema(**kwargs) -> Schema:
    """Create a mock Schema dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/schemas/1",
        "name": "Test Schema",
        "queues": [],
        "content": [{"id": "section1", "label": "Section 1", "children": []}],
        "metadata": {},
        "modified_by": None,
        "modified_at": "2025-01-01T00:00:00Z",
    }
    defaults.update(kwargs)
    return Schema(**defaults)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    return client


@pytest.fixture
def mock_mcp() -> Mock:
    """Create a mock FastMCP instance that captures registered tools."""
    tools: dict = {}

    def tool_decorator(**kwargs):
        def wrapper(fn):
            tools[fn.__name__] = fn
            return fn

        return wrapper

    mcp = Mock()
    mcp.tool = tool_decorator
    mcp._tools = tools
    return mcp


@pytest.mark.unit
class TestGetSchema:
    """Tests for get_schema tool."""

    @pytest.mark.asyncio
    async def test_get_schema_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful schema retrieval."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schema = create_mock_schema(
            id=50,
            name="Invoice Schema",
            content=[
                {
                    "id": "header_section",
                    "label": "Header",
                    "children": [{"id": "invoice_number", "label": "Invoice Number"}],
                }
            ],
        )
        mock_client.retrieve_schema.return_value = mock_schema

        get_schema = mock_mcp._tools["get_schema"]
        result = await get_schema(schema_id=50)

        assert result.id == 50
        assert result.name == "Invoice Schema"
        assert len(result.content) == 1
        mock_client.retrieve_schema.assert_called_once_with(50)


@pytest.mark.unit
class TestUpdateSchema:
    """Tests for update_schema tool."""

    @pytest.mark.asyncio
    async def test_update_schema_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful schema update."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        register_schema_tools(mock_mcp, mock_client)

        updated_schema = create_mock_schema(id=50, name="Updated Schema")
        mock_client._http_client.update.return_value = {"id": 50}
        mock_client.retrieve_schema.return_value = updated_schema

        update_schema = mock_mcp._tools["update_schema"]
        result = await update_schema(schema_id=50, schema_data={"name": "Updated Schema"})

        assert result.id == 50
        assert result.name == "Updated Schema"

    @pytest.mark.asyncio
    async def test_update_schema_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test update_schema is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)

        register_schema_tools(mock_mcp, mock_client)

        update_schema = mock_mcp._tools["update_schema"]
        result = await update_schema(schema_id=50, schema_data={"name": "Updated"})

        assert result["error"] == "update_schema is not available in read-only mode"
        mock_client._http_client.update.assert_not_called()


@pytest.mark.unit
class TestCreateSchema:
    """Tests for create_schema tool."""

    @pytest.mark.asyncio
    async def test_create_schema_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful schema creation."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        register_schema_tools(mock_mcp, mock_client)

        content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [{"id": "invoice_number", "label": "Invoice Number", "type": "string"}],
            }
        ]

        new_schema = create_mock_schema(id=100, name="New Schema", content=content)
        mock_client.create_new_schema.return_value = new_schema

        create_schema = mock_mcp._tools["create_schema"]
        result = await create_schema(name="New Schema", content=content)

        assert result.id == 100
        assert result.name == "New Schema"
        mock_client.create_new_schema.assert_called_once_with({"name": "New Schema", "content": content})

    @pytest.mark.asyncio
    async def test_create_schema_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_schema is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)

        register_schema_tools(mock_mcp, mock_client)

        create_schema = mock_mcp._tools["create_schema"]
        result = await create_schema(name="New Schema", content=[])

        assert result["error"] == "create_schema is not available in read-only mode"
        mock_client.create_new_schema.assert_not_called()


@pytest.mark.unit
class TestPatchSchema:
    """Tests for patch_schema tool."""

    @pytest.mark.asyncio
    async def test_patch_schema_add_datapoint(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test adding a datapoint to a section."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [{"id": "invoice_number", "label": "Invoice Number", "category": "datapoint"}],
            }
        ]

        mock_schema = create_mock_schema(id=50, content=existing_content)
        mock_client.retrieve_schema.return_value = mock_schema
        mock_client._http_client.request_json.return_value = {"content": existing_content}
        mock_client._http_client.update.return_value = {}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="add",
            node_id="vendor_name",
            parent_id="header_section",
            node_data={"label": "Vendor Name", "type": "string", "category": "datapoint"},
        )

        assert result.id == 50
        mock_client._http_client.update.assert_called_once()
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        header_section = updated_content[0]
        assert len(header_section["children"]) == 2
        assert header_section["children"][1]["id"] == "vendor_name"

    @pytest.mark.asyncio
    async def test_patch_schema_update_datapoint(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test updating properties of an existing datapoint."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [
                    {
                        "id": "invoice_number",
                        "label": "Invoice Number",
                        "category": "datapoint",
                        "score_threshold": 0.5,
                    }
                ],
            }
        ]

        mock_schema = create_mock_schema(id=50, content=existing_content)
        mock_client.retrieve_schema.return_value = mock_schema
        mock_client._http_client.request_json.return_value = {"content": existing_content}
        mock_client._http_client.update.return_value = {}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="update",
            node_id="invoice_number",
            node_data={"label": "Invoice #", "score_threshold": 0.9},
        )

        assert result.id == 50
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        datapoint = updated_content[0]["children"][0]
        assert datapoint["label"] == "Invoice #"
        assert datapoint["score_threshold"] == 0.9

    @pytest.mark.asyncio
    async def test_patch_schema_remove_datapoint(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test removing a datapoint from a section."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [
                    {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint"},
                    {"id": "old_field", "label": "Old Field", "category": "datapoint"},
                ],
            }
        ]

        mock_schema = create_mock_schema(id=50, content=existing_content)
        mock_client.retrieve_schema.return_value = mock_schema
        mock_client._http_client.request_json.return_value = {"content": existing_content}
        mock_client._http_client.update.return_value = {}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="remove",
            node_id="old_field",
        )

        assert result.id == 50
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        header_section = updated_content[0]
        assert len(header_section["children"]) == 1
        assert header_section["children"][0]["id"] == "invoice_number"

    @pytest.mark.asyncio
    async def test_patch_schema_invalid_operation(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that invalid operation returns error."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="invalid",
            node_id="some_field",
        )

        assert result["error"] == "Invalid operation 'invalid'. Must be 'add', 'update', or 'remove'."

    @pytest.mark.asyncio
    async def test_patch_schema_unexpected_content_format(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test patch_schema when schema content is not a list."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_client._http_client.request_json.return_value = {"content": "not_a_list"}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="add",
            node_id="new_field",
            parent_id="section1",
            node_data={"label": "New Field"},
        )

        assert result["error"] == "Unexpected schema content format"
        mock_client._http_client.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_patch_schema_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test patch_schema is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="add",
            node_id="new_field",
            parent_id="header_section",
            node_data={"label": "New Field"},
        )

        assert result["error"] == "patch_schema is not available in read-only mode"
        mock_client._http_client.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_patch_schema_node_not_found(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that updating a non-existent node returns error."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [],
            }
        ]

        mock_schema = create_mock_schema(id=50, content=existing_content)
        mock_client.retrieve_schema.return_value = mock_schema
        mock_client._http_client.request_json.return_value = {"content": existing_content}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="update",
            node_id="nonexistent_field",
            node_data={"label": "Updated Label"},
        )

        assert "not found" in result["error"]


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

        with pytest.raises(ValueError, match=r"Cannot remove tuple .* from multivalue"):
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
class TestSchemaDataclasses:
    """Tests for schema dataclass types."""

    def test_schema_datapoint_to_dict(self) -> None:
        """Test SchemaDatapoint converts to dict excluding None values."""
        datapoint = SchemaDatapoint(label="Invoice Number", type="string", score_threshold=0.8)
        result = datapoint.to_dict()

        assert result["label"] == "Invoice Number"
        assert result["type"] == "string"
        assert result["category"] == "datapoint"
        assert result["score_threshold"] == 0.8
        assert "rir_field_names" not in result
        assert "formula" not in result

    def test_schema_datapoint_with_formula(self) -> None:
        """Test SchemaDatapoint with formula field."""
        datapoint = SchemaDatapoint(label="Total", type="number", formula="field_a + field_b")
        result = datapoint.to_dict()

        assert result["formula"] == "field_a + field_b"
        assert result["type"] == "number"

    def test_schema_tuple_to_dict(self) -> None:
        """Test SchemaTuple converts to dict with nested children."""
        tuple_node = SchemaTuple(
            id="line_item",
            label="Line Item",
            children=[
                SchemaDatapoint(label="Description", type="string"),
                SchemaDatapoint(label="Amount", type="number"),
            ],
        )
        result = tuple_node.to_dict()

        assert result["id"] == "line_item"
        assert result["label"] == "Line Item"
        assert result["category"] == "tuple"
        assert len(result["children"]) == 2
        assert result["children"][0]["label"] == "Description"
        assert result["children"][1]["label"] == "Amount"

    def test_schema_multivalue_with_tuple(self) -> None:
        """Test SchemaMultivalue with tuple children (table structure)."""
        multivalue = SchemaMultivalue(
            label="Line Items",
            children=SchemaTuple(
                id="line_item",
                label="Line Item",
                children=[
                    SchemaDatapoint(label="Description", type="string"),
                    SchemaDatapoint(label="Amount", type="number"),
                ],
            ),
        )
        result = multivalue.to_dict()

        assert result["label"] == "Line Items"
        assert result["category"] == "multivalue"
        assert result["children"]["id"] == "line_item"
        assert result["children"]["label"] == "Line Item"
        assert result["children"]["category"] == "tuple"

    def test_schema_multivalue_with_datapoint(self) -> None:
        """Test SchemaMultivalue with single datapoint (repeating field)."""
        multivalue = SchemaMultivalue(
            label="PO Numbers",
            children=SchemaDatapoint(label="PO Number", type="string"),
        )
        result = multivalue.to_dict()

        assert result["label"] == "PO Numbers"
        assert result["category"] == "multivalue"
        assert result["children"]["label"] == "PO Number"
        assert result["children"]["category"] == "datapoint"

    def test_schema_node_update_to_dict(self) -> None:
        """Test SchemaNodeUpdate only includes set fields."""
        update = SchemaNodeUpdate(label="Updated Label", score_threshold=0.9)
        result = update.to_dict()

        assert result == {"label": "Updated Label", "score_threshold": 0.9}
        assert "type" not in result
        assert "hidden" not in result

    def test_schema_tuple_with_hidden_true(self) -> None:
        """Test SchemaTuple with hidden=True includes hidden field in output."""
        tuple_node = SchemaTuple(
            id="hidden_tuple",
            label="Hidden Tuple",
            children=[SchemaDatapoint(label="Field", type="string")],
            hidden=True,
        )
        result = tuple_node.to_dict()

        assert result["id"] == "hidden_tuple"
        assert result["hidden"] is True
        assert result["category"] == "tuple"

    def test_schema_multivalue_all_optional_fields(self) -> None:
        """Test SchemaMultivalue with all optional fields set."""
        multivalue = SchemaMultivalue(
            label="Line Items",
            children=SchemaDatapoint(label="Item", type="string"),
            id="line_items_mv",
            rir_field_names=["line_items"],
            min_occurrences=1,
            max_occurrences=10,
            hidden=True,
        )
        result = multivalue.to_dict()

        assert result["id"] == "line_items_mv"
        assert result["rir_field_names"] == ["line_items"]
        assert result["min_occurrences"] == 1
        assert result["max_occurrences"] == 10
        assert result["hidden"] is True
        assert result["category"] == "multivalue"

    def test_schema_node_update_with_stretch(self) -> None:
        """Test SchemaNodeUpdate with stretch field."""
        update = SchemaNodeUpdate(label="Column", width=100, stretch=True)
        result = update.to_dict()

        assert result["label"] == "Column"
        assert result["width"] == 100
        assert result["stretch"] is True

    @pytest.mark.asyncio
    async def test_patch_schema_with_dataclass(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test patch_schema accepts dataclass node_data."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [],
            }
        ]

        mock_schema = create_mock_schema(id=50, content=existing_content)
        mock_client.retrieve_schema.return_value = mock_schema
        mock_client._http_client.request_json.return_value = {"content": existing_content}
        mock_client._http_client.update.return_value = {}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="add",
            node_id="vendor_name",
            parent_id="header_section",
            node_data=SchemaDatapoint(label="Vendor Name", type="string"),
        )

        assert result.id == 50
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        header_section = updated_content[0]
        assert len(header_section["children"]) == 1
        assert header_section["children"][0]["id"] == "vendor_name"
        assert header_section["children"][0]["label"] == "Vendor Name"

    @pytest.mark.asyncio
    async def test_patch_schema_update_with_dataclass(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test patch_schema update operation with SchemaNodeUpdate dataclass."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [{"id": "invoice_number", "label": "Invoice Number", "category": "datapoint"}],
            }
        ]

        mock_schema = create_mock_schema(id=50, content=existing_content)
        mock_client.retrieve_schema.return_value = mock_schema
        mock_client._http_client.request_json.return_value = {"content": existing_content}
        mock_client._http_client.update.return_value = {}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="update",
            node_id="invoice_number",
            node_data=SchemaNodeUpdate(label="Invoice #", score_threshold=0.95),
        )

        assert result.id == 50
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        datapoint = updated_content[0]["children"][0]
        assert datapoint["label"] == "Invoice #"
        assert datapoint["score_threshold"] == 0.95
