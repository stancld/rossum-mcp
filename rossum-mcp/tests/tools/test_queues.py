"""Tests for rossum_mcp.tools.queues module."""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rossum_api import APIClientError
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.engine import Engine
from rossum_api.models.queue import Queue
from rossum_api.models.schema import Schema
from rossum_mcp.tools import base
from rossum_mcp.tools.queues import register_queue_tools

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def create_mock_queue(**kwargs) -> Queue:
    """Create a mock Queue dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/queues/1",
        "name": "Test Queue",
        "workspace": "https://api.test.rossum.ai/v1/workspaces/1",
        "connector": None,
        "schema": "https://api.test.rossum.ai/v1/schemas/1",
        "inbox": "https://api.test.rossum.ai/v1/inboxes/1",
        "hooks": [],
        "users": [],
        "use_confirmed_state": True,
        "default_score_threshold": 0.8,
        "locale": "en_GB",
        "training_enabled": True,
        "automation_enabled": True,
        "automation_level": "never",
        "generic_engine": None,
        "dedicated_engine": None,
        "engine": "https://api.test.rossum.ai/v1/engines/1",
        "counts": {},
        "metadata": {},
        "settings": {},
        "status": "active",
        "document_lifetime": None,
        "delete_after": None,
    }
    defaults.update(kwargs)
    return Queue(**defaults)


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


def create_mock_engine(**kwargs) -> Engine:
    """Create a mock Engine dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/engines/1",
        "name": "Test Engine",
        "type": "extractor",
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "learning_enabled": True,
        "training_queues": [],
        "description": "",
        "agenda_id": "test-agenda-id",
    }
    defaults.update(kwargs)
    return Engine(**defaults)


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
class TestGetQueue:
    """Tests for get_queue tool."""

    @pytest.mark.asyncio
    async def test_get_queue_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful queue retrieval."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=100, name="Production Queue")
        mock_client.retrieve_queue.return_value = mock_queue

        get_queue = mock_mcp._tools["get_queue"]
        result = await get_queue(queue_id=100)

        assert result.id == 100
        assert result.name == "Production Queue"
        assert result.schema == mock_queue.schema
        assert result.workspace == mock_queue.workspace
        mock_client.retrieve_queue.assert_called_once_with(100)


