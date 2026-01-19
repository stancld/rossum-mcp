"""Tests for rossum_mcp.tools.engines module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_engine, create_mock_engine_field
from rossum_api.domain_logic.resources import Resource
from rossum_mcp.tools import base
from rossum_mcp.tools.engines import register_engine_tools

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock()
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
class TestGetEngine:
    """Tests for get_engine tool."""

    @pytest.mark.asyncio
    async def test_get_engine_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful engine retrieval."""
        register_engine_tools(mock_mcp, mock_client)

        mock_engine = create_mock_engine(id=123, name="Custom Engine", type="extractor")
        mock_client.retrieve_engine.return_value = mock_engine

        get_engine = mock_mcp._tools["get_engine"]
        result = await get_engine(engine_id=123)

        assert result.id == 123
        assert result.name == "Custom Engine"
        assert result.type == "extractor"
        mock_client.retrieve_engine.assert_called_once_with(123)


@pytest.mark.unit
class TestListEngines:
    """Tests for list_engines tool."""

    @pytest.mark.asyncio
    async def test_list_engines_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful engines listing."""
        register_engine_tools(mock_mcp, mock_client)

        mock_engine1 = create_mock_engine(id=1, name="Engine 1")
        mock_engine2 = create_mock_engine(id=2, name="Engine 2")

        async def async_iter():
            for item in [mock_engine1, mock_engine2]:
                yield item

        mock_client.list_engines = Mock(side_effect=lambda **kwargs: async_iter())

        list_engines = mock_mcp._tools["list_engines"]
        result = await list_engines()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_engines_with_filters(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test engines listing with filters."""
        register_engine_tools(mock_mcp, mock_client)

        mock_engine = create_mock_engine(id=1, type="extractor")

        async def async_iter():
            yield mock_engine

        mock_client.list_engines = Mock(side_effect=lambda **kwargs: async_iter())

        list_engines = mock_mcp._tools["list_engines"]
        result = await list_engines(engine_type="extractor")

        assert len(result) == 1
        mock_client.list_engines.assert_called_once_with(type="extractor")

    @pytest.mark.asyncio
    async def test_list_engines_with_id_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test engines listing with id filter."""
        register_engine_tools(mock_mcp, mock_client)

        mock_engine = create_mock_engine(id=42, type="extractor")

        async def async_iter():
            yield mock_engine

        mock_client.list_engines = Mock(side_effect=lambda **kwargs: async_iter())

        list_engines = mock_mcp._tools["list_engines"]
        result = await list_engines(id=42)

        assert len(result) == 1
        mock_client.list_engines.assert_called_once_with(id=42)

    @pytest.mark.asyncio
    async def test_list_engines_with_agenda_id_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test engines listing with agenda_id filter."""
        register_engine_tools(mock_mcp, mock_client)

        mock_engine = create_mock_engine(id=1, agenda_id="my-agenda")

        async def async_iter():
            yield mock_engine

        mock_client.list_engines = Mock(side_effect=lambda **kwargs: async_iter())

        list_engines = mock_mcp._tools["list_engines"]
        result = await list_engines(agenda_id="my-agenda")

        assert len(result) == 1
        mock_client.list_engines.assert_called_once_with(agenda_id="my-agenda")


@pytest.mark.unit
class TestUpdateEngine:
    """Tests for update_engine tool."""

    @pytest.mark.asyncio
    async def test_update_engine_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful engine update."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_engine_tools(mock_mcp, mock_client)

        mock_engine = create_mock_engine(id=123, name="Updated Engine")
        mock_client._http_client.update.return_value = {"id": 123}
        mock_client._deserializer.return_value = mock_engine

        update_engine = mock_mcp._tools["update_engine"]
        result = await update_engine(engine_id=123, engine_data={"name": "Updated Engine"})

        assert result.id == 123
        assert result.name == "Updated Engine"
        mock_client._http_client.update.assert_called_once_with(Resource.Engine, 123, {"name": "Updated Engine"})

    @pytest.mark.asyncio
    async def test_update_engine_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test update_engine is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        register_engine_tools(mock_mcp, mock_client)

        update_engine = mock_mcp._tools["update_engine"]
        result = await update_engine(engine_id=123, engine_data={"name": "Updated"})

        assert result["error"] == "update_engine is not available in read-only mode"


