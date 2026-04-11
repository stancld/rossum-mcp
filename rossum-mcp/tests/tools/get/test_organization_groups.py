"""Tests for rossum_mcp.tools.get.registry and rossum_mcp.tools.search.registry (organization groups)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.organization_group import OrganizationGroup
from rossum_mcp.tools.get.registry import _get_organization_group
from rossum_mcp.tools.search.organization_groups import _list_organization_groups


def create_mock_organization_group(**kwargs) -> OrganizationGroup:
    defaults = {
        "id": 1,
        "name": "Test Organization Group",
        "is_trial": False,
        "is_production": True,
        "deployment_location": "eu",
        "modified_by": None,
        "modified_at": None,
        "features": None,
        "usage": {},
    }
    defaults.update(kwargs)
    return OrganizationGroup(**defaults)


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestGetOrganizationGroup:
    """Tests for get_organization_group tool."""

    @pytest.mark.asyncio
    async def test_get_organization_group_success(self, mock_client: AsyncMock) -> None:
        """Test successful organization group retrieval."""
        mock_org_group = create_mock_organization_group(id=100, name="Production Organization Group")
        mock_client.retrieve_organization_group.return_value = mock_org_group

        result = await _get_organization_group(mock_client, organization_group_id=100)

        assert result.id == 100
        assert result.name == "Production Organization Group"
        mock_client.retrieve_organization_group.assert_called_once_with(100)


@pytest.mark.unit
class TestListOrganizationGroups:
    """Tests for list_organization_groups tool."""

    @pytest.mark.asyncio
    async def test_list_organization_groups_success(self, mock_client: AsyncMock) -> None:
        """Test successful organization groups listing."""
        mock_og1 = create_mock_organization_group(id=1, name="Organization Group 1")
        mock_og2 = create_mock_organization_group(id=2, name="Organization Group 2")

        async def mock_cursor_fetch_all(resource, **filters):
            yield mock_og1
            yield mock_og2

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_organization_groups(mock_client)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_organization_groups_with_name_filter(self, mock_client: AsyncMock) -> None:
        """Test organization groups listing filtered by name."""
        mock_og = create_mock_organization_group(id=1, name="Production")
        received_filters: dict = {}

        async def mock_cursor_fetch_all(resource, **filters):
            received_filters.update(filters)
            yield mock_og

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_organization_groups(mock_client, name="Production")

        assert len(result) == 1
        assert received_filters["name"] == "Production"

    @pytest.mark.asyncio
    async def test_list_organization_groups_skips_broken_items(self, mock_client: AsyncMock) -> None:
        """Test list_organization_groups gracefully skips items that fail deserialization."""
        mock_og = create_mock_organization_group(id=1, name="Good Organization Group")

        call_count = 0

        def mock_deserializer(resource, raw):
            nonlocal call_count
            call_count += 1
            if raw.get("id") == 2:
                raise ValueError("broken organization group")
            return mock_og

        mock_client._deserializer = mock_deserializer

        async def mock_cursor_fetch_all(resource, **filters):
            yield {"id": 1}
            yield {"id": 2}
            yield {"id": 3}

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_organization_groups(mock_client)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_organization_groups_with_regex_name_filter(self, mock_client: AsyncMock) -> None:
        """Test that use_regex=True filters organization groups client-side by regex pattern."""
        mock_groups = [
            create_mock_organization_group(id=1, name="ACME Corp EU"),
            create_mock_organization_group(id=2, name="Beta Ltd"),
            create_mock_organization_group(id=3, name="acme-backup"),
        ]
        received_filters: dict = {}

        async def mock_cursor_fetch_all(resource, **filters):
            received_filters.update(filters)
            for group in mock_groups:
                yield group

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_organization_groups(mock_client, name="acme", use_regex=True)

        assert len(result) == 2
        assert result[0].name == "ACME Corp EU"
        assert result[1].name == "acme-backup"
        assert "name" not in received_filters

    @pytest.mark.asyncio
    async def test_list_organization_groups_with_regex_no_match(self, mock_client: AsyncMock) -> None:
        """Test that use_regex=True returns empty list when no groups match pattern."""
        mock_groups = [create_mock_organization_group(id=1, name="Beta Ltd")]

        async def mock_cursor_fetch_all(resource, **filters):
            for group in mock_groups:
                yield group

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_organization_groups(mock_client, name="^acme$", use_regex=True)

        assert len(result) == 0
