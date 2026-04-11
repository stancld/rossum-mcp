"""Tests for user and user role search functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.group import Group
from rossum_api.models.user import User
from rossum_mcp.tools.search.users import _list_user_roles, _list_users


def _user(
    id: int = 1,
    username: str = "user1",
    email: str = "user1@example.com",
    groups: list[str] | None = None,
) -> User:
    return User(
        id=id,
        url=f"https://api.test.rossum.ai/v1/users/{id}",
        first_name="First",
        last_name="Last",
        email=email,
        date_joined="2025-01-01T00:00:00Z",
        username=username,
        organization="https://api.test.rossum.ai/v1/organizations/1",
        groups=groups or [],
    )


def _group(id: int, name: str) -> Group:
    return Group(id=id, name=name, url=f"https://api.test.rossum.ai/v1/groups/{id}")


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


ADMIN_GROUP_URL = "https://api.test.rossum.ai/v1/groups/10"


@pytest.mark.unit
class TestListUsers:
    @pytest.mark.asyncio
    async def test_returns_all_users(self, mock_client: AsyncMock) -> None:
        users = [_user(id=1), _user(id=2, username="user2", email="u2@example.com")]

        async def mock_fetch(resource, **filters):
            for u in users:
                yield u

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_users(mock_client)

        assert len(result) == 2
        assert {u.id for u in result} == {1, 2}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("is_admin_flag", "expected_ids"),
        [
            (True, {1}),
            (False, {2, 3}),
        ],
        ids=["filter_admins_only", "filter_non_admins_only"],
    )
    async def test_filter_by_organization_group_admin(
        self, mock_client: AsyncMock, is_admin_flag: bool, expected_ids: set[int]
    ) -> None:
        """Test client-side filtering by organization_group_admin role."""
        users = [
            _user(id=1, groups=[ADMIN_GROUP_URL]),
            _user(id=2, username="user2", email="u2@example.com", groups=["https://api.test.rossum.ai/v1/groups/20"]),
            _user(id=3, username="user3", email="u3@example.com", groups=[]),
        ]
        groups = [
            _group(10, "organization_group_admin"),
            _group(20, "annotator"),
        ]

        async def mock_fetch(resource, **filters):
            items = users if resource == Resource.User else groups
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_users(mock_client, is_organization_group_admin=is_admin_flag)

        assert {u.id for u in result} == expected_ids

    @pytest.mark.asyncio
    async def test_filter_admin_no_matching_role(self, mock_client: AsyncMock) -> None:
        """When no organization_group_admin role exists, no users match."""
        users = [_user(id=1, groups=["https://api.test.rossum.ai/v1/groups/20"])]
        groups = [_group(20, "annotator")]

        async def mock_fetch(resource, **filters):
            items = users if resource == Resource.User else groups
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_users(mock_client, is_organization_group_admin=True)

        assert result == []

    @pytest.mark.asyncio
    async def test_filter_admin_user_with_multiple_groups(self, mock_client: AsyncMock) -> None:
        """User belonging to both admin and other groups is included when filtering for admins."""
        users = [_user(id=1, groups=[ADMIN_GROUP_URL, "https://api.test.rossum.ai/v1/groups/20"])]
        groups = [_group(10, "organization_group_admin"), _group(20, "annotator")]

        async def mock_fetch(resource, **filters):
            items = users if resource == Resource.User else groups
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_users(mock_client, is_organization_group_admin=True)

        assert len(result) == 1
        assert result[0].id == 1

    @pytest.mark.asyncio
    async def test_skips_admin_filter_when_none(self, mock_client: AsyncMock) -> None:
        """When is_organization_group_admin is None, no group fetching occurs."""
        users = [_user(id=1, groups=[ADMIN_GROUP_URL])]

        call_resources: list[Resource] = []

        async def mock_fetch(resource, **filters):
            call_resources.append(resource)
            for u in users:
                yield u

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_users(mock_client)

        assert len(result) == 1
        assert Resource.Group not in call_resources


@pytest.mark.unit
class TestListUserRoles:
    @pytest.mark.asyncio
    async def test_returns_all_roles(self, mock_client: AsyncMock) -> None:
        groups = [_group(10, "organization_group_admin"), _group(20, "annotator")]

        async def mock_fetch(resource, **filters):
            for g in groups:
                yield g

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_user_roles(mock_client)

        assert len(result) == 2
        assert {g.name for g in result} == {"organization_group_admin", "annotator"}
