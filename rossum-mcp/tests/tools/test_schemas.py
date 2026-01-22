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
    _apply_add_operation,
    _apply_remove_operation,
    _apply_update_operation,
    _collect_all_field_ids,
    _find_node_anywhere,
    _find_node_in_children,
    _find_parent_children_list,
    _get_section_children_as_list,
    _remove_fields_from_content,
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

    @pytest.mark.asyncio
    async def test_get_schema_not_found(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test schema not found returns error dict instead of raising exception."""
        from rossum_api import APIClientError

        register_schema_tools(mock_mcp, mock_client)

        mock_client.retrieve_schema.side_effect = APIClientError(
            method="GET",
            url="https://api.test/schemas/999",
            status_code=404,
            error=Exception("Not found"),
        )

        get_schema = mock_mcp._tools["get_schema"]
        result = await get_schema(schema_id=999)

        assert isinstance(result, dict)
        assert "error" in result
        assert "999" in result["error"]
        assert "not found" in result["error"]


@pytest.mark.unit
class TestListSchemas:
    """Tests for list_schemas tool."""

    @pytest.mark.asyncio
    async def test_list_schemas_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful schema listing."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schemas = [
            create_mock_schema(id=1, name="Schema 1"),
            create_mock_schema(id=2, name="Schema 2"),
        ]

        async def mock_list_schemas(**filters):
            for schema in mock_schemas:
                yield schema

        mock_client.list_schemas = mock_list_schemas

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas()

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2

    @pytest.mark.asyncio
    async def test_list_schemas_with_name_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test schema listing with name filter."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schemas = [create_mock_schema(id=1, name="Invoice Schema")]
        filters_received = {}

        async def mock_list_schemas(**filters):
            nonlocal filters_received
            filters_received = filters
            for schema in mock_schemas:
                yield schema

        mock_client.list_schemas = mock_list_schemas

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas(name="Invoice Schema")

        assert len(result) == 1
        assert filters_received["name"] == "Invoice Schema"

    @pytest.mark.asyncio
    async def test_list_schemas_with_queue_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test schema listing with queue filter."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schemas = [create_mock_schema(id=1, name="Schema 1")]
        filters_received = {}

        async def mock_list_schemas(**filters):
            nonlocal filters_received
            filters_received = filters
            for schema in mock_schemas:
                yield schema

        mock_client.list_schemas = mock_list_schemas

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas(queue_id=5)

        assert len(result) == 1
        assert filters_received["queue"] == 5

    @pytest.mark.asyncio
    async def test_list_schemas_with_all_filters(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test schema listing with all filters."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schemas = [create_mock_schema(id=1, name="Test Schema")]
        filters_received = {}

        async def mock_list_schemas(**filters):
            nonlocal filters_received
            filters_received = filters
            for schema in mock_schemas:
                yield schema

        mock_client.list_schemas = mock_list_schemas

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas(name="Test Schema", queue_id=3)

        assert len(result) == 1
        assert filters_received["name"] == "Test Schema"
        assert filters_received["queue"] == 3

    @pytest.mark.asyncio
    async def test_list_schemas_empty_result(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test schema listing with no results."""
        register_schema_tools(mock_mcp, mock_client)

        async def mock_list_schemas(**filters):
            return
            yield

        mock_client.list_schemas = mock_list_schemas

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_schemas_truncates_content(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test that content field is truncated in list response."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schema = create_mock_schema(
            id=1,
            name="Schema 1",
            content=[
                {
                    "id": "header_section",
                    "label": "Header",
                    "children": [{"id": "invoice_number", "label": "Invoice Number"}],
                }
            ],
        )

        async def mock_list_schemas(**filters):
            yield mock_schema

        mock_client.list_schemas = mock_list_schemas

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas()

        assert len(result) == 1
        assert result[0].content == "<omitted>"
        assert result[0].name == "Schema 1"
        assert result[0].id == 1


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


@pytest.mark.unit
class TestGetSchemaTreeStructure:
    """Tests for get_schema_tree_structure tool."""

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful tree structure extraction."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schema = create_mock_schema(
            id=50,
            content=[
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"},
                        {"id": "invoice_date", "label": "Invoice Date", "category": "datapoint", "type": "date"},
                    ],
                },
                {
                    "id": "line_items_section",
                    "label": "Line Items",
                    "category": "section",
                    "children": [
                        {
                            "id": "line_items",
                            "label": "Line Items",
                            "category": "multivalue",
                            "children": {
                                "id": "line_item",
                                "label": "Line Item",
                                "category": "tuple",
                                "children": [
                                    {
                                        "id": "description",
                                        "label": "Description",
                                        "category": "datapoint",
                                        "type": "string",
                                    },
                                    {"id": "amount", "label": "Amount", "category": "datapoint", "type": "number"},
                                ],
                            },
                        }
                    ],
                },
            ],
        )
        mock_client.retrieve_schema.return_value = mock_schema

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        result = await get_schema_tree_structure(schema_id=50)

        assert len(result) == 2
        assert result[0]["id"] == "header_section"
        assert result[0]["label"] == "Header"
        assert len(result[0]["children"]) == 2
        assert result[0]["children"][0]["id"] == "invoice_number"
        assert result[0]["children"][0]["type"] == "string"
        assert result[1]["children"][0]["id"] == "line_items"
        assert result[1]["children"][0]["children"][0]["id"] == "line_item"

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_not_found(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test tree structure returns error dict when schema not found."""
        from rossum_api import APIClientError

        register_schema_tools(mock_mcp, mock_client)

        mock_client.retrieve_schema.side_effect = APIClientError(
            method="GET",
            url="https://api.test/schemas/999",
            status_code=404,
            error=Exception("Not found"),
        )

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        result = await get_schema_tree_structure(schema_id=999)

        assert isinstance(result, dict)
        assert "error" in result
        assert "999" in result["error"]
        assert "not found" in result["error"]


@pytest.mark.unit
class TestPruneSchemaFields:
    """Tests for prune_schema_fields tool."""

    @pytest.mark.asyncio
    async def test_prune_schema_fields_with_fields_to_keep(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test pruning with fields_to_keep."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"},
                        {"id": "invoice_date", "label": "Invoice Date", "category": "datapoint", "type": "date"},
                        {"id": "vendor_name", "label": "Vendor Name", "category": "datapoint", "type": "string"},
                    ],
                }
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict
        mock_client._http_client.update.return_value = {}

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_keep=["invoice_number"])

        assert "invoice_date" in result["removed_fields"]
        assert "vendor_name" in result["removed_fields"]
        assert "invoice_number" in result["remaining_fields"]
        assert "header_section" in result["remaining_fields"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_with_fields_to_remove(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test pruning with fields_to_remove."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"},
                        {"id": "invoice_date", "label": "Invoice Date", "category": "datapoint", "type": "date"},
                    ],
                }
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict
        mock_client._http_client.update.return_value = {}

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_remove=["invoice_date"])

        assert "invoice_date" in result["removed_fields"]
        assert "invoice_number" in result["remaining_fields"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test pruning in read-only mode returns error."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_keep=["invoice_number"])

        assert "error" in result
        assert "read-only" in result["error"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_both_params_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test error when both fields_to_keep and fields_to_remove provided."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_keep=["a"], fields_to_remove=["b"])

        assert "error" in result
        assert "not both" in result["error"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_no_params_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test error when neither parameter provided."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50)

        assert "error" in result
        assert "Must specify" in result["error"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_preserves_parent_containers_for_nested_fields(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that keeping a nested field preserves its parent containers (multivalue, section)."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "197466",
                    "category": "section",
                    "schema_id": "invoice_info_section",
                    "children": [
                        {
                            "id": "197467",
                            "category": "datapoint",
                            "schema_id": "invoice_number",
                            "page": 1,
                            "position": [916, 168, 1190, 222],
                            "rir_position": [916, 168, 1190, 222],
                            "rir_confidence": 0.97657,
                            "value": "FV103828806S",
                            "validation_sources": ["score"],
                            "type": "string",
                        },
                        {
                            "id": "197468",
                            "category": "datapoint",
                            "schema_id": "date_due",
                            "page": 1,
                            "position": [938, 618, 1000, 654],
                            "rir_position": [940, 618, 1020, 655],
                            "rir_confidence": 0.98279,
                            "value": "12/22/2018",
                            "validation_sources": ["score"],
                            "type": "date",
                        },
                        {
                            "id": "197469",
                            "category": "datapoint",
                            "schema_id": "amount_due",
                            "page": 1,
                            "position": [1134, 1050, 1190, 1080],
                            "rir_position": [1134, 1050, 1190, 1080],
                            "rir_confidence": 0.74237,
                            "value": "55.20",
                            "validation_sources": ["human"],
                            "type": "number",
                        },
                    ],
                },
                {
                    "id": "197500",
                    "category": "section",
                    "schema_id": "line_items_section",
                    "children": [
                        {
                            "id": "197501",
                            "category": "multivalue",
                            "schema_id": "line_items",
                            "children": [
                                {
                                    "id": "198139",
                                    "category": "tuple",
                                    "schema_id": "line_item",
                                    "children": [
                                        {
                                            "id": "198140",
                                            "category": "datapoint",
                                            "schema_id": "item_desc",
                                            "page": 1,
                                            "position": [173, 883, 395, 904],
                                            "rir_position": None,
                                            "rir_confidence": None,
                                            "value": "Red Rose",
                                            "validation_sources": [],
                                            "type": "string",
                                        },
                                        {
                                            "id": "198142",
                                            "category": "datapoint",
                                            "schema_id": "item_net_unit_price",
                                            "page": 1,
                                            "position": [714, 846, 768, 870],
                                            "rir_position": None,
                                            "rir_confidence": None,
                                            "value": "1532.02",
                                            "validation_sources": ["human"],
                                            "type": "number",
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                },
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict
        mock_client._http_client.update.return_value = {}

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_keep=["198140"])

        assert "197501" in result["remaining_fields"]
        assert "197500" in result["remaining_fields"]
        assert "198139" in result["remaining_fields"]
        assert "198140" in result["remaining_fields"]

        assert "198142" in result["removed_fields"]
        assert "197467" in result["removed_fields"]
        assert "197468" in result["removed_fields"]
        assert "197469" in result["removed_fields"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_all_fields_kept(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test prune when fields_to_keep matches all fields so remove_set is empty."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"}
                    ],
                }
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_keep=["header_section", "invoice_number"])

        assert result["removed_fields"] == []
        assert sorted(result["remaining_fields"]) == ["header_section", "invoice_number"]
        mock_client._http_client.update.assert_not_called()

    def _setup_multivalue_schema(
        self,
        mock_mcp: Mock,
        mock_client: AsyncMock,
        monkeypatch: MonkeyPatch,
        tuple_children: list[dict],
    ) -> None:
        """Set up read-write mode and configure mock with a multivalue schema."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)
        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"},
                        {
                            "id": "line_items",
                            "label": "Line Items",
                            "category": "multivalue",
                            "children": {
                                "id": "line_item",
                                "label": "Line Item",
                                "category": "tuple",
                                "children": tuple_children,
                            },
                        },
                    ],
                }
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict
        mock_client._http_client.update.return_value = {}

    @pytest.mark.asyncio
    async def test_prune_schema_fields_removes_multivalue_when_tuple_removed(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that removing tuple also removes parent multivalue (no stub left)."""
        self._setup_multivalue_schema(
            mock_mcp,
            mock_client,
            monkeypatch,
            tuple_children=[{"id": "item_desc", "label": "Description", "category": "datapoint", "type": "string"}],
        )

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_remove=["line_item"])

        assert "line_item" in result["removed_fields"]
        assert "line_items" in result["removed_fields"]
        assert "invoice_number" in result["remaining_fields"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_removes_multivalue_when_all_tuple_children_removed(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that removing all tuple children also removes multivalue."""
        self._setup_multivalue_schema(
            mock_mcp,
            mock_client,
            monkeypatch,
            tuple_children=[
                {"id": "item_desc", "label": "Description", "category": "datapoint", "type": "string"},
                {"id": "item_qty", "label": "Quantity", "category": "datapoint", "type": "number"},
            ],
        )

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_remove=["item_desc", "item_qty"])

        assert "item_desc" in result["removed_fields"]
        assert "item_qty" in result["removed_fields"]
        assert "line_item" in result["removed_fields"]
        assert "line_items" in result["removed_fields"]
        assert "invoice_number" in result["remaining_fields"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_removes_empty_sections(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that sections with no remaining children are removed (API rejects empty sections)."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"}
                    ],
                },
                {
                    "id": "payment_section",
                    "label": "Payment",
                    "category": "section",
                    "children": [
                        {"id": "bank_account", "label": "Bank Account", "category": "datapoint", "type": "string"}
                    ],
                },
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict
        mock_client._http_client.update.return_value = {}

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_keep=["invoice_number"])

        assert "bank_account" in result["removed_fields"]
        assert "payment_section" in result["removed_fields"]
        assert "invoice_number" in result["remaining_fields"]
        assert "header_section" in result["remaining_fields"]
        assert "payment_section" not in result["remaining_fields"]


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
            schemas._apply_remove_operation(content, "top_level_node")

    def test_apply_remove_operation_top_level_section_without_category(self) -> None:
        """Test removing a top-level node with implicit section category (lines 395-396)."""
        content = [
            {"id": "implicit_section", "category": "section", "children": []},
        ]

        with pytest.raises(ValueError, match="Cannot remove a section"):
            schemas._apply_remove_operation(content, "implicit_section")


