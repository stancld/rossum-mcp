"""Tests for _list_email_templates workspace resolution."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_email_template, create_mock_queue
from rossum_mcp.tools.search.email_templates import _list_email_templates


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestListEmailTemplates:
    """Tests for _list_email_templates workspace resolution."""

    @pytest.mark.asyncio
    async def test_list_email_templates_resolves_workspaces(self, mock_client: AsyncMock) -> None:
        """Test that workspace URLs are resolved from queue data."""
        mock_templates = [
            create_mock_email_template(
                id=1,
                name="Template 1",
                queue="https://api.test.rossum.ai/v1/queues/10",
            ),
            create_mock_email_template(
                id=2,
                name="Template 2",
                queue="https://api.test.rossum.ai/v1/queues/20",
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

        call_count = 0

        async def mock_cursor_fetch_all(resource, **filters):
            nonlocal call_count
            items = mock_templates if call_count == 0 else mock_queues
            call_count += 1
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_email_templates(mock_client)

        assert len(result) == 2
        assert result[0].workspaces == ["https://api.test.rossum.ai/v1/workspaces/100"]
        assert result[1].workspaces == ["https://api.test.rossum.ai/v1/workspaces/200"]

    @pytest.mark.asyncio
    async def test_list_email_templates_same_queue_same_workspace(self, mock_client: AsyncMock) -> None:
        """Test templates on the same queue get the same workspace."""
        mock_templates = [
            create_mock_email_template(
                id=1,
                name="Template 1",
                queue="https://api.test.rossum.ai/v1/queues/10",
            ),
            create_mock_email_template(
                id=2,
                name="Template 2",
                queue="https://api.test.rossum.ai/v1/queues/10",
            ),
        ]
        mock_queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
        ]

        call_count = 0

        async def mock_cursor_fetch_all(resource, **filters):
            nonlocal call_count
            items = mock_templates if call_count == 0 else mock_queues
            call_count += 1
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_email_templates(mock_client)

        assert len(result) == 2
        assert result[0].workspaces == ["https://api.test.rossum.ai/v1/workspaces/100"]
        assert result[1].workspaces == ["https://api.test.rossum.ai/v1/workspaces/100"]

    @pytest.mark.asyncio
    async def test_list_email_templates_filters_by_workspace_id(self, mock_client: AsyncMock) -> None:
        """Test that workspace_id filter keeps only templates in the given workspace."""
        mock_templates = [
            create_mock_email_template(
                id=1,
                name="Template 1",
                queue="https://api.test.rossum.ai/v1/queues/10",
            ),
            create_mock_email_template(
                id=2,
                name="Template 2",
                queue="https://api.test.rossum.ai/v1/queues/20",
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

        call_count = 0

        async def mock_cursor_fetch_all(resource, **filters):
            nonlocal call_count
            items = mock_templates if call_count == 0 else mock_queues
            call_count += 1
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_email_templates(mock_client, workspace_id=100)

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].workspaces == ["https://api.test.rossum.ai/v1/workspaces/100"]

    @pytest.mark.asyncio
    async def test_list_email_templates_workspace_id_no_match(self, mock_client: AsyncMock) -> None:
        """Test that workspace_id filter returns empty when no templates match."""
        mock_templates = [
            create_mock_email_template(
                id=1,
                name="Template 1",
                queue="https://api.test.rossum.ai/v1/queues/10",
            ),
        ]
        mock_queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
        ]

        call_count = 0

        async def mock_cursor_fetch_all(resource, **filters):
            nonlocal call_count
            items = mock_templates if call_count == 0 else mock_queues
            call_count += 1
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_email_templates(mock_client, workspace_id=999)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_email_templates_unresolvable_queue(self, mock_client: AsyncMock) -> None:
        """Test that workspaces is empty when queue cannot be resolved."""
        mock_templates = [
            create_mock_email_template(
                id=1,
                name="Template 1",
                queue="https://api.test.rossum.ai/v1/queues/999",
            ),
        ]

        call_count = 0

        async def mock_cursor_fetch_all(resource, **filters):
            nonlocal call_count
            items = mock_templates if call_count == 0 else []
            call_count += 1
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_email_templates(mock_client)

        assert len(result) == 1
        assert result[0].workspaces == []
