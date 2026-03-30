"""Tests for get_email_template operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_email_template, create_mock_queue
from rossum_mcp.tools.get.registry import _get_email_template


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestGetEmailTemplate:
    """Tests for get_email_template tool."""

    @pytest.mark.asyncio
    async def test_get_email_template_success(self, mock_client: AsyncMock) -> None:
        """Test successful email template retrieval."""
        mock_template = create_mock_email_template(id=5, name="Test Template")
        mock_client.retrieve_email_template.return_value = mock_template

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

        result = await _get_email_template(mock_client, 5)

        assert result.id == 5
        assert result.name == "Test Template"
        assert result.workspaces == ["https://api.test.rossum.ai/v1/workspaces/100"]
        mock_client.retrieve_email_template.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_get_email_template_resolves_workspace(self, mock_client: AsyncMock) -> None:
        """Test that workspace URL is resolved from the queue field."""
        mock_template = create_mock_email_template(
            id=5,
            name="Invoice Template",
            queue="https://api.test.rossum.ai/v1/queues/10",
        )
        mock_client.retrieve_email_template.return_value = mock_template

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

        result = await _get_email_template(mock_client, 5)

        assert result.id == 5
        assert result.workspaces == ["https://api.test.rossum.ai/v1/workspaces/200"]

    @pytest.mark.asyncio
    async def test_get_email_template_unresolvable_queue(self, mock_client: AsyncMock) -> None:
        """Test that workspaces is empty when queue cannot be resolved."""
        mock_template = create_mock_email_template(
            id=5,
            name="Orphan Template",
            queue="https://api.test.rossum.ai/v1/queues/999",
        )
        mock_client.retrieve_email_template.return_value = mock_template

        async def mock_fetch_all(resource, **filters):
            return
            yield

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _get_email_template(mock_client, 5)

        assert result.id == 5
        assert result.workspaces == []
