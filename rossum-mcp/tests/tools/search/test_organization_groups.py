"""Tests for organization group search functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.organization_group import OrganizationGroup
from rossum_mcp.tools.search.organization_groups import _list_organization_groups


def _org_group(id: int, name: str) -> OrganizationGroup:
    return OrganizationGroup(
        id=id,
        name=name,
        is_trial=False,
        is_production=True,
        deployment_location="eu",
    )


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestListOrganizationGroups:
    @pytest.mark.asyncio
    async def test_returns_all_groups(self, mock_client: AsyncMock) -> None:
        groups = [_org_group(1, "Group A"), _org_group(2, "Group B")]

        async def mock_fetch(resource, **filters):
            for g in groups:
                yield g

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_organization_groups(mock_client)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_regex_name_filter(self, mock_client: AsyncMock) -> None:
        groups = [
            _org_group(1, "Production EU"),
            _org_group(2, "Staging"),
            _org_group(3, "Production US"),
        ]

        async def mock_fetch(resource, **filters):
            for g in groups:
                yield g

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_organization_groups(mock_client, name="Production", use_regex=True)

        assert len(result) == 2
        assert {g.id for g in result} == {1, 3}

    @pytest.mark.asyncio
    async def test_regex_bypasses_api_name_filter(self, mock_client: AsyncMock) -> None:
        captured_filters: dict = {}

        async def mock_fetch(resource, **filters):
            captured_filters.update(filters)
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_fetch

        await _list_organization_groups(mock_client, name="test", use_regex=True)

        assert "name" not in captured_filters