@pytest.mark.unit
class TestFieldPruning:
    """Tests for field collection and pruning functions."""

    def test_collect_all_field_ids_with_dict_children(self) -> None:
        """Test _collect_all_field_ids traverses dict children (multivalue case)."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "multivalue1",
                        "category": "multivalue",
                        "children": {
                            "id": "tuple1",
                            "category": "tuple",
                            "children": [
                                {"id": "field1", "category": "datapoint"},
                                {"id": "field2", "category": "datapoint"},
                            ],
                        },
                    }
                ],
            }
        ]

        result = _collect_all_field_ids(content)

        assert result == {"section1", "multivalue1", "tuple1", "field1", "field2"}

    def test_remove_fields_from_nested_list_children(self) -> None:
        """Test _remove_fields_from_content removes field from nested list children."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "parent1",
                        "category": "tuple",
                        "children": [
                            {"id": "keep_field", "category": "datapoint"},
                            {"id": "remove_field", "category": "datapoint"},
                        ],
                    }
                ],
            }
        ]

        result, removed = _remove_fields_from_content(content, {"remove_field"})

        assert removed == ["remove_field"]
        parent_children = result[0]["children"][0]["children"]
        assert len(parent_children) == 1
        assert parent_children[0]["id"] == "keep_field"

    def test_remove_fields_from_dict_children_inner_tuple(self) -> None:
        """Test _remove_fields_from_content removes entire multivalue when tuple is removed."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "multivalue1",
                        "category": "multivalue",
                        "children": {
                            "id": "tuple1",
                            "category": "tuple",
                            "children": [
                                {"id": "keep_me", "category": "datapoint"},
                                {"id": "remove_me", "category": "datapoint"},
                            ],
                        },
                    }
                ],
            }
        ]

        result, removed = _remove_fields_from_content(content, {"tuple1"})

        assert "tuple1" in removed
        assert "multivalue1" in removed
        assert "section1" in removed
        assert result == []

    def test_remove_fields_filters_inside_dict_children_nested(self) -> None:
        """Test _remove_fields_from_content filters children inside dict children's nested list."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "multivalue1",
                        "category": "multivalue",
                        "children": {
                            "id": "tuple1",
                            "category": "tuple",
                            "children": [
                                {"id": "desc", "category": "datapoint"},
                                {"id": "amount", "category": "datapoint"},
                                {"id": "unit_price", "category": "datapoint"},
                            ],
                        },
                    }
                ],
            }
        ]

        result, removed = _remove_fields_from_content(content, {"amount", "unit_price"})

        assert sorted(removed) == ["amount", "unit_price"]
        tuple_children = result[0]["children"][0]["children"]["children"]
        assert len(tuple_children) == 1
        assert tuple_children[0]["id"] == "desc"


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

        node, _index, _parent_list, parent_node = schemas._find_node_in_children(children, "nested_field", None)

        assert node is not None
        assert node["id"] == "nested_field"
        assert parent_node == tuple_node

    def test_find_parent_children_list_section_is_multivalue(self) -> None:
        """Test _find_parent_children_list returns (None, True) for top-level multivalue section (line 279)."""
        content = [{"id": "multivalue_section", "category": "multivalue", "children": {"id": "inner"}}]

        result, is_multivalue = schemas._find_parent_children_list(content, "multivalue_section")

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

        result, is_multivalue = schemas._find_parent_children_list(content, "target_tuple")

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

        result, is_multivalue = schemas._find_parent_children_list(content, "nonexistent")

        assert result is None
        assert is_multivalue is False

    def test_apply_add_operation_missing_node_data_raises_error(self) -> None:
        """Test _apply_add_operation raises ValueError when node_data is None (line 316)."""
        content = [{"id": "section", "children": []}]

        with pytest.raises(ValueError, match="node_data is required"):
            schemas._apply_add_operation(content, "new_id", None, "section", None)

    def test_apply_add_operation_missing_parent_id_raises_error(self) -> None:
        """Test _apply_add_operation raises ValueError when parent_id is None (line 318)."""
        content = [{"id": "section", "children": []}]

        with pytest.raises(ValueError, match="parent_id is required"):
            schemas._apply_add_operation(content, "new_id", {"label": "New"}, None, None)

    def test_get_section_children_as_list_returns_empty_for_invalid_type(self) -> None:
        """Test _get_section_children_as_list returns [] for non-list/dict children (line 349)."""
        section = {"id": "section", "children": "invalid_string"}

        result = schemas._get_section_children_as_list(section)

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
            schemas._apply_remove_operation(content, "inner_tuple")


