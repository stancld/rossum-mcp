"""Tests for rossum_mcp.tools.update.users module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.user import User
from rossum_mcp.tools.update.users import register_user_tools


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
class TestUpdateUser:
    """Tests for update_user tool."""

    @pytest.mark.asyncio
    async def test_update_user_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful user update."""
        register_user_tools(mock_mcp, mock_client)

        updated_user = create_mock_user(id=100, first_name="Updated")
        mock_client._http_client.update.return_value = updated_user
        mock_client._deserializer = Mock(return_value=updated_user)

        update_user = mock_mcp._tools["update_user"]
        result = await update_user(user_id=100, first_name="Updated")

        assert result.first_name == "Updated"
        mock_client._http_client.update.assert_called_once()
        call_args = mock_client._http_client.update.call_args
        assert call_args[0][1] == 100
        assert call_args[0][2] == {"first_name": "Updated"}

    @pytest.mark.asyncio
    async def test_update_user_multiple_fields(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test user update with multiple fields."""
        register_user_tools(mock_mcp, mock_client)

        updated_user = create_mock_user(id=100, first_name="Jane", is_active=False)
        mock_client._http_client.update.return_value = updated_user
        mock_client._deserializer = Mock(return_value=updated_user)

        update_user = mock_mcp._tools["update_user"]
        result = await update_user(
            user_id=100,
            first_name="Jane",
            last_name="Doe",
            is_active=False,
            groups=["https://api.test.rossum.ai/v1/groups/3"],
        )

        assert result.first_name == "Jane"
        call_args = mock_client._http_client.update.call_args
        patch_data = call_args[0][2]
        assert patch_data == {
            "first_name": "Jane",
            "last_name": "Doe",
            "is_active": False,
            "groups": ["https://api.test.rossum.ai/v1/groups/3"],
        }
