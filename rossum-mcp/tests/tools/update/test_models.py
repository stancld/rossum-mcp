"""Tests for schema update dataclass models."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_schema
from rossum_mcp.tools.models import SchemaDatapoint
from rossum_mcp.tools.update.handler import register_update_tools
from rossum_mcp.tools.update.models import SchemaNodeUpdate


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
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
class TestSchemaNodeUpdate:
    """Tests for SchemaNodeUpdate dataclass."""

    def test_schema_node_update_to_dict(self) -> None:
        """Test SchemaNodeUpdate only includes set fields."""
        update = SchemaNodeUpdate(label="Updated Label", score_threshold=0.9)
        result = update.to_dict()

        assert result == {"label": "Updated Label", "score_threshold": 0.9}
        assert "type" not in result
        assert "hidden" not in result

    def test_schema_node_update_with_matching(self) -> None:
        """Test SchemaNodeUpdate with lookup matching configuration."""
        matching = {
            "type": "master_data_hub",
            "configuration": {
                "dataset": "imported-abc123",
                "queries": [{"aggregate": [{"$match": {"Name": "$sender_name"}}]}],
                "variables": {"sender_name": {"__formula": "field.sender_name"}},
            },
        }
        update = SchemaNodeUpdate(
            matching=matching,
            enum_value_type="string",
        )
        result = update.to_dict()

        assert result["matching"]["type"] == "master_data_hub"
        assert result["matching"]["configuration"]["dataset"] == "imported-abc123"
        assert result["enum_value_type"] == "string"
        assert "label" not in result

    def test_schema_node_update_with_stretch(self) -> None:
        """Test SchemaNodeUpdate with stretch field."""
        update = SchemaNodeUpdate(label="Column", width=100, stretch=True)
        result = update.to_dict()

        assert result["label"] == "Column"
        assert result["width"] == 100
        assert result["stretch"] is True

    @pytest.mark.asyncio
    async def test_patch_schema_with_dataclass(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test patch_schema accepts dataclass node_data."""
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
        mock_client._http_client.update.return_value = {}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="add",
            node_id="vendor_name",
            parent_id="header_section",
            node_data=SchemaDatapoint(label="Vendor Name", type="string"),
        )

        assert result["status"] == "success"
        assert result["schema_id"] == 50
        assert result["node"]["label"] == "Vendor Name"
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        header_section = updated_content[0]
        assert len(header_section["children"]) == 1
        assert header_section["children"][0]["id"] == "vendor_name"
        assert header_section["children"][0]["label"] == "Vendor Name"

    @pytest.mark.asyncio
    async def test_patch_schema_update_with_dataclass(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test patch_schema update operation with SchemaNodeUpdate dataclass."""
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
            operation="update",
            node_id="invoice_number",
            node_data=SchemaNodeUpdate(label="Invoice #", score_threshold=0.95),
        )

        assert result["status"] == "success"
        assert result["schema_id"] == 50
        assert result["node"]["label"] == "Invoice #"
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        datapoint = updated_content[0]["children"][0]
        assert datapoint["label"] == "Invoice #"
        assert datapoint["score_threshold"] == 0.95
