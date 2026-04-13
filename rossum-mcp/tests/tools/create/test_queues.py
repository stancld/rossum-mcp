"""Tests for rossum_mcp.tools.create.queues module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from fastmcp.exceptions import ToolError
from rossum_api.models.engine import Engine
from rossum_api.models.queue import Queue
from rossum_api.models.schema import Schema
from rossum_mcp.tools.base import get_queue_engine_url
from rossum_mcp.tools.create import register_create_tools
from rossum_mcp.tools.create.queues import _create_queue_from_template
from rossum_mcp.tools.resource_tracking import TRACKED_RESOURCES_KEY


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
class TestCreateQueueFromTemplate:
    """Tests for create_queue_from_template tool."""

    @pytest.mark.asyncio
    async def test_create_queue_from_template_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful queue creation from template."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_queue = create_mock_queue(id=300, name="New Template Queue")
        mock_client._http_client.request_json.return_value = {"id": 300, "name": "New Template Queue"}
        mock_client._deserializer = Mock(return_value=mock_queue)

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
    async def test_create_queue_from_template_with_engine(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue creation from template with custom engine."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_queue = create_mock_queue(id=300, name="New Template Queue")
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)

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
    async def test_create_queue_from_template_invalid_template(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test queue creation from template with invalid template name."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        create_queue_from_template = mock_mcp._tools["create_queue_from_template"]
        with pytest.raises(ToolError, match="Invalid template_name") as exc_info:
            await create_queue_from_template(
                name="New Queue",
                template_name="Invalid Template",
                workspace_id=1,
            )

        assert "Available templates" in str(exc_info.value)
        mock_client._http_client.request_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_tracks_schema_and_engine(self, mock_client: AsyncMock) -> None:
        """Test that _create_queue_from_template tracks side-effect schema and engine."""
        mock_queue = create_mock_queue(
            id=300,
            name="Template Queue",
            schema="https://api.test.rossum.ai/v1/schemas/50",
            engine="https://api.test.rossum.ai/v1/engines/60",
        )
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)
        mock_client.retrieve_schema.return_value = create_mock_schema(id=50, name="Template Schema")
        mock_client.retrieve_engine.return_value = create_mock_engine(id=60, name="Template Engine")

        result = await _create_queue_from_template(
            mock_client, "https://api.test.rossum.ai/v1", "Template Queue", "EU Demo Template", workspace_id=1
        )

        assert isinstance(result, dict)
        assert result["id"] == 300
        tracked = result[TRACKED_RESOURCES_KEY]
        assert len(tracked) == 2
        assert tracked[0]["entity_type"] == "schema"
        assert tracked[0]["entity_id"] == "50"
        assert tracked[0]["data"]["name"] == "Template Schema"
        assert tracked[1]["entity_type"] == "engine"
        assert tracked[1]["entity_id"] == "60"
        assert tracked[1]["data"]["name"] == "Template Engine"

    @pytest.mark.asyncio
    async def test_tracks_engine_even_when_engine_id_provided(self, mock_client: AsyncMock) -> None:
        """Test that engine is tracked even when engine_id is explicitly provided (pre-existing engine)."""
        mock_queue = create_mock_queue(
            id=300,
            schema="https://api.test.rossum.ai/v1/schemas/50",
            engine="https://api.test.rossum.ai/v1/engines/42",
        )
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)
        mock_client.retrieve_schema.return_value = create_mock_schema(id=50)
        mock_client.retrieve_engine.return_value = create_mock_engine(id=42, name="Existing Engine")

        result = await _create_queue_from_template(
            mock_client,
            "https://api.test.rossum.ai/v1",
            "Template Queue",
            "EU Demo Template",
            workspace_id=1,
            engine_id=42,
        )

        assert isinstance(result, dict)
        tracked = result[TRACKED_RESOURCES_KEY]
        engine_tracked = [t for t in tracked if t["entity_type"] == "engine"]
        assert len(engine_tracked) == 1
        assert engine_tracked[0]["entity_id"] == "42"

    @pytest.mark.asyncio
    async def test_schema_fetch_failure_is_logged_and_skipped(self, mock_client: AsyncMock) -> None:
        """Test that schema fetch failure doesn't break queue creation."""
        mock_queue = create_mock_queue(
            id=300,
            schema="https://api.test.rossum.ai/v1/schemas/50",
            engine="https://api.test.rossum.ai/v1/engines/60",
        )
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)
        mock_client.retrieve_schema.side_effect = Exception("Schema not found")
        mock_client.retrieve_engine.return_value = create_mock_engine(id=60, name="Template Engine")

        result = await _create_queue_from_template(
            mock_client, "https://api.test.rossum.ai/v1", "Queue", "EU Demo Template", workspace_id=1
        )

        assert isinstance(result, dict)
        tracked = result[TRACKED_RESOURCES_KEY]
        assert len(tracked) == 1
        assert tracked[0]["entity_type"] == "engine"

    @pytest.mark.asyncio
    async def test_engine_fetch_failure_is_logged_and_skipped(self, mock_client: AsyncMock) -> None:
        """Test that engine fetch failure doesn't break queue creation."""
        mock_queue = create_mock_queue(
            id=300,
            schema="https://api.test.rossum.ai/v1/schemas/50",
            engine="https://api.test.rossum.ai/v1/engines/60",
        )
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)
        mock_client.retrieve_schema.return_value = create_mock_schema(id=50, name="Template Schema")
        mock_client.retrieve_engine.side_effect = Exception("Engine not found")

        result = await _create_queue_from_template(
            mock_client, "https://api.test.rossum.ai/v1", "Queue", "EU Demo Template", workspace_id=1
        )

        assert isinstance(result, dict)
        tracked = result[TRACKED_RESOURCES_KEY]
        assert len(tracked) == 1
        assert tracked[0]["entity_type"] == "schema"

    @pytest.mark.asyncio
    async def test_both_fetches_fail_returns_queue_without_tracked(self, mock_client: AsyncMock) -> None:
        """When both schema and engine fetch fail, result has empty tracked list."""
        mock_queue = create_mock_queue(
            id=300,
            schema="https://api.test.rossum.ai/v1/schemas/50",
            engine="https://api.test.rossum.ai/v1/engines/60",
        )
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)
        mock_client.retrieve_schema.side_effect = Exception("Schema fetch failed")
        mock_client.retrieve_engine.side_effect = Exception("Engine fetch failed")

        result = await _create_queue_from_template(
            mock_client, "https://api.test.rossum.ai/v1", "Queue", "EU Demo Template", workspace_id=1
        )

        # No tracked resources → embed_tracked_resources returns the original Queue dataclass
        assert isinstance(result, Queue)
        assert result.id == 300

    @pytest.mark.asyncio
    async def test_queue_with_no_engine_only_tracks_schema(self, mock_client: AsyncMock) -> None:
        """Test that queue with no engine URL only tracks schema."""
        mock_queue = create_mock_queue(
            id=300,
            schema="https://api.test.rossum.ai/v1/schemas/50",
            engine=None,
            dedicated_engine=None,
            generic_engine=None,
        )
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)
        mock_client.retrieve_schema.return_value = create_mock_schema(id=50, name="Template Schema")

        result = await _create_queue_from_template(
            mock_client, "https://api.test.rossum.ai/v1", "Queue", "EU Demo Template", workspace_id=1
        )

        assert isinstance(result, dict)
        tracked = result[TRACKED_RESOURCES_KEY]
        assert len(tracked) == 1
        assert tracked[0]["entity_type"] == "schema"
        mock_client.retrieve_engine.assert_not_called()


@pytest.mark.unit
class TestGetQueueEngineUrl:
    """Tests for get_queue_engine_url helper."""

    BASE = "https://api.test.rossum.ai/v1/engines"

    @pytest.mark.parametrize(
        ("dedicated", "generic", "engine", "expected_id"),
        [
            (20, 30, 10, 20),
            (None, 30, 10, 30),
            (None, None, 10, 10),
            (None, None, None, None),
        ],
        ids=["dedicated_priority", "generic_fallback", "engine_fallback", "all_none"],
    )
    def test_engine_url_priority(
        self, dedicated: int | None, generic: int | None, engine: int | None, expected_id: int | None
    ) -> None:
        def to_url(eid: int | None) -> str | None:
            return f"{self.BASE}/{eid}" if eid is not None else None

        queue = create_mock_queue(
            dedicated_engine=to_url(dedicated),
            generic_engine=to_url(generic),
            engine=to_url(engine),
        )
        assert get_queue_engine_url(queue) == to_url(expected_id)
