"""Tests for rossum_mcp.tools.queues module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api import APIClientError
from rossum_api.models.engine import Engine
from rossum_api.models.queue import Queue
from rossum_api.models.schema import Schema

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
        from rossum_mcp.tools.queues import register_queue_tools

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
class TestGetQueueSchema:
    """Tests for get_queue_schema tool."""

    @pytest.mark.asyncio
    async def test_get_queue_schema_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful queue schema retrieval."""
        from rossum_mcp.tools.queues import register_queue_tools

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
        from rossum_mcp.tools.queues import register_queue_tools

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
        from rossum_mcp.tools.queues import register_queue_tools

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
        from rossum_mcp.tools.queues import register_queue_tools

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
        from rossum_mcp.tools.queues import register_queue_tools

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
        from rossum_mcp.tools.queues import register_queue_tools

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

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.queues import register_queue_tools

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

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.queues import register_queue_tools

        register_queue_tools(mock_mcp, mock_client)

        create_queue = mock_mcp._tools["create_queue"]
        result = await create_queue(name="New Queue", workspace_id=1, schema_id=10)

        assert result["error"] == "create_queue is not available in read-only mode"
        mock_client.create_new_queue.assert_not_called()


@pytest.mark.unit
class TestUpdateQueue:
    """Tests for update_queue tool."""

    @pytest.mark.asyncio
    async def test_update_queue_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful queue update."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_api.domain_logic.resources import Resource
        from rossum_mcp.tools.queues import register_queue_tools

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

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.queues import register_queue_tools

        register_queue_tools(mock_mcp, mock_client)

        update_queue = mock_mcp._tools["update_queue"]
        result = await update_queue(queue_id=100, queue_data={"name": "Updated"})

        assert result["error"] == "update_queue is not available in read-only mode"
        mock_client._http_client.update.assert_not_called()