@pytest.mark.unit
class TestSchemaValidation:
    """Tests for schema validation functions.

    Note: These tests use schemas.* to access functions/classes dynamically
    because other tests use importlib.reload(schemas) which creates new class objects.
    """

    def test_validate_id_empty_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Node id is required"):
            schemas._validate_id("")

    def test_validate_id_exceeds_max_length_raises_error(self) -> None:
        long_id = "a" * 51
        with pytest.raises(schemas.SchemaValidationError, match="exceeds 50 characters"):
            schemas._validate_id(long_id)

    def test_validate_id_valid_passes(self) -> None:
        schemas._validate_id("valid_id")
        schemas._validate_id("a" * 50)

    def test_validate_datapoint_missing_label_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="missing required 'label'"):
            schemas._validate_datapoint({"type": "string"})

    def test_validate_datapoint_missing_type_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="missing required 'type'"):
            schemas._validate_datapoint({"label": "Test"})

    def test_validate_datapoint_invalid_type_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Invalid datapoint type 'invalid'"):
            schemas._validate_datapoint({"label": "Test", "type": "invalid"})

    def test_validate_datapoint_valid_types_pass(self) -> None:
        for dp_type in ["string", "number", "date", "enum", "button"]:
            schemas._validate_datapoint({"label": "Test", "type": dp_type})

    def test_validate_tuple_missing_label_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Tuple missing required 'label'"):
            schemas._validate_tuple({"id": "test", "children": []}, "test", "")

    def test_validate_tuple_missing_id_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Tuple missing required 'id'"):
            schemas._validate_tuple({"label": "Test", "children": []}, "", "")

    def test_validate_tuple_children_not_list_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="children must be a list"):
            schemas._validate_tuple({"id": "test", "label": "Test", "children": {}}, "test", "")

    def test_validate_tuple_child_without_id_raises_error(self) -> None:
        node = {
            "id": "test",
            "label": "Test",
            "children": [{"category": "datapoint", "label": "Child", "type": "string"}],
        }
        with pytest.raises(schemas.SchemaValidationError, match="must have 'id'"):
            schemas._validate_tuple(node, "test", "")

    def test_validate_multivalue_missing_label_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Multivalue missing required 'label'"):
            schemas._validate_multivalue({"children": {}}, "test", "")

    def test_validate_multivalue_missing_children_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Multivalue missing required 'children'"):
            schemas._validate_multivalue({"label": "Test"}, "test", "")

    def test_validate_multivalue_children_as_list_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="must be a single object"):
            schemas._validate_multivalue({"label": "Test", "children": []}, "test", "")

    def test_validate_section_missing_label_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Section missing required 'label'"):
            schemas._validate_section({"id": "test", "children": []}, "test", "")

    def test_validate_section_missing_id_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Section missing required 'id'"):
            schemas._validate_section({"label": "Test", "children": []}, "", "")

    def test_validate_section_children_not_list_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="children must be a list"):
            schemas._validate_section({"id": "test", "label": "Test", "children": {}}, "test", "")

    def test_validate_node_datapoint(self) -> None:
        schemas._validate_node({"category": "datapoint", "id": "field", "label": "Field", "type": "string"})

    def test_validate_node_tuple(self) -> None:
        node = {
            "category": "tuple",
            "id": "row",
            "label": "Row",
            "children": [{"category": "datapoint", "id": "col", "label": "Col", "type": "string"}],
        }
        schemas._validate_node(node)

    def test_validate_node_multivalue(self) -> None:
        node = {
            "category": "multivalue",
            "id": "items",
            "label": "Items",
            "children": {"category": "tuple", "id": "item", "label": "Item", "children": []},
        }
        schemas._validate_node(node)

    def test_validate_node_section(self) -> None:
        node = {
            "category": "section",
            "id": "header",
            "label": "Header",
            "children": [{"category": "datapoint", "id": "field", "label": "Field", "type": "string"}],
        }
        schemas._validate_node(node)

    def test_validate_node_invalid_id_in_nested_child(self) -> None:
        node = {
            "category": "section",
            "id": "header",
            "label": "Header",
            "children": [{"category": "datapoint", "id": "a" * 51, "label": "Field", "type": "string"}],
        }
        with pytest.raises(schemas.SchemaValidationError, match="exceeds 50 characters"):
            schemas._validate_node(node)
