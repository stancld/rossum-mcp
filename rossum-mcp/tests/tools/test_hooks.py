"""Tests for rossum_mcp.tools.hooks module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.hook import Hook

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def create_mock_hook(**kwargs) -> Hook:
    """Create a mock Hook dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/hooks/1",
        "name": "Test Hook",
        "type": "function",
        "queues": [],
        "events": [],
        "active": True,
        "config": {},
        "settings": {},
        "sideload": [],
        "run_after": [],
        "metadata": {},
        "extension_source": "custom",
        "test": {},
        "token_owner": None,
        "extension_image_url": None,
        "guide": None,
        "read_more_url": None,
    }
    defaults.update(kwargs)
    return Hook(**defaults)


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
class TestGetHook:
    """Tests for get_hook tool."""

    @pytest.mark.asyncio
    async def test_get_hook_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful hook retrieval."""
        from rossum_mcp.tools.hooks import register_hook_tools

        register_hook_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=123, name="Validation Hook", type="function")
        mock_client.retrieve_hook.return_value = mock_hook

        get_hook = mock_mcp._tools["get_hook"]
        result = await get_hook(hook_id=123)

        assert result.id == 123
        assert result.name == "Validation Hook"
        assert result.type == "function"
        mock_client.retrieve_hook.assert_called_once_with(123)


@pytest.mark.unit
class TestListHooks:
    """Tests for list_hooks tool."""

    @pytest.mark.asyncio
    async def test_list_hooks_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful hooks listing."""
        from rossum_mcp.tools.hooks import register_hook_tools

        register_hook_tools(mock_mcp, mock_client)

        mock_hook1 = create_mock_hook(id=1, name="Hook 1")
        mock_hook2 = create_mock_hook(id=2, name="Hook 2")

        async def async_iter():
            for item in [mock_hook1, mock_hook2]:
                yield item

        mock_client.list_hooks = Mock(side_effect=lambda **kwargs: async_iter())

        list_hooks = mock_mcp._tools["list_hooks"]
        result = await list_hooks()

        assert result.count == 2
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_list_hooks_with_queue_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test hooks listing filtered by queue."""
        from rossum_mcp.tools.hooks import register_hook_tools

        register_hook_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=1, name="Queue Hook")

        async def async_iter():
            yield mock_hook

        mock_client.list_hooks = Mock(side_effect=lambda **kwargs: async_iter())

        list_hooks = mock_mcp._tools["list_hooks"]
        result = await list_hooks(queue_id=100)

        assert result.count == 1
        mock_client.list_hooks.assert_called_once_with(queue=100)

    @pytest.mark.asyncio
    async def test_list_hooks_with_active_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test hooks listing filtered by active status."""
        from rossum_mcp.tools.hooks import register_hook_tools

        register_hook_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=1, active=True)

        async def async_iter():
            yield mock_hook

        mock_client.list_hooks = Mock(side_effect=lambda **kwargs: async_iter())

        list_hooks = mock_mcp._tools["list_hooks"]
        result = await list_hooks(active=True)

        assert result.count == 1
        mock_client.list_hooks.assert_called_once_with(active=True)

    @pytest.mark.asyncio
    async def test_list_hooks_with_first_n(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test hooks listing with first_n limit."""
        from rossum_mcp.tools.hooks import register_hook_tools

        register_hook_tools(mock_mcp, mock_client)

        mock_hook1 = create_mock_hook(id=1, name="Hook 1")
        mock_hook2 = create_mock_hook(id=2, name="Hook 2")
        mock_hook3 = create_mock_hook(id=3, name="Hook 3")

        async def async_iter():
            for item in [mock_hook1, mock_hook2, mock_hook3]:
                yield item

        mock_client.list_hooks = Mock(side_effect=lambda **kwargs: async_iter())

        list_hooks = mock_mcp._tools["list_hooks"]
        result = await list_hooks(first_n=2)

        assert result.count == 2
        assert len(result.results) == 2


@pytest.mark.unit
class TestCreateHook:
    """Tests for create_hook tool."""

    @pytest.mark.asyncio
    async def test_create_hook_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful hook creation."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.hooks import register_hook_tools

        register_hook_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=200, name="New Hook", type="function")
        mock_client.create_new_hook.return_value = mock_hook

        create_hook = mock_mcp._tools["create_hook"]
        result = await create_hook(name="New Hook", type="function")

        assert result.id == 200
        assert result.name == "New Hook"

    @pytest.mark.asyncio
    async def test_create_hook_with_config(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test hook creation with configuration."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.hooks import register_hook_tools

        register_hook_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=200, name="Configured Hook")
        mock_client.create_new_hook.return_value = mock_hook

        create_hook = mock_mcp._tools["create_hook"]
        result = await create_hook(
            name="Configured Hook",
            type="function",
            config={"source": "def rossum_hook(): pass", "runtime": "python3.12"},
            events=["annotation_content.initialize"],
            queues=["https://api.test.rossum.ai/v1/queues/1"],
        )

        assert result.id == 200
        mock_client.create_new_hook.assert_called_once()
        call_args = mock_client.create_new_hook.call_args[0][0]
        assert call_args["name"] == "Configured Hook"
        assert "function" in call_args["config"]  # source converted to function

    @pytest.mark.asyncio
    async def test_create_hook_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_hook is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")

        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        from rossum_mcp.tools.hooks import register_hook_tools

        register_hook_tools(mock_mcp, mock_client)

        create_hook = mock_mcp._tools["create_hook"]
        result = await create_hook(name="New Hook", type="function")

        assert result["error"] == "create_hook is not available in read-only mode"
        mock_client.create_new_hook.assert_not_called()
