"""Tests for rossum_mcp.tools.create.users module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.organization import Organization
from rossum_api.models.user import User
from rossum_mcp.tools.create import register_create_tools


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


def create_mock_organization(**kwargs) -> Organization:
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/organizations/1",
        "name": "Test Org",
        "workspaces": [],
        "users": [],
        "organization_group": "https://api.test.rossum.ai/v1/organization_groups/1",
        "is_trial": False,
        "created_at": "2024-01-01T00:00:00Z",
    }
    defaults.update(kwargs)
    return Organization(**defaults)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)

    async def _mock_list_organizations(**filters):
        yield create_mock_organization()

    client.list_organizations = _mock_list_organizations
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
class TestCreateUser:
    """Tests for create_user tool."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful user creation."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_user = create_mock_user(
            id=100,
            username="new.user@example.com",
            email="new.user@example.com",
        )
        mock_client.create_new_user.return_value = mock_user

        create_user = mock_mcp._tools["create_user"]
        result = await create_user(username="new.user@example.com", email="new.user@example.com")

        assert result.id == 100
        assert result.username == "new.user@example.com"
        mock_client.create_new_user.assert_called_once_with(
            {
                "username": "new.user@example.com",
                "email": "new.user@example.com",
                "organization": "https://api.test.rossum.ai/v1/organizations/1",
                "is_active": True,
                "auth_type": "password",
            }
        )

    @pytest.mark.asyncio
    async def test_create_user_with_optional_fields(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test user creation with optional fields."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_user = create_mock_user(
            id=101,
            username="jane@example.com",
            email="jane@example.com",
            first_name="Jane",
            last_name="Smith",
        )
        mock_client.create_new_user.return_value = mock_user

        create_user = mock_mcp._tools["create_user"]
        result = await create_user(
            username="jane@example.com",
            email="jane@example.com",
            first_name="Jane",
            last_name="Smith",
            queues=["https://api.test.rossum.ai/v1/queues/1"],
            groups=["https://api.test.rossum.ai/v1/groups/2"],
            metadata={"external_id": "abc123"},
        )

        assert result.id == 101
        call_data = mock_client.create_new_user.call_args[0][0]
        assert call_data["username"] == "jane@example.com"
        assert call_data["organization"] == "https://api.test.rossum.ai/v1/organizations/1"
        assert call_data["first_name"] == "Jane"
        assert call_data["last_name"] == "Smith"
        assert call_data["queues"] == ["https://api.test.rossum.ai/v1/queues/1"]
        assert call_data["groups"] == ["https://api.test.rossum.ai/v1/groups/2"]
        assert call_data["metadata"] == {"external_id": "abc123"}
