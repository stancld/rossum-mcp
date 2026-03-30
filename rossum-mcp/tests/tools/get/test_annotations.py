"""Tests for rossum_mcp.tools.get.annotations and related modules."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, Mock

import anyio
import pytest
from conftest import create_mock_annotation, create_mock_queue
from rossum_mcp.tools.get.handler import register_get_tools
from rossum_mcp.tools.get.registry import _get_annotation
from rossum_mcp.tools.search.registry import _list_annotations


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
class TestGetAnnotation:
    """Tests for get_annotation tool."""

    @pytest.mark.asyncio
    async def test_get_annotation_success(self, mock_client: AsyncMock) -> None:
        """Test successful annotation retrieval with workspace resolution."""
        mock_annotation = create_mock_annotation(id=67890, status="confirmed")
        mock_client.retrieve_annotation.return_value = mock_annotation

        mock_queues = [
            create_mock_queue(
                id=1,
                url="https://api.test.rossum.ai/v1/queues/1",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            )
        ]

        async def mock_fetch_all(resource, **filters):
            for item in mock_queues:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _get_annotation(mock_client, annotation_id=67890)

        assert result.id == 67890
        assert result.status == "confirmed"
        assert result.workspaces == ["https://api.test.rossum.ai/v1/workspaces/100"]
        mock_client.retrieve_annotation.assert_called_once_with(67890)

    @pytest.mark.asyncio
    async def test_get_annotation_resolves_workspace(self, mock_client: AsyncMock) -> None:
        """Test that workspace URL is resolved from the queue field."""
        mock_annotation = create_mock_annotation(
            id=67890,
            queue="https://api.test.rossum.ai/v1/queues/10",
        )
        mock_client.retrieve_annotation.return_value = mock_annotation

        mock_queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/200",
            )
        ]

        async def mock_fetch_all(resource, **filters):
            for item in mock_queues:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _get_annotation(mock_client, annotation_id=67890)

        assert result.id == 67890
        assert result.workspaces == ["https://api.test.rossum.ai/v1/workspaces/200"]

    @pytest.mark.asyncio
    async def test_get_annotation_unresolvable_queue(self, mock_client: AsyncMock) -> None:
        """Test that workspaces is empty when queue cannot be resolved."""
        mock_annotation = create_mock_annotation(
            id=67890,
            queue="https://api.test.rossum.ai/v1/queues/999",
        )
        mock_client.retrieve_annotation.return_value = mock_annotation

        async def mock_fetch_all(resource, **filters):
            return
            yield

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _get_annotation(mock_client, annotation_id=67890)

        assert result.id == 67890
        assert result.workspaces == []

    @pytest.mark.asyncio
    async def test_get_annotation_no_queue(self, mock_client: AsyncMock) -> None:
        """Test that workspaces is empty when annotation has no queue."""
        mock_annotation = create_mock_annotation(id=67890, queue=None)
        mock_client.retrieve_annotation.return_value = mock_annotation

        result = await _get_annotation(mock_client, annotation_id=67890)

        assert result.id == 67890
        assert result.workspaces == []


@pytest.mark.unit
class TestGetAnnotationContent:
    """Tests for get_annotation_content tool."""

    @pytest.mark.asyncio
    async def test_get_annotation_content_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test annotation content is written to a local file and path is returned."""
        register_get_tools(mock_mcp, mock_client)

        content_data = [{"id": "abc123", "value": "test_value"}]
        mock_annotation = create_mock_annotation(id=67890, content=content_data)
        mock_client.retrieve_annotation.return_value = mock_annotation

        get_annotation_content = mock_mcp._tools["get_annotation_content"]
        result = await get_annotation_content(annotation_id=67890)

        assert "path" in result
        path = anyio.Path(result["path"])
        assert await path.exists()
        assert json.loads(await path.read_text()) == content_data
        mock_client.retrieve_annotation.assert_called_once_with(67890, sideloads=("content",))
        await path.unlink()


