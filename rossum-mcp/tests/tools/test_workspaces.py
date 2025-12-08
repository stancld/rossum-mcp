"""Tests for rossum_mcp.tools.workspaces module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.workspace import Workspace

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


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
class TestGetWorkspace:
    """Tests for get_workspace tool."""

    @pytest.mark.asyncio
    async def test_get_workspace_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful workspace retrieval."""
        from rossum_mcp.tools.workspaces import register_workspace_tools

        register_workspace_tools(mock_mcp, mock_client)

        mock_workspace = create_mock_workspace(id=100, name="Production Workspace")
        mock_client.retrieve_workspace.return_value = mock_workspace

        get_workspace = mock_mcp._tools["get_workspace"]
        result = await get_workspace(workspace_id=100)

        assert result["id"] == 100
        assert result["name"] == "Production Workspace"
        mock_client.retrieve_workspace.assert_called_once_with(100)


@pytest.mark.unit
class TestListWorkspaces:
    """Tests for list_workspaces tool."""

    @pytest.mark.asyncio
    async def test_list_workspaces_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful workspaces listing."""
        from rossum_mcp.tools.workspaces import register_workspace_tools

        register_workspace_tools(mock_mcp, mock_client)

        mock_ws1 = create_mock_workspace(id=1, name="Workspace 1")
        mock_ws2 = create_mock_workspace(id=2, name="Workspace 2")

        async def async_iter():
            for item in [mock_ws1, mock_ws2]:
                yield item

        mock_client.list_workspaces = Mock(side_effect=lambda **kwargs: async_iter())

        list_workspaces = mock_mcp._tools["list_workspaces"]
        result = await list_workspaces()

        assert result["count"] == 2
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_list_workspaces_with_organization_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test workspaces listing filtered by organization."""
        from rossum_mcp.tools.workspaces import register_workspace_tools

        register_workspace_tools(mock_mcp, mock_client)

        mock_ws = create_mock_workspace(id=1, name="Org Workspace")

        async def async_iter():
            yield mock_ws

        mock_client.list_workspaces = Mock(side_effect=lambda **kwargs: async_iter())

        list_workspaces = mock_mcp._tools["list_workspaces"]
        result = await list_workspaces(organization_id=50)

        assert result["count"] == 1
        mock_client.list_workspaces.assert_called_once_with(organization=50)

    @pytest.mark.asyncio
    async def test_list_workspaces_with_name_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test workspaces listing filtered by name."""
        from rossum_mcp.tools.workspaces import register_workspace_tools

        register_workspace_tools(mock_mcp, mock_client)

        mock_ws = create_mock_workspace(id=1, name="Production")

        async def async_iter():
            yield mock_ws

        mock_client.list_workspaces = Mock(side_effect=lambda **kwargs: async_iter())

        list_workspaces = mock_mcp._tools["list_workspaces"]
        result = await list_workspaces(name="Production")

        assert result["count"] == 1
        mock_client.list_workspaces.assert_called_once_with(name="Production")


@pytest.mark.unit
class TestCreateWorkspace:
    """Tests for create_workspace tool."""

    @pytest.mark.asyncio
    async def test_create_workspace_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful workspace creation."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.workspaces import register_workspace_tools

        register_workspace_tools(mock_mcp, mock_client)

        mock_workspace = create_mock_workspace(id=200, name="New Workspace")
        mock_client.create_new_workspace.return_value = mock_workspace

        create_workspace = mock_mcp._tools["create_workspace"]
        result = await create_workspace(name="New Workspace", organization_id=1)

        assert result["id"] == 200
        assert result["name"] == "New Workspace"
        assert "created successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_create_workspace_with_metadata(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test workspace creation with metadata."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.workspaces import register_workspace_tools

        register_workspace_tools(mock_mcp, mock_client)

        mock_workspace = create_mock_workspace(id=200, name="New Workspace")
        mock_client.create_new_workspace.return_value = mock_workspace

        create_workspace = mock_mcp._tools["create_workspace"]
        result = await create_workspace(
            name="New Workspace",
            organization_id=1,
            metadata={"department": "finance"},
        )

        assert result["id"] == 200
        call_args = mock_client.create_new_workspace.call_args[0][0]
        assert call_args["metadata"] == {"department": "finance"}

    @pytest.mark.asyncio
    async def test_create_workspace_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_workspace is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.workspaces import register_workspace_tools

        register_workspace_tools(mock_mcp, mock_client)

        create_workspace = mock_mcp._tools["create_workspace"]
        result = await create_workspace(name="New Workspace", organization_id=1)

        assert result["error"] == "create_workspace is not available in read-only mode"
        mock_client.create_new_workspace.assert_not_called()