@pytest.mark.unit
class TestListQueues:
    """Tests for list_queues tool."""

    @pytest.mark.asyncio
    async def test_list_queues_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful queue listing."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queues = [
            create_mock_queue(id=1, name="Queue 1"),
            create_mock_queue(id=2, name="Queue 2"),
        ]

        async def mock_list_queues(**filters):
            for queue in mock_queues:
                yield queue

        mock_client.list_queues = mock_list_queues

        list_queues = mock_mcp._tools["list_queues"]
        result = await list_queues()

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2

    @pytest.mark.asyncio
    async def test_list_queues_with_workspace_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue listing with workspace filter."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queues = [create_mock_queue(id=1, name="Queue 1")]
        filters_received = {}

        async def mock_list_queues(**filters):
            nonlocal filters_received
            filters_received = filters
            for queue in mock_queues:
                yield queue

        mock_client.list_queues = mock_list_queues

        list_queues = mock_mcp._tools["list_queues"]
        result = await list_queues(workspace_id=5)

        assert len(result) == 1
        assert filters_received["workspace"] == 5

    @pytest.mark.asyncio
    async def test_list_queues_with_name_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue listing with name filter."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queues = [create_mock_queue(id=1, name="Test Queue")]
        filters_received = {}

        async def mock_list_queues(**filters):
            nonlocal filters_received
            filters_received = filters
            for queue in mock_queues:
                yield queue

        mock_client.list_queues = mock_list_queues

        list_queues = mock_mcp._tools["list_queues"]
        result = await list_queues(name="Test Queue")

        assert len(result) == 1
        assert filters_received["name"] == "Test Queue"

    @pytest.mark.asyncio
    async def test_list_queues_with_all_filters(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue listing with all filters."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queues = [create_mock_queue(id=1, name="Test Queue")]
        filters_received = {}

        async def mock_list_queues(**filters):
            nonlocal filters_received
            filters_received = filters
            for queue in mock_queues:
                yield queue

        mock_client.list_queues = mock_list_queues

        list_queues = mock_mcp._tools["list_queues"]
        result = await list_queues(workspace_id=3, name="Test Queue")

        assert len(result) == 1
        assert filters_received["workspace"] == 3
        assert filters_received["name"] == "Test Queue"

    @pytest.mark.asyncio
    async def test_list_queues_empty_result(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue listing with no results."""
        register_queue_tools(mock_mcp, mock_client)

        async def mock_list_queues(**filters):
            return
            yield

        mock_client.list_queues = mock_list_queues

        list_queues = mock_mcp._tools["list_queues"]
        result = await list_queues()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_queues_truncates_verbose_settings(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test that verbose settings fields are truncated in list response."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(
            id=1,
            name="Queue 1",
            settings={
                "columns": [{"schema_id": "doc_id"}],
                "accepted_mime_types": ["image/*", "application/pdf", "application/zip"],
                "annotation_list_table": {"columns": [{"visible": True, "column_type": "meta"}]},
                "ui_upload_enabled": True,
            },
        )

        async def mock_list_queues(**filters):
            yield mock_queue

        mock_client.list_queues = mock_list_queues

        list_queues = mock_mcp._tools["list_queues"]
        result = await list_queues()

        assert len(result) == 1
        assert result[0].settings["accepted_mime_types"] == "<omitted>"
        assert result[0].settings["annotation_list_table"] == "<omitted>"
        assert result[0].settings["columns"] == [{"schema_id": "doc_id"}]
        assert result[0].settings["ui_upload_enabled"] is True

    @pytest.mark.asyncio
    async def test_list_queues_handles_empty_settings(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test that empty settings are handled correctly."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=1, name="Queue 1", settings={})

        async def mock_list_queues(**filters):
            yield mock_queue

        mock_client.list_queues = mock_list_queues

        list_queues = mock_mcp._tools["list_queues"]
        result = await list_queues()

        assert len(result) == 1
        assert result[0].settings == {}


@pytest.mark.unit
class TestGetQueueSchema:
    """Tests for get_queue_schema tool."""

    @pytest.mark.asyncio
    async def test_get_queue_schema_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful queue schema retrieval."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=100, schema="https://api.test.rossum.ai/v1/schemas/50")
        mock_schema = create_mock_schema(id=50, name="Invoice Schema")

        mock_client.retrieve_queue.return_value = mock_queue
        mock_client.retrieve_schema.return_value = mock_schema

        get_queue_schema = mock_mcp._tools["get_queue_schema"]
        result = await get_queue_schema(queue_id=100)

        assert result.id == 50
        assert result.name == "Invoice Schema"
        mock_client.retrieve_queue.assert_called_once_with(100)
        mock_client.retrieve_schema.assert_called_once_with(50)

    @pytest.mark.asyncio
    async def test_get_queue_schema_with_trailing_slash(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue schema retrieval handles trailing slash in URL."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=100, schema="https://api.test.rossum.ai/v1/schemas/50/")
        mock_schema = create_mock_schema(id=50)

        mock_client.retrieve_queue.return_value = mock_queue
        mock_client.retrieve_schema.return_value = mock_schema

        get_queue_schema = mock_mcp._tools["get_queue_schema"]
        await get_queue_schema(queue_id=100)

        mock_client.retrieve_schema.assert_called_once_with(50)


@pytest.mark.unit
class TestGetQueueEngine:
    """Tests for get_queue_engine tool."""

    @pytest.mark.asyncio
    async def test_get_queue_engine_from_engine_field(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue engine retrieval from engine field."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(
            id=100,
            engine="https://api.test.rossum.ai/v1/engines/15",
            dedicated_engine=None,
            generic_engine=None,
        )
        mock_engine = create_mock_engine(id=15, name="Custom Engine")

        mock_client.retrieve_queue.return_value = mock_queue
        mock_client.retrieve_engine.return_value = mock_engine

        get_queue_engine = mock_mcp._tools["get_queue_engine"]
        result = await get_queue_engine(queue_id=100)

        assert result.id == 15
        assert result.name == "Custom Engine"
        mock_client.retrieve_engine.assert_called_once_with(15)

    @pytest.mark.asyncio
    async def test_get_queue_engine_from_dedicated_engine(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue engine retrieval prefers dedicated_engine."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(
            id=100,
            engine="https://api.test.rossum.ai/v1/engines/10",
            dedicated_engine="https://api.test.rossum.ai/v1/engines/20",
            generic_engine=None,
        )
        mock_engine = create_mock_engine(id=20, name="Dedicated Engine")

        mock_client.retrieve_queue.return_value = mock_queue
        mock_client.retrieve_engine.return_value = mock_engine

        get_queue_engine = mock_mcp._tools["get_queue_engine"]
        result = await get_queue_engine(queue_id=100)

        assert result.id == 20
        mock_client.retrieve_engine.assert_called_once_with(20)

    @pytest.mark.asyncio
    async def test_get_queue_engine_no_engine_assigned(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue engine retrieval when no engine is assigned."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(
            id=100,
            engine=None,
            dedicated_engine=None,
            generic_engine=None,
        )
        mock_client.retrieve_queue.return_value = mock_queue

        get_queue_engine = mock_mcp._tools["get_queue_engine"]
        result = await get_queue_engine(queue_id=100)

        assert result["message"] == "No engine assigned to this queue"
        mock_client.retrieve_engine.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_queue_engine_engine_not_found(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue engine retrieval when engine returns 404."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(
            id=100,
            engine="https://api.test.rossum.ai/v1/engines/999",
            dedicated_engine=None,
            generic_engine=None,
        )
        mock_client.retrieve_queue.return_value = mock_queue
        mock_client.retrieve_engine.side_effect = APIClientError(
            method="GET",
            url="https://api.test.rossum.ai/v1/engines/999",
            status_code=404,
            error=Exception("Not found"),
        )

        get_queue_engine = mock_mcp._tools["get_queue_engine"]
        result = await get_queue_engine(queue_id=100)

        assert "Engine not found" in result["message"]
        assert "engines/999" in result["message"]

    @pytest.mark.asyncio
    async def test_get_queue_engine_from_generic_engine(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue engine retrieval from generic_engine field."""
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(
            id=100,
            engine="https://api.test.rossum.ai/v1/engines/10",
            dedicated_engine=None,
            generic_engine="https://api.test.rossum.ai/v1/engines/30",
        )
        mock_engine = create_mock_engine(id=30, name="Generic Engine")

        mock_client.retrieve_queue.return_value = mock_queue
        mock_client.retrieve_engine.return_value = mock_engine

        get_queue_engine = mock_mcp._tools["get_queue_engine"]
        result = await get_queue_engine(queue_id=100)

        assert result.id == 30
        assert result.name == "Generic Engine"
        mock_client.retrieve_engine.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_get_queue_engine_dict_engine(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue engine retrieval when engine_url is a dict (uses deserialize_default)."""
        register_queue_tools(mock_mcp, mock_client)

        engine_dict = {
            "id": 42,
            "url": "https://api.test.rossum.ai/v1/engines/42",
            "name": "Inline Engine",
            "type": "extractor",
        }
        mock_queue = create_mock_queue(
            id=100,
            engine=engine_dict,
            dedicated_engine=None,
            generic_engine=None,
        )
        mock_engine = create_mock_engine(id=42, name="Inline Engine")

        mock_client.retrieve_queue.return_value = mock_queue

        with patch("rossum_mcp.tools.queues.deserialize_default", return_value=mock_engine) as mock_deserialize:
            get_queue_engine = mock_mcp._tools["get_queue_engine"]
            result = await get_queue_engine(queue_id=100)

            mock_deserialize.assert_called_once_with(Resource.Engine, engine_dict)
            assert result.id == 42
            assert result.name == "Inline Engine"
            mock_client.retrieve_engine.assert_not_called()


@pytest.mark.unit
class TestCreateQueue:
    """Tests for create_queue tool."""

    @pytest.mark.asyncio
    async def test_create_queue_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful queue creation."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(
            id=200,
            name="New Queue",
            workspace="https://api.test.rossum.ai/v1/workspaces/1",
            schema="https://api.test.rossum.ai/v1/schemas/10",
        )
        mock_client.create_new_queue.return_value = mock_queue

        create_queue = mock_mcp._tools["create_queue"]
        result = await create_queue(
            name="New Queue",
            workspace_id=1,
            schema_id=10,
        )

        assert result.id == 200
        assert result.name == "New Queue"
        mock_client.create_new_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_queue_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_queue is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        create_queue = mock_mcp._tools["create_queue"]
        result = await create_queue(name="New Queue", workspace_id=1, schema_id=10)

        assert result["error"] == "create_queue is not available in read-only mode"
        mock_client.create_new_queue.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_queue_with_inbox_id(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_queue with inbox_id parameter."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=200, name="New Queue")
        mock_client.create_new_queue.return_value = mock_queue

        create_queue = mock_mcp._tools["create_queue"]
        await create_queue(name="New Queue", workspace_id=1, schema_id=10, inbox_id=5)

        call_args = mock_client.create_new_queue.call_args[0][0]
        assert call_args["inbox"] == "https://api.test.rossum.ai/v1/inboxes/5"

    @pytest.mark.asyncio
    async def test_create_queue_with_connector_id(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_queue with connector_id parameter."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=200, name="New Queue")
        mock_client.create_new_queue.return_value = mock_queue

        create_queue = mock_mcp._tools["create_queue"]
        await create_queue(name="New Queue", workspace_id=1, schema_id=10, connector_id=7)

        call_args = mock_client.create_new_queue.call_args[0][0]
        assert call_args["connector"] == "https://api.test.rossum.ai/v1/connectors/7"

    @pytest.mark.asyncio
    async def test_create_queue_with_splitting_screen_flag_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_queue with splitting_screen_feature_flag when env vars are set."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("SPLITTING_SCREEN_FLAG_NAME", "enable_splitting")
        monkeypatch.setenv("SPLITTING_SCREEN_FLAG_VALUE", "true")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=200, name="New Queue")
        mock_client.create_new_queue.return_value = mock_queue

        create_queue = mock_mcp._tools["create_queue"]
        await create_queue(name="New Queue", workspace_id=1, schema_id=10, splitting_screen_feature_flag=True)

        call_args = mock_client.create_new_queue.call_args[0][0]
        assert call_args["settings"] == {"enable_splitting": "true"}

    @pytest.mark.asyncio
    async def test_create_queue_with_splitting_screen_flag_missing_env(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test create_queue with splitting_screen_feature_flag when env vars are missing."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.delenv("SPLITTING_SCREEN_FLAG_NAME", raising=False)
        monkeypatch.delenv("SPLITTING_SCREEN_FLAG_VALUE", raising=False)
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=200, name="New Queue")
        mock_client.create_new_queue.return_value = mock_queue

        create_queue = mock_mcp._tools["create_queue"]
        with caplog.at_level(logging.ERROR):
            await create_queue(name="New Queue", workspace_id=1, schema_id=10, splitting_screen_feature_flag=True)

        call_args = mock_client.create_new_queue.call_args[0][0]
        assert "settings" not in call_args
        assert "Splitting screen failed to update" in caplog.text


@pytest.mark.unit
class TestUpdateQueue:
    """Tests for update_queue tool."""

    @pytest.mark.asyncio
    async def test_update_queue_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful queue update."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=100, name="Updated Queue")
        mock_client._http_client.update.return_value = {"id": 100, "name": "Updated Queue"}
        mock_client._deserializer.return_value = mock_queue

        update_queue = mock_mcp._tools["update_queue"]
        result = await update_queue(queue_id=100, queue_data={"name": "Updated Queue"})

        assert result.id == 100
        assert result.name == "Updated Queue"
        mock_client._http_client.update.assert_called_once_with(Resource.Queue, 100, {"name": "Updated Queue"})

    @pytest.mark.asyncio
    async def test_update_queue_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test update_queue is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        update_queue = mock_mcp._tools["update_queue"]
        result = await update_queue(queue_id=100, queue_data={"name": "Updated"})

        assert result["error"] == "update_queue is not available in read-only mode"
        mock_client._http_client.update.assert_not_called()


@pytest.mark.unit
class TestGetQueueTemplateNames:
    """Tests for get_queue_template_names tool."""

    @pytest.mark.asyncio
    async def test_get_queue_template_names_returns_list(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test that get_queue_template_names returns the template list."""
        register_queue_tools(mock_mcp, mock_client)

        get_queue_template_names = mock_mcp._tools["get_queue_template_names"]
        result = await get_queue_template_names()

        assert isinstance(result, list)
        assert "EU Demo Template" in result
        assert "US Demo Template" in result
        assert "Empty Organization Template" in result
        assert len(result) == 20


@pytest.mark.unit
class TestCreateQueueFromTemplate:
    """Tests for create_queue_from_template tool."""

    @pytest.mark.asyncio
    async def test_create_queue_from_template_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful queue creation from template."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=300, name="New Template Queue")
        mock_client._http_client.request_json.return_value = {"id": 300, "name": "New Template Queue"}
        mock_client._deserializer.return_value = mock_queue

        create_queue_from_template = mock_mcp._tools["create_queue_from_template"]
        result = await create_queue_from_template(
            name="New Template Queue",
            template_name="EU Demo Template",
            workspace_id=1,
        )

        assert result.id == 300
        assert result.name == "New Template Queue"
        mock_client._http_client.request_json.assert_called_once()
        call_kwargs = mock_client._http_client.request_json.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["url"] == "queues/from_template"
        assert call_kwargs["json"]["name"] == "New Template Queue"
        assert call_kwargs["json"]["template_name"] == "EU Demo Template"
        assert call_kwargs["json"]["workspace"] == "https://api.test.rossum.ai/v1/workspaces/1"
        assert call_kwargs["json"]["include_documents"] is False

    @pytest.mark.asyncio
    async def test_create_queue_from_template_with_engine(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test queue creation from template with custom engine."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=300, name="New Template Queue")
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer.return_value = mock_queue

        create_queue_from_template = mock_mcp._tools["create_queue_from_template"]
        await create_queue_from_template(
            name="New Template Queue",
            template_name="US Demo Template",
            workspace_id=1,
            engine_id=42,
        )

        call_kwargs = mock_client._http_client.request_json.call_args[1]
        assert call_kwargs["json"]["engine"] == "https://api.test.rossum.ai/v1/engines/42"

    @pytest.mark.asyncio
    async def test_create_queue_from_template_invalid_template(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test queue creation from template with invalid template name."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        create_queue_from_template = mock_mcp._tools["create_queue_from_template"]
        result = await create_queue_from_template(
            name="New Queue",
            template_name="Invalid Template",
            workspace_id=1,
        )

        assert "error" in result
        assert "Invalid template_name" in result["error"]
        assert "available_templates" in result
        mock_client._http_client.request_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_queue_from_template_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_queue_from_template is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        create_queue_from_template = mock_mcp._tools["create_queue_from_template"]
        result = await create_queue_from_template(
            name="New Queue",
            template_name="EU Demo Template",
            workspace_id=1,
        )

        assert result["error"] == "create_queue_from_template is not available in read-only mode"
        mock_client._http_client.request_json.assert_not_called()


@pytest.mark.unit
class TestDeleteQueue:
    """Tests for delete_queue tool."""

    @pytest.mark.asyncio
    async def test_delete_queue_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful queue deletion."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_client.delete_queue.return_value = None

        delete_queue = mock_mcp._tools["delete_queue"]
        result = await delete_queue(queue_id=100)

        assert "scheduled for deletion" in result["message"]
        assert "100" in result["message"]
        mock_client.delete_queue.assert_called_once_with(100)

    @pytest.mark.asyncio
    async def test_delete_queue_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test delete_queue is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        delete_queue = mock_mcp._tools["delete_queue"]
        result = await delete_queue(queue_id=100)

        assert result["error"] == "delete_queue is not available in read-only mode"
        mock_client.delete_queue.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_queue_not_found(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test delete_queue raises error when queue doesn't exist."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_client.delete_queue.side_effect = APIClientError(
            method="DELETE",
            url="https://api.test.rossum.ai/v1/queues/99999",
            status_code=404,
            error=Exception("Not Found"),
        )

        delete_queue = mock_mcp._tools["delete_queue"]
        with pytest.raises(APIClientError) as exc_info:
            await delete_queue(queue_id=99999)

        assert exc_info.value.status_code == 404
