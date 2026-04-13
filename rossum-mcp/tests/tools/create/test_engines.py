"""Tests for rossum_mcp.tools.create.engines module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_engine, create_mock_engine_field
from fastmcp.exceptions import ToolError
from rossum_mcp.tools.create import register_create_tools


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
class TestCreateEngine:
    """Tests for create_engine tool."""

    @pytest.mark.asyncio
    async def test_create_engine_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful engine creation."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_engine = create_mock_engine(id=200, name="New Engine", type="extractor")
        mock_client._http_client.create.return_value = {"id": 200}
        mock_client._deserializer = Mock(return_value=mock_engine)

        create_engine = mock_mcp._tools["create_engine"]
        result = await create_engine(name="New Engine", organization_id=1, engine_type="extractor")

        assert result.id == 200
        assert result.name == "New Engine"

    @pytest.mark.asyncio
    async def test_create_engine_invalid_type(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test create_engine with invalid engine type."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        create_engine = mock_mcp._tools["create_engine"]

        with pytest.raises(ToolError, match="Invalid engine_type"):
            await create_engine(name="New Engine", organization_id=1, engine_type="invalid")


@pytest.mark.unit
class TestCreateEngineField:
    """Tests for create_engine_field tool."""

    @pytest.mark.asyncio
    async def test_create_engine_field_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful engine field creation."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_field = create_mock_engine_field(id=500, label="Invoice Number")
        mock_client._http_client.create.return_value = {"id": 500}
        mock_client._deserializer = Mock(return_value=mock_field)

        create_engine_field = mock_mcp._tools["create_engine_field"]
        result = await create_engine_field(
            engine_id=123,
            name="invoice_number",
            label="Invoice Number",
            field_type="string",
            schema_ids=[1, 2],
        )

        assert result.id == 500
        assert result.label == "Invoice Number"

    @pytest.mark.parametrize(
        ("multiline_kwargs", "expected_string"),
        [
            ({"multiline": True}, "true"),
            ({}, "false"),
        ],
        ids=["multiline_true", "multiline_default_false"],
    )
    @pytest.mark.asyncio
    async def test_create_engine_field_multiline_sent_as_string(
        self, mock_mcp: Mock, mock_client: AsyncMock, multiline_kwargs: dict, expected_string: str
    ) -> None:
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_field = create_mock_engine_field(id=501, label="Notes")
        mock_client._http_client.create.return_value = {"id": 501}
        mock_client._deserializer = Mock(return_value=mock_field)

        create_engine_field = mock_mcp._tools["create_engine_field"]
        await create_engine_field(
            engine_id=123,
            name="notes",
            label="Notes",
            field_type="string",
            schema_ids=[1],
            **multiline_kwargs,
        )

        create_call = mock_client._http_client.create.call_args
        assert create_call[0][1]["multiline"] == expected_string

    @pytest.mark.parametrize(
        ("extra_kwargs", "match"),
        [
            ({"schema_ids": [], "field_type": "string"}, "schema_ids cannot be empty"),
            ({"schema_ids": [1], "field_type": "invalid"}, "Invalid field_type"),
        ],
        ids=["empty_schemas", "invalid_type"],
    )
    @pytest.mark.asyncio
    async def test_create_engine_field_validation_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, extra_kwargs: dict, match: str
    ) -> None:
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        create_engine_field = mock_mcp._tools["create_engine_field"]

        with pytest.raises(ToolError, match=match):
            await create_engine_field(
                engine_id=123,
                name="field",
                label="Field",
                **extra_kwargs,
            )

    @pytest.mark.asyncio
    async def test_create_engine_field_with_optional_params(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test engine field creation with subtype and pre_trained_field_id."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_field = create_mock_engine_field(id=500, subtype="iban", pre_trained_field_id="iban_field")
        mock_client._http_client.create.return_value = {"id": 500}
        mock_client._deserializer = Mock(return_value=mock_field)

        create_engine_field = mock_mcp._tools["create_engine_field"]
        result = await create_engine_field(
            engine_id=123,
            name="bank_account",
            label="Bank Account",
            field_type="string",
            schema_ids=[1],
            subtype="iban",
            pre_trained_field_id="iban_field",
        )

        assert result.id == 500
        create_call = mock_client._http_client.create.call_args
        assert create_call[0][1]["subtype"] == "iban"
        assert create_call[0][1]["pre_trained_field_id"] == "iban_field"