@pytest.mark.unit
class TestCreateEngine:
    """Tests for create_engine tool."""

    @pytest.mark.asyncio
    async def test_create_engine_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful engine creation."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_engine_tools(mock_mcp, mock_client)

        mock_engine = create_mock_engine(id=200, name="New Engine", type="extractor")
        mock_client._http_client.create.return_value = {"id": 200}
        mock_client._deserializer.return_value = mock_engine

        create_engine = mock_mcp._tools["create_engine"]
        result = await create_engine(name="New Engine", organization_id=1, engine_type="extractor")

        assert result.id == 200
        assert result.name == "New Engine"

    @pytest.mark.asyncio
    async def test_create_engine_invalid_type(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_engine with invalid engine type."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_engine_tools(mock_mcp, mock_client)

        create_engine = mock_mcp._tools["create_engine"]

        with pytest.raises(ValueError) as exc_info:
            await create_engine(name="New Engine", organization_id=1, engine_type="invalid")

        assert "Invalid engine_type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_engine_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_engine is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        register_engine_tools(mock_mcp, mock_client)

        create_engine = mock_mcp._tools["create_engine"]
        result = await create_engine(name="New Engine", organization_id=1, engine_type="extractor")

        assert result["error"] == "create_engine is not available in read-only mode"


@pytest.mark.unit
class TestCreateEngineField:
    """Tests for create_engine_field tool."""

    @pytest.mark.asyncio
    async def test_create_engine_field_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful engine field creation."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_engine_tools(mock_mcp, mock_client)

        mock_field = create_mock_engine_field(id=500, label="Invoice Number")
        mock_client._http_client.create.return_value = {"id": 500}
        mock_client._deserializer.return_value = mock_field

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

    @pytest.mark.asyncio
    async def test_create_engine_field_empty_schemas(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_engine_field fails with empty schema_ids."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_engine_tools(mock_mcp, mock_client)

        create_engine_field = mock_mcp._tools["create_engine_field"]

        with pytest.raises(ValueError) as exc_info:
            await create_engine_field(
                engine_id=123,
                name="field",
                label="Field",
                field_type="string",
                schema_ids=[],
            )

        assert "schema_ids cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_engine_field_invalid_type(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_engine_field fails with invalid field type."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_engine_tools(mock_mcp, mock_client)

        create_engine_field = mock_mcp._tools["create_engine_field"]

        with pytest.raises(ValueError) as exc_info:
            await create_engine_field(
                engine_id=123,
                name="field",
                label="Field",
                field_type="invalid",
                schema_ids=[1],
            )

        assert "Invalid field_type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_engine_field_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_engine_field is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        register_engine_tools(mock_mcp, mock_client)

        create_engine_field = mock_mcp._tools["create_engine_field"]
        result = await create_engine_field(
            engine_id=123,
            name="field",
            label="Field",
            field_type="string",
            schema_ids=[1],
        )

        assert result["error"] == "create_engine_field is not available in read-only mode"

    @pytest.mark.asyncio
    async def test_create_engine_field_with_optional_params(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test engine field creation with subtype and pre_trained_field_id."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_engine_tools(mock_mcp, mock_client)

        mock_field = create_mock_engine_field(id=500, subtype="iban", pre_trained_field_id="iban_field")
        mock_client._http_client.create.return_value = {"id": 500}
        mock_client._deserializer.return_value = mock_field

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


@pytest.mark.unit
class TestGetEngineFields:
    """Tests for get_engine_fields tool."""

    @pytest.mark.asyncio
    async def test_get_engine_fields_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful engine fields retrieval."""
        register_engine_tools(mock_mcp, mock_client)

        mock_field1 = create_mock_engine_field(id=1, label="Field 1")
        mock_field2 = create_mock_engine_field(id=2, label="Field 2")

        async def async_iter():
            for item in [mock_field1, mock_field2]:
                yield item

        mock_client.retrieve_engine_fields = Mock(side_effect=lambda **kwargs: async_iter())

        get_engine_fields = mock_mcp._tools["get_engine_fields"]
        result = await get_engine_fields(engine_id=123)

        assert len(result) == 2
        mock_client.retrieve_engine_fields.assert_called_once_with(engine_id=123)

    @pytest.mark.asyncio
    async def test_get_engine_fields_all(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test retrieving all engine fields without filter."""
        register_engine_tools(mock_mcp, mock_client)

        async def async_iter():
            return
            yield

        mock_client.retrieve_engine_fields = Mock(side_effect=lambda **kwargs: async_iter())

        get_engine_fields = mock_mcp._tools["get_engine_fields"]
        result = await get_engine_fields()

        assert len(result) == 0
        mock_client.retrieve_engine_fields.assert_called_once_with(engine_id=None)
