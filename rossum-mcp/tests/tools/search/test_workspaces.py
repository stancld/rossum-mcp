"""Tests for workspace search functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_workspace
from rossum_mcp.tools.search.workspaces import _list_workspaces


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestListWorkspaces:
    @pytest.mark.asyncio
    async def test_returns_all_workspaces(self, mock_client: AsyncMock) -> None:
        workspaces = [
            create_mock_workspace(id=1, name="WS 1"),
            create_mock_workspace(id=2, name="WS 2"),
        ]

        async def mock_fetch(resource, **filters):
            for w in workspaces:
                yield w

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_workspaces(mock_client)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_regex_name_filter(self, mock_client: AsyncMock) -> None:
        workspaces = [
            create_mock_workspace(id=1, name="Production US"),
            create_mock_workspace(id=2, name="Staging"),
            create_mock_workspace(id=3, name="Production EU"),
        ]

        async def mock_fetch(resource, **filters):
            for w in workspaces:
                yield w

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_workspaces(mock_client, name="^Production", use_regex=True)

        assert len(result) == 2
        assert {w.id for w in result} == {1, 3}

    @pytest.mark.asyncio
    async def test_organization_id_passed_as_filter(self, mock_client: AsyncMock) -> None:
        captured_filters: dict = {}

        async def mock_fetch(resource, **filters):
            captured_filters.update(filters)
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_fetch

        await _list_workspaces(mock_client, organization_id=42)

        assert captured_filters["organization"] == 42

    @pytest.mark.asyncio
    async def test_regex_bypasses_api_name_filter(self, mock_client: AsyncMock) -> None:
        captured_filters: dict = {}

        async def mock_fetch(resource, **filters):
            captured_filters.update(filters)
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_fetch

        await _list_workspaces(mock_client, name="test", use_regex=True)

        assert "name" not in captured_filters
