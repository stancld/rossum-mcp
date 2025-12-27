"""Tests for rossum_mcp.tools.users module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.group import Group
from rossum_api.models.user import User
from rossum_mcp.tools.users import register_user_tools


def create_mock_user(**kwargs) -> User:
    """Create a mock User dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/users/1",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "date_joined": "2024-01-01T00:00:00Z",
        "username": "john.doe@example.com",
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "last_login": "2024-01-15T10:30:00Z",
        "is_active": True,
        "email_verified": True,
        "password": None,
        "groups": [],
        "queues": [],
        "ui_settings": {},
        "metadata": {},
        "oidc_id": None,
        "auth_type": "password",
        "deleted": False,
    }
    defaults.update(kwargs)
    return User(**defaults)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    return AsyncMock()


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
class TestGetUser:
    """Tests for get_user tool."""

    @pytest.mark.asyncio
    async def test_get_user_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful user retrieval."""
        register_user_tools(mock_mcp, mock_client)

        mock_user = create_mock_user(id=100, username="test.user@example.com")
        mock_client.retrieve_user.return_value = mock_user

        get_user = mock_mcp._tools["get_user"]
        result = await get_user(user_id=100)

        assert result.id == 100
        assert result.username == "test.user@example.com"
        mock_client.retrieve_user.assert_called_once_with(100)


@pytest.mark.unit
class TestListUsers:
    """Tests for list_users tool."""

    @pytest.mark.asyncio
    async def test_list_users_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful users listing."""
        register_user_tools(mock_mcp, mock_client)

        mock_user1 = create_mock_user(id=1, username="user1@example.com")
        mock_user2 = create_mock_user(id=2, username="user2@example.com")

        async def async_iter():
            for item in [mock_user1, mock_user2]:
                yield item

        mock_client.list_users = Mock(side_effect=lambda **kwargs: async_iter())

        list_users = mock_mcp._tools["list_users"]
        result = await list_users()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_users_with_username_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test users listing filtered by username."""
        register_user_tools(mock_mcp, mock_client)

        mock_user = create_mock_user(id=1, username="specific.user@example.com")

        async def async_iter():
            yield mock_user

        mock_client.list_users = Mock(side_effect=lambda **kwargs: async_iter())

        list_users = mock_mcp._tools["list_users"]
        result = await list_users(username="specific.user@example.com")

        assert len(result) == 1
        mock_client.list_users.assert_called_once_with(username="specific.user@example.com")

    @pytest.mark.asyncio
    async def test_list_users_with_email_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test users listing filtered by email."""
        register_user_tools(mock_mcp, mock_client)

        mock_user = create_mock_user(id=1, email="test@example.com")

        async def async_iter():
            yield mock_user

        mock_client.list_users = Mock(side_effect=lambda **kwargs: async_iter())

        list_users = mock_mcp._tools["list_users"]
        result = await list_users(email="test@example.com")

        assert len(result) == 1
        mock_client.list_users.assert_called_once_with(email="test@example.com")

    @pytest.mark.asyncio
    async def test_list_users_with_is_active_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test users listing filtered by active status."""
        register_user_tools(mock_mcp, mock_client)

        mock_user = create_mock_user(id=1, is_active=True)

        async def async_iter():
            yield mock_user

        mock_client.list_users = Mock(side_effect=lambda **kwargs: async_iter())

        list_users = mock_mcp._tools["list_users"]
        result = await list_users(is_active=True)

        assert len(result) == 1
        mock_client.list_users.assert_called_once_with(is_active=True)

    @pytest.mark.asyncio
    async def test_list_users_empty_result(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test users listing when no users match."""
        register_user_tools(mock_mcp, mock_client)

        async def async_iter():
            for _ in []:
                yield

        mock_client.list_users = Mock(side_effect=lambda **kwargs: async_iter())

        list_users = mock_mcp._tools["list_users"]
        result = await list_users()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_users_with_multiple_filters(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test users listing with multiple filters."""
        register_user_tools(mock_mcp, mock_client)

        mock_user = create_mock_user(id=1, first_name="John", last_name="Doe")

        async def async_iter():
            yield mock_user

        mock_client.list_users = Mock(side_effect=lambda **kwargs: async_iter())

        list_users = mock_mcp._tools["list_users"]
        result = await list_users(first_name="John", last_name="Doe")

        assert len(result) == 1
        mock_client.list_users.assert_called_once_with(first_name="John", last_name="Doe")


@pytest.mark.unit
class TestListUserRoles:
    """Tests for list_user_roles tool."""

    @pytest.mark.asyncio
    async def test_list_user_roles_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful user roles listing."""
        register_user_tools(mock_mcp, mock_client)

        mock_group1 = Group(id=1, url="https://api.test.rossum.ai/v1/groups/1", name="admin")
        mock_group2 = Group(id=2, url="https://api.test.rossum.ai/v1/groups/2", name="annotator")

        async def async_iter():
            for item in [mock_group1, mock_group2]:
                yield item

        mock_client.list_user_roles = Mock(return_value=async_iter())

        list_user_roles = mock_mcp._tools["list_user_roles"]
        result = await list_user_roles()

        assert len(result) == 2
        assert result[0].name == "admin"
        assert result[1].name == "annotator"
