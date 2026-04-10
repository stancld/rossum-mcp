"""Tests for rossum_mcp.tools.create.workspaces module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.workspace import Workspace
from rossum_mcp.tools.create import register_create_tools


def create_mock_workspace(**kwargs) -> Workspace:
    """Create a mock Workspace dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/workspaces/1",
        "name": "Test Workspace",
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "queues": [],
        "autopilot": False,
        "metadata": {},
    }
    defaults.update(kwargs)
    return Workspace(**defaults)


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
class TestCreateWorkspace:
    """Tests for create_workspace tool."""

    @pytest.mark.asyncio
    async def test_create_workspace_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful workspace creation."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_workspace = create_mock_workspace(id=200, name="New Workspace")
        mock_client.create_new_workspace.return_value = mock_workspace

        create_workspace = mock_mcp._tools["create_workspace"]
        result = await create_workspace(name="New Workspace", organization_id=1)

        assert result.id == 200
        assert result.name == "New Workspace"

    @pytest.mark.asyncio
    async def test_create_workspace_with_metadata(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test workspace creation with metadata."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_workspace = create_mock_workspace(id=200, name="New Workspace")
        mock_client.create_new_workspace.return_value = mock_workspace

        create_workspace = mock_mcp._tools["create_workspace"]
        result = await create_workspace(
            name="New Workspace",
            organization_id=1,
            metadata={"department": "finance"},
        )

        assert result.id == 200
        call_args = mock_client.create_new_workspace.call_args[0][0]
        assert call_args["metadata"] == {"department": "finance"}