@pytest.mark.unit
class TestListAnnotations:
    """Tests for list_annotations tool."""

    @pytest.mark.asyncio
    async def test_list_annotations_success(self, mock_client: AsyncMock) -> None:
        """Test successful annotations listing with workspace resolution."""
        mock_ann1 = create_mock_annotation(id=1, status="confirmed", queue="https://api.test.rossum.ai/v1/queues/10")
        mock_ann2 = create_mock_annotation(id=2, status="to_review", queue="https://api.test.rossum.ai/v1/queues/10")
        mock_queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            )
        ]

        call_count = 0

        async def mock_fetch_all(resource, **filters):
            nonlocal call_count
            items = [mock_ann1, mock_ann2] if call_count == 0 else mock_queues
            call_count += 1
            for item in items:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_annotations(mock_client, queue_id=100, status="confirmed,to_review")

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2
        assert result[0].workspaces == ["https://api.test.rossum.ai/v1/workspaces/100"]
        assert result[1].workspaces == ["https://api.test.rossum.ai/v1/workspaces/100"]

    @pytest.mark.asyncio
    async def test_list_annotations_filters_by_workspace_id(self, mock_client: AsyncMock) -> None:
        """Test that workspace_id filter keeps only annotations in the given workspace."""
        mock_ann1 = create_mock_annotation(id=1, status="confirmed", queue="https://api.test.rossum.ai/v1/queues/10")
        mock_ann2 = create_mock_annotation(id=2, status="to_review", queue="https://api.test.rossum.ai/v1/queues/20")
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

        call_count = 0

        async def mock_fetch_all(resource, **filters):
            nonlocal call_count
            items = [mock_ann1, mock_ann2] if call_count == 0 else mock_queues
            call_count += 1
            for item in items:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_annotations(mock_client, queue_id=100, workspace_id=100)

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].workspaces == ["https://api.test.rossum.ai/v1/workspaces/100"]

    @pytest.mark.asyncio
    async def test_list_annotations_workspace_id_no_match(self, mock_client: AsyncMock) -> None:
        """Test that workspace_id filter returns empty when no annotations match."""
        mock_ann1 = create_mock_annotation(id=1, status="confirmed", queue="https://api.test.rossum.ai/v1/queues/10")
        mock_queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
        ]

        call_count = 0

        async def mock_fetch_all(resource, **filters):
            nonlocal call_count
            items = [mock_ann1] if call_count == 0 else mock_queues
            call_count += 1
            for item in items:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_annotations(mock_client, queue_id=100, workspace_id=999)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_annotations_no_status_filter(self, mock_client: AsyncMock) -> None:
        """Test annotations listing without status filter."""

        async def mock_fetch_all(resource, **filters):
            return
            yield

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_annotations(mock_client, queue_id=100, status=None)

        assert len(result) == 0
        assert result == []

    @pytest.mark.asyncio
    async def test_list_annotations_skips_broken_items(self, mock_client: AsyncMock) -> None:
        """Test list_annotations gracefully skips items that fail deserialization."""
        mock_ann = create_mock_annotation(id=1, status="confirmed")
        mock_queues = [
            create_mock_queue(
                id=1,
                url="https://api.test.rossum.ai/v1/queues/1",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            )
        ]

        def mock_deserializer(resource, raw):
            if isinstance(raw, dict) and raw.get("id") == 2:
                raise ValueError("broken annotation")
            if isinstance(raw, dict):
                return mock_ann
            return raw

        mock_client._deserializer = mock_deserializer

        call_count = 0

        async def mock_fetch_all(resource, **filters):
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                yield {"id": 1, "status": "confirmed"}
                yield {"id": 2, "status": "broken"}
                yield {"id": 3, "status": "to_review"}
            else:
                call_count += 1
                for item in mock_queues:
                    yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_annotations(mock_client, queue_id=100, status="confirmed,to_review")

        assert len(result) == 2
