"""Tests for schema update, patch, prune, and list operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from conftest import create_mock_queue, create_mock_schema
from fastmcp.exceptions import ToolError
from rossum_api import APIClientError
from rossum_api.domain_logic.resources import Resource
from rossum_mcp.tools.search.models import SchemaListItem
from rossum_mcp.tools.search.registry import _list_schemas
from rossum_mcp.tools.update.handler import register_update_tools


@pytest.mark.unit
class TestListSchemas:
    """Tests for list_schemas tool."""

    @pytest.mark.asyncio
    async def test_list_schemas_success(self, mock_client: AsyncMock) -> None:
        """Test successful schema listing."""
        mock_schemas = [
            create_mock_schema(id=1, name="Schema 1"),
            create_mock_schema(id=2, name="Schema 2"),
        ]

        async def mock_fetch_all(resource, **filters):
            for schema in mock_schemas:
                yield schema

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_schemas(mock_client)

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2

    @pytest.mark.asyncio
    async def test_list_schemas_with_name_filter(self, mock_client: AsyncMock) -> None:
        """Test schema listing with name filter."""
        mock_schemas = [create_mock_schema(id=1, name="Invoice Schema")]
        filters_received = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal filters_received
            filters_received = filters
            for schema in mock_schemas:
                yield schema

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_schemas(mock_client, name="Invoice Schema")

        assert len(result) == 1
        assert filters_received["name"] == "Invoice Schema"

    @pytest.mark.asyncio
    async def test_list_schemas_with_queue_filter(self, mock_client: AsyncMock) -> None:
        """Test schema listing with queue filter."""
        mock_schemas = [create_mock_schema(id=1, name="Schema 1")]
        filters_received = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal filters_received
            filters_received = filters
            for schema in mock_schemas:
                yield schema

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_schemas(mock_client, queue_id=5)

        assert len(result) == 1
        assert filters_received["queue"] == 5

    @pytest.mark.asyncio
    async def test_list_schemas_with_all_filters(self, mock_client: AsyncMock) -> None:
        """Test schema listing with all filters."""
        mock_schemas = [create_mock_schema(id=1, name="Test Schema")]
        filters_received = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal filters_received
            filters_received = filters
            for schema in mock_schemas:
                yield schema

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_schemas(mock_client, name="Test Schema", queue_id=3)

        assert len(result) == 1
        assert filters_received["name"] == "Test Schema"
        assert filters_received["queue"] == 3

    @pytest.mark.asyncio
    async def test_list_schemas_empty_result(self, mock_client: AsyncMock) -> None:
        """Test schema listing with no results."""

        async def mock_fetch_all(resource, **filters):
            return
            yield

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_schemas(mock_client)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_schemas_truncates_content(self, mock_client: AsyncMock) -> None:
        """Test that content field is truncated in list response."""
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

        async def mock_fetch_all(resource, **filters):
            yield mock_schema

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_schemas(mock_client)

        assert len(result) == 1
        item = result[0]
        assert isinstance(item, SchemaListItem)
        assert item.content == "<omitted>"
        assert item.name == "Schema 1"
        assert item.id == 1

    @pytest.mark.asyncio
    async def test_list_schemas_skips_broken_items(self, mock_client: AsyncMock) -> None:
        """Test list_schemas gracefully skips items that fail deserialization."""
        good_schema = create_mock_schema(id=1, name="Good Schema")

        def mock_deserializer(resource, raw):
            if raw.get("id") == 2:
                raise ValueError("broken schema")
            return good_schema

        mock_client._deserializer = mock_deserializer

        async def mock_fetch_all(resource, **filters):
            yield {"id": 1, "name": "Good Schema"}
            yield {"id": 2, "name": "Broken Schema"}
            yield {"id": 3, "name": "Another Good Schema"}

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_schemas(mock_client)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_schemas_with_regex_name_filter(self, mock_client: AsyncMock) -> None:
        """Test that use_regex=True filters schemas client-side by regex pattern."""
        mock_schemas = [
            create_mock_schema(id=1, name="Invoice Schema"),
            create_mock_schema(id=2, name="Receipt Schema"),
            create_mock_schema(id=3, name="invoice_v2"),
        ]
        filters_received = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal filters_received
            filters_received = filters
            for schema in mock_schemas:
                yield schema

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_schemas(mock_client, name="invoice", use_regex=True)

        assert len(result) == 2
        assert result[0].name == "Invoice Schema"
        assert result[1].name == "invoice_v2"
        assert "name" not in filters_received

    @pytest.mark.asyncio
    async def test_list_schemas_with_regex_no_match(self, mock_client: AsyncMock) -> None:
        """Test that use_regex=True returns empty list when no schemas match pattern."""
        mock_schemas = [create_mock_schema(id=1, name="Receipt Schema")]

        async def mock_fetch_all(resource, **filters):
            for schema in mock_schemas:
                yield schema

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_schemas(mock_client, name="^invoice$", use_regex=True)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_schemas_resolves_workspaces(self, mock_client: AsyncMock) -> None:
        """Test that workspace URLs are resolved from queue data."""
        mock_schemas = [
            create_mock_schema(
                id=1,
                name="Schema 1",
                queues=[
                    "https://api.test.rossum.ai/v1/queues/10",
                    "https://api.test.rossum.ai/v1/queues/20",
                ],
            ),
            create_mock_schema(
                id=2,
                name="Schema 2",
                queues=["https://api.test.rossum.ai/v1/queues/20"],
            ),
        ]
        mock_queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
            create_mock_queue(
                id=20,
                url="https://api.test.rossum.ai/v1/queues/20",
                workspace="https://api.test.rossum.ai/v1/workspaces/200",
            ),
        ]

        async def mock_fetch_all(resource, **filters):
            items = mock_schemas if resource == Resource.Schema else mock_queues
            for item in items:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_schemas(mock_client)

        assert len(result) == 2
        assert sorted(result[0].workspaces) == [
            "https://api.test.rossum.ai/v1/workspaces/100",
            "https://api.test.rossum.ai/v1/workspaces/200",
        ]
        assert result[1].workspaces == ["https://api.test.rossum.ai/v1/workspaces/200"]

    @pytest.mark.asyncio
    async def test_list_schemas_workspaces_none_when_no_queues(self, mock_client: AsyncMock) -> None:
        """Test that workspaces is None when schema has no queues."""
        mock_schemas = [create_mock_schema(id=1, name="Schema 1", queues=[])]

        async def mock_fetch_all(resource, **filters):
            for schema in mock_schemas:
                yield schema

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_schemas(mock_client)

        assert len(result) == 1
        assert result[0].workspaces is None


@pytest.mark.unit
class TestPatchSchema:
    """Tests for patch_schema tool."""

    @pytest.mark.asyncio
    async def test_patch_schema_add_datapoint(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test adding a datapoint to a section."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

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

        assert result["status"] == "success"
        assert result["schema_id"] == 50
        assert result["node_id"] == "vendor_name"
        assert result["node"]["label"] == "Vendor Name"
        mock_client._http_client.update.assert_called_once()
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        header_section = updated_content[0]
        assert len(header_section["children"]) == 2
        assert header_section["children"][1]["id"] == "vendor_name"

    @pytest.mark.asyncio
    async def test_patch_schema_update_datapoint(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test updating properties of an existing datapoint."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

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

        assert result["status"] == "success"
        assert result["schema_id"] == 50
        assert result["node"]["label"] == "Invoice #"
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        datapoint = updated_content[0]["children"][0]
        assert datapoint["label"] == "Invoice #"
        assert datapoint["score_threshold"] == 0.9

    @pytest.mark.asyncio
    async def test_patch_schema_remove_datapoint(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test removing a datapoint from a section."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

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

        assert result["status"] == "success"
        assert result["schema_id"] == 50
        assert result["node"] is None
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        header_section = updated_content[0]
        assert len(header_section["children"]) == 1
        assert header_section["children"][0]["id"] == "invoice_number"

    @pytest.mark.asyncio
    async def test_patch_schema_retries_on_412(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test that patch_schema retries on 412 Precondition Failed."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

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
        mock_client._http_client.update.side_effect = [
            APIClientError("PATCH", "schemas/50", 412, "Precondition Failed"),
            {},
        ]

        patch_schema = mock_mcp._tools["patch_schema"]
        with patch("rossum_mcp.tools.update.schemas.handler.asyncio.sleep", new_callable=AsyncMock):
            result = await patch_schema(
                schema_id=50,
                operation="add",
                node_id="vendor_name",
                parent_id="header_section",
                node_data={"label": "Vendor Name", "type": "string", "category": "datapoint"},
            )

        assert result["status"] == "success"
        assert result["schema_id"] == 50
        assert mock_client._http_client.update.call_count == 2
        assert mock_client._http_client.request_json.call_count == 2

    @pytest.mark.asyncio
    async def test_patch_schema_raises_after_max_retries_on_412(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test that patch_schema raises after exhausting retries on 412."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [{"id": "invoice_number", "label": "Invoice Number", "category": "datapoint"}],
            }
        ]

        mock_client._http_client.request_json.return_value = {"content": existing_content}
        mock_client._http_client.update.side_effect = APIClientError("PATCH", "schemas/50", 412, "Precondition Failed")

        patch_schema = mock_mcp._tools["patch_schema"]
        with (
            patch("rossum_mcp.tools.update.schemas.handler.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(APIClientError, match="412"),
        ):
            await patch_schema(
                schema_id=50,
                operation="add",
                node_id="vendor_name",
                parent_id="header_section",
                node_data={"label": "Vendor Name", "type": "string", "category": "datapoint"},
            )

    @pytest.mark.asyncio
    async def test_patch_schema_invalid_operation(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test that invalid operation returns error."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        patch_schema = mock_mcp._tools["patch_schema"]
        with pytest.raises(ToolError, match="Invalid operation 'invalid'"):
            await patch_schema(
                schema_id=50,
                operation="invalid",
                node_id="some_field",
            )

    @pytest.mark.asyncio
    async def test_patch_schema_unexpected_content_format(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test patch_schema when schema content is not a list."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_client._http_client.request_json.return_value = {"content": "not_a_list"}

        patch_schema = mock_mcp._tools["patch_schema"]
        with pytest.raises(ToolError, match="Unexpected schema content format"):
            await patch_schema(
                schema_id=50,
                operation="add",
                node_id="new_field",
                parent_id="section1",
                node_data={"label": "New Field"},
            )

        mock_client._http_client.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_patch_schema_node_not_found(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test that updating a non-existent node returns error."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

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
        with pytest.raises(ToolError, match="not found"):
            await patch_schema(
                schema_id=50,
                operation="update",
                node_id="nonexistent_field",
                node_data={"label": "Updated Label"},
            )
