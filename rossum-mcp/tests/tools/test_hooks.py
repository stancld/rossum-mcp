"""Tests for rossum_mcp.tools.hooks module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_hook
from rossum_mcp.tools import base
from rossum_mcp.tools.hooks import register_hook_tools

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


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
        register_hook_tools(mock_mcp, mock_client)

        mock_hook1 = create_mock_hook(id=1, name="Hook 1")
        mock_hook2 = create_mock_hook(id=2, name="Hook 2")

        async def async_iter():
            for item in [mock_hook1, mock_hook2]:
                yield item

        mock_client.list_hooks = Mock(side_effect=lambda **kwargs: async_iter())

        list_hooks = mock_mcp._tools["list_hooks"]
        result = await list_hooks()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_hooks_with_queue_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test hooks listing filtered by queue."""
        register_hook_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=1, name="Queue Hook")

        async def async_iter():
            yield mock_hook

        mock_client.list_hooks = Mock(side_effect=lambda **kwargs: async_iter())

        list_hooks = mock_mcp._tools["list_hooks"]
        result = await list_hooks(queue_id=100)

        assert len(result) == 1
        mock_client.list_hooks.assert_called_once_with(queue=100)

    @pytest.mark.asyncio
    async def test_list_hooks_with_active_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test hooks listing filtered by active status."""
        register_hook_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=1, active=True)

        async def async_iter():
            yield mock_hook

        mock_client.list_hooks = Mock(side_effect=lambda **kwargs: async_iter())

        list_hooks = mock_mcp._tools["list_hooks"]
        result = await list_hooks(active=True)

        assert len(result) == 1
        mock_client.list_hooks.assert_called_once_with(active=True)

    @pytest.mark.asyncio
    async def test_list_hooks_with_first_n(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test hooks listing with first_n limit."""
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

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_hooks_with_first_n_greater_than_available(
        self, mock_mcp: Mock, mock_client: AsyncMock
    ) -> None:
        """Test hooks listing when first_n exceeds available items (should not crash)."""
        register_hook_tools(mock_mcp, mock_client)

        mock_hook1 = create_mock_hook(id=1, name="Hook 1")

        async def async_iter():
            yield mock_hook1

        mock_client.list_hooks = Mock(side_effect=lambda **kwargs: async_iter())

        list_hooks = mock_mcp._tools["list_hooks"]
        result = await list_hooks(first_n=10)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_hooks_with_first_n_empty_result(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test hooks listing when no hooks exist but first_n is specified."""
        register_hook_tools(mock_mcp, mock_client)

        async def async_iter():
            return
            yield

        mock_client.list_hooks = Mock(side_effect=lambda **kwargs: async_iter())

        list_hooks = mock_mcp._tools["list_hooks"]
        result = await list_hooks(first_n=5)

        assert len(result) == 0


@pytest.mark.unit
class TestCreateHook:
    """Tests for create_hook tool."""

    @pytest.mark.asyncio
    async def test_create_hook_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful hook creation."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        importlib.reload(base)

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

        importlib.reload(base)

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

        importlib.reload(base)

        register_hook_tools(mock_mcp, mock_client)

        create_hook = mock_mcp._tools["create_hook"]
        result = await create_hook(name="New Hook", type="function")

        assert result["error"] == "create_hook is not available in read-only mode"
        mock_client.create_new_hook.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_hook_with_settings_secret_timeout(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test hook creation with settings, secret, and timeout_s capping."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        importlib.reload(base)

        register_hook_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=201, name="Full Config Hook")
        mock_client.create_new_hook.return_value = mock_hook

        create_hook = mock_mcp._tools["create_hook"]
        result = await create_hook(
            name="Full Config Hook",
            type="function",
            config={"timeout_s": 120},
            settings={"key": "value"},
            secret="my-secret",
        )

        assert result.id == 201
        call_args = mock_client.create_new_hook.call_args[0][0]
        assert call_args["config"]["timeout_s"] == 60  # capped at 60
        assert call_args["settings"] == {"key": "value"}
        assert call_args["secret"] == "my-secret"


@pytest.mark.unit
class TestCreateHookFromTemplate:
    """Tests for create_hook_from_template tool."""

    @pytest.mark.asyncio
    async def test_create_hook_from_template_webhook_with_external_url(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test creating a hook from template via hooks/create endpoint."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        importlib.reload(base)

        register_hook_tools(mock_mcp, mock_client)

        # Mock the HTTP client for hooks/create POST and the base_url property
        mock_http_client = AsyncMock()
        mock_http_client.base_url = "https://api.test.rossum.ai/v1"
        mock_http_client.request_json.return_value = {"id": 300}
        mock_client._http_client = mock_http_client

        mock_hook = create_mock_hook(id=300, name="Template Hook")
        mock_client.retrieve_hook.return_value = mock_hook

        create_hook_from_template = mock_mcp._tools["create_hook_from_template"]
        result = await create_hook_from_template(
            name="My Webhook Hook",
            hook_template_id=5,
            queues=["https://api.test.rossum.ai/v1/queues/1"],
            events=["annotation_content.initialize"],
        )

        assert result.id == 300
        mock_http_client.request_json.assert_called_once_with(
            "POST",
            "hooks/create",
            json={
                "name": "My Webhook Hook",
                "hook_template": "https://api.test.rossum.ai/v1/hook_templates/5",
                "queues": ["https://api.test.rossum.ai/v1/queues/1"],
                "events": ["annotation_content.initialize"],
            },
        )
        mock_client.retrieve_hook.assert_called_once_with(300)

    @pytest.mark.asyncio
    async def test_create_hook_from_template_missing_hook_id(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test error handling when API response doesn't contain hook ID."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        importlib.reload(base)

        register_hook_tools(mock_mcp, mock_client)

        # Mock the HTTP client - API returns response without id
        mock_http_client = AsyncMock()
        mock_http_client.base_url = "https://api.test.rossum.ai/v1"
        mock_http_client.request_json.return_value = {}
        mock_client._http_client = mock_http_client

        create_hook_from_template = mock_mcp._tools["create_hook_from_template"]
        result = await create_hook_from_template(
            name="My Webhook Hook",
            hook_template_id=5,
            queues=["https://api.test.rossum.ai/v1/queues/1"],
            events=["annotation_content.initialize"],
        )

        assert "error" in result
        assert "Hook wasn't likely created" in result["error"]
        mock_client.retrieve_hook.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_hook_from_template_with_token_owner(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test creating a hook from template with token_owner parameter."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        importlib.reload(base)

        register_hook_tools(mock_mcp, mock_client)

        # Mock the HTTP client for hooks/create POST
        mock_http_client = AsyncMock()
        mock_http_client.base_url = "https://api.test.rossum.ai/v1"
        mock_http_client.request_json.return_value = {"id": 400}
        mock_client._http_client = mock_http_client

        mock_hook = create_mock_hook(id=400, name="Function Template Hook")
        mock_client.retrieve_hook.return_value = mock_hook

        create_hook_from_template = mock_mcp._tools["create_hook_from_template"]
        result = await create_hook_from_template(
            name="My Function Hook",
            hook_template_id=10,
            queues=["https://api.test.rossum.ai/v1/queues/1"],
            events=["annotation_content.initialize"],
            token_owner="https://api.test.rossum.ai/v1/users/42",
        )

        assert result.id == 400
        mock_http_client.request_json.assert_called_once_with(
            "POST",
            "hooks/create",
            json={
                "name": "My Function Hook",
                "hook_template": "https://api.test.rossum.ai/v1/hook_templates/10",
                "queues": ["https://api.test.rossum.ai/v1/queues/1"],
                "events": ["annotation_content.initialize"],
                "token_owner": "https://api.test.rossum.ai/v1/users/42",
            },
        )
        mock_client.retrieve_hook.assert_called_once_with(400)

    @pytest.mark.asyncio
    async def test_create_hook_from_template_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_hook_from_template is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")

        importlib.reload(base)

        register_hook_tools(mock_mcp, mock_client)

        create_hook_from_template = mock_mcp._tools["create_hook_from_template"]
        result = await create_hook_from_template(
            name="My Hook",
            hook_template_id=5,
            queues=["https://api.test.rossum.ai/v1/queues/1"],
            events=["annotation_content.initialize"],
        )

        assert result["error"] == "create_hook_from_template is not available in read-only mode"
        mock_client.create_new_hook.assert_not_called()


@pytest.mark.unit
class TestUpdateHook:
    """Tests for update_hook tool."""

    @pytest.mark.asyncio
    async def test_update_hook_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful hook update."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        importlib.reload(base)

        register_hook_tools(mock_mcp, mock_client)

        existing_hook = create_mock_hook(
            id=100,
            name="Old Name",
            queues=["https://api.test.rossum.ai/v1/queues/1"],
            events=["annotation_content.initialize"],
            config={"runtime": "python3.12"},
        )
        mock_client.retrieve_hook.return_value = existing_hook

        updated_hook = create_mock_hook(id=100, name="New Name")
        mock_client.update_part_hook.return_value = updated_hook

        update_hook = mock_mcp._tools["update_hook"]
        result = await update_hook(hook_id=100, name="New Name")

        assert result.id == 100
        assert result.name == "New Name"
        mock_client.retrieve_hook.assert_called_once_with(100)
        mock_client.update_part_hook.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_hook_with_all_fields(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test hook update with all optional fields."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        importlib.reload(base)

        register_hook_tools(mock_mcp, mock_client)

        existing_hook = create_mock_hook(id=100, name="Old Name", config=None)
        mock_client.retrieve_hook.return_value = existing_hook

        updated_hook = create_mock_hook(id=100, name="Updated")
        mock_client.update_part_hook.return_value = updated_hook

        update_hook = mock_mcp._tools["update_hook"]
        result = await update_hook(
            hook_id=100,
            name="Updated",
            queues=["https://api.test.rossum.ai/v1/queues/2"],
            events=["annotation_content.export"],
            config={"new": "config"},
            settings={"setting": "value"},
            active=False,
        )

        assert result.id == 100
        call_args = mock_client.update_part_hook.call_args[0][1]
        assert call_args["name"] == "Updated"
        assert call_args["queues"] == ["https://api.test.rossum.ai/v1/queues/2"]
        assert call_args["events"] == ["annotation_content.export"]
        assert call_args["config"] == {"new": "config"}
        assert call_args["settings"] == {"setting": "value"}
        assert call_args["active"] is False

    @pytest.mark.asyncio
    async def test_update_hook_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test update_hook is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")

        importlib.reload(base)

        register_hook_tools(mock_mcp, mock_client)

        update_hook = mock_mcp._tools["update_hook"]
        result = await update_hook(hook_id=100, name="New Name")

        assert result["error"] == "update_hook is not available in read-only mode"
        mock_client.update_part_hook.assert_not_called()


@pytest.mark.unit
class TestListHookLogs:
    """Tests for list_hook_logs tool."""

    @pytest.mark.asyncio
    async def test_list_hook_logs_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful hook logs listing."""
        register_hook_tools(mock_mcp, mock_client)

        mock_log = Mock()
        mock_log.id = 1

        async def async_iter():
            yield mock_log

        mock_client.list_hook_run_data = Mock(side_effect=lambda **kwargs: async_iter())

        list_hook_logs = mock_mcp._tools["list_hook_logs"]
        result = await list_hook_logs(hook_id=123)

        assert len(result) == 1
        mock_client.list_hook_run_data.assert_called_once_with(hook=123)

    @pytest.mark.asyncio
    async def test_list_hook_logs_with_filters(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test hook logs listing with multiple filters."""
        register_hook_tools(mock_mcp, mock_client)

        async def async_iter():
            return
            yield

        mock_client.list_hook_run_data = Mock(side_effect=lambda **kwargs: async_iter())

        list_hook_logs = mock_mcp._tools["list_hook_logs"]
        result = await list_hook_logs(
            hook_id=123, queue_id=456, log_level="ERROR", timestamp_after="2024-01-15T10:30:00Z", page_size=50
        )

        assert result == []
        mock_client.list_hook_run_data.assert_called_once_with(
            hook=123, queue=456, log_level="ERROR", timestamp_after="2024-01-15T10:30:00Z", page_size=50
        )


@pytest.mark.unit
class TestListHookTemplates:
    """Tests for list_hook_templates tool."""

    @pytest.mark.asyncio
    async def test_list_hook_templates_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful hook templates listing."""
        register_hook_tools(mock_mcp, mock_client)

        template_data = [
            {
                "url": "https://api.test.rossum.ai/v1/hook_templates/1",
                "name": "Validation Template",
                "description": "Validates data",
                "type": "function",
                "events": ["annotation_content.initialize"],
                "config": {"code": "..."},
                "settings_schema": {"type": "object"},
                "guide": "Some guide",
                "use_token_owner": False,
            },
            {
                "url": "https://api.test.rossum.ai/v1/hook_templates/2",
                "name": "Webhook Template",
                "type": "webhook",
                "events": ["annotation_status.changed"],
                "config": {},
                "use_token_owner": True,
            },
        ]

        async def async_iter():
            for item in template_data:
                yield item

        mock_client.request_paginated = Mock(side_effect=lambda *args: async_iter())

        list_hook_templates = mock_mcp._tools["list_hook_templates"]
        result = await list_hook_templates()

        assert len(result) == 2
        assert result[0].id == 1
        assert result[0].name == "Validation Template"
        assert result[0].description == "Validates data"
        assert result[0].settings_schema == {"type": "object"}
        assert result[0].use_token_owner is False
        assert result[0].guide == "<omitted>"  # guide is truncated to save context
        assert result[1].id == 2
        assert result[1].name == "Webhook Template"
        assert result[1].description == ""  # default
        assert result[1].use_token_owner is True
        mock_client.request_paginated.assert_called_once_with("hook_templates")


@pytest.mark.unit
class TestDeleteHook:
    """Tests for delete_hook tool."""

    @pytest.mark.asyncio
    async def test_delete_hook_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful hook deletion."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_hook_tools(mock_mcp, mock_client)

        mock_client.delete_hook.return_value = None

        delete_hook = mock_mcp._tools["delete_hook"]
        result = await delete_hook(hook_id=123)

        assert "deleted successfully" in result["message"]
        assert "123" in result["message"]
        mock_client.delete_hook.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_delete_hook_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test delete_hook is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        register_hook_tools(mock_mcp, mock_client)

        delete_hook = mock_mcp._tools["delete_hook"]
        result = await delete_hook(hook_id=123)

        assert result["error"] == "delete_hook is not available in read-only mode"
        mock_client.delete_hook.assert_not_called()
