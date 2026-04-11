"""Tests for engine search functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_engine
from rossum_mcp.tools.search.engines import _list_engines


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestListEngines:
    @pytest.mark.asyncio
    async def test_returns_all_engines(self, mock_client: AsyncMock) -> None:
        engines = [
            create_mock_engine(id=1, name="Extractor", type="extractor"),
            create_mock_engine(id=2, name="Splitter", type="splitter"),
        ]

        async def mock_fetch(resource, **filters):
            for e in engines:
                yield e

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_engines(mock_client)

        assert len(result) == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("engine_type", "agenda_id", "expected_filter_key", "expected_filter_value"),
        [
            ("extractor", None, "type", "extractor"),
            (None, "my-agenda", "agenda_id", "my-agenda"),
        ],
        ids=["filter_by_type", "filter_by_agenda"],
    )
    async def test_passes_filters_to_api(
        self,
        mock_client: AsyncMock,
        engine_type: str | None,
        agenda_id: str | None,
        expected_filter_key: str,
        expected_filter_value: str,
    ) -> None:
        captured_filters: dict = {}

        async def mock_fetch(resource, **filters):
            captured_filters.update(filters)
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_fetch

        await _list_engines(mock_client, engine_type=engine_type, agenda_id=agenda_id)

        assert captured_filters[expected_filter_key] == expected_filter_value
