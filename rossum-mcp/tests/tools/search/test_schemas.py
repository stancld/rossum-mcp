"""Tests for schema search functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_queue, create_mock_schema
from rossum_api.domain_logic.resources import Resource
from rossum_mcp.tools.search.schemas import _list_schemas


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestListSchemas:
    @pytest.mark.asyncio
    async def test_resolves_workspaces(self, mock_client: AsyncMock) -> None:
        schemas = [
            create_mock_schema(
                id=1,
                name="Schema 1",
                queues=["https://api.test.rossum.ai/v1/queues/10"],
            ),
        ]
        queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
        ]

        async def mock_fetch(resource, **filters):
            items = schemas if resource == Resource.Schema else queues
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_schemas(mock_client)

        assert len(result) == 1
        assert result[0].workspaces == ["https://api.test.rossum.ai/v1/workspaces/100"]

    @pytest.mark.asyncio
    async def test_truncates_content(self, mock_client: AsyncMock) -> None:
        """SchemaListItem omits content field."""
        schemas = [create_mock_schema(id=1, name="S1", content=[{"id": "big_section"}])]

        async def mock_fetch(resource, **filters):
            for s in schemas:
                yield s

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_schemas(mock_client)

        assert result[0].content == "<omitted>"

    @pytest.mark.asyncio
    async def test_filter_by_workspace_id(self, mock_client: AsyncMock) -> None:
        schemas = [
            create_mock_schema(id=1, name="S1", queues=["https://api.test.rossum.ai/v1/queues/10"]),
            create_mock_schema(id=2, name="S2", queues=["https://api.test.rossum.ai/v1/queues/20"]),
        ]
        queues = [
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

        async def mock_fetch(resource, **filters):
            items = schemas if resource == Resource.Schema else queues
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_schemas(mock_client, workspace_id=200)

        assert len(result) == 1
        assert result[0].id == 2

    @pytest.mark.asyncio
    async def test_regex_name_filter(self, mock_client: AsyncMock) -> None:
        schemas = [
            create_mock_schema(id=1, name="Invoice Schema"),
            create_mock_schema(id=2, name="PO Schema"),
            create_mock_schema(id=3, name="Invoice Template Schema"),
        ]

        async def mock_fetch(resource, **filters):
            for s in schemas:
                yield s

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_schemas(mock_client, name="^Invoice", use_regex=True)

        assert len(result) == 2
        assert {r.id for r in result} == {1, 3}

    @pytest.mark.asyncio
    async def test_no_queues_yields_none_workspaces(self, mock_client: AsyncMock) -> None:
        schemas = [create_mock_schema(id=1, name="Orphan", queues=[])]

        async def mock_fetch(resource, **filters):
            for s in schemas:
                yield s

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_schemas(mock_client)

        assert result[0].workspaces is None
