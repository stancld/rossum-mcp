"""Tests for hook, hook log, and hook template search functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_hook, create_mock_queue
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.hook import HookRunData
from rossum_api.models.hook_template import HookTemplate
from rossum_mcp.tools.search.hooks import (
    _list_hook_logs,
    _list_hook_templates,
    _list_hooks,
    _truncate_hook_template_for_list,
)


def _hook_run_data(**kwargs) -> HookRunData:
    defaults = {
        "log_level": "INFO",
        "action": "initialize",
        "event": "annotation_content",
        "request_id": "req-1",
        "organization_id": 1,
        "hook_id": 1,
        "hook_type": "function",
    }
    defaults.update(kwargs)
    return HookRunData(**defaults)


def _hook_template(**kwargs) -> HookTemplate:
    defaults = {
        "name": "Template 1",
        "url": "https://api.test.rossum.ai/v1/hook_templates/1",
        "description": "A template",
        "sideload": ["queues"],
        "metadata": {"key": "value"},
        "config": {"url": "https://example.com"},
        "test": {"input": "test"},
        "settings": {"opt": True},
        "settings_schema": {"type": "object"},
        "secrets_schema": {"type": "object"},
        "guide": "Some guide text",
        "read_more_url": "https://example.com/docs",
        "extension_image_url": "https://example.com/image.png",
        "settings_description": [{"key": "desc"}],
        "store_description": "Store description",
        "external_url": "https://example.com/ext",
    }
    defaults.update(kwargs)
    return HookTemplate(**defaults)


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.mark.unit
class TestListHooks:
    @pytest.mark.asyncio
    async def test_resolves_workspaces_from_queues(self, mock_client: AsyncMock) -> None:
        hooks = [
            create_mock_hook(
                id=1,
                queues=[
                    "https://api.test.rossum.ai/v1/queues/10",
                    "https://api.test.rossum.ai/v1/queues/20",
                ],
            ),
        ]
        queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
            create_mock_queue(
                id=20,
                url="https://api.test.rossum.ai/v1/queues/20",
                workspace="https://api.test.rossum.ai/v1/workspaces/200",
            ),
        ]

        async def mock_fetch(resource, **filters):
            items = hooks if resource == Resource.Hook else queues
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_hooks(mock_client)

        assert len(result) == 1
        assert sorted(result[0].workspaces) == [
            "https://api.test.rossum.ai/v1/workspaces/100",
            "https://api.test.rossum.ai/v1/workspaces/200",
        ]

    @pytest.mark.asyncio
    async def test_filter_by_workspace_id(self, mock_client: AsyncMock) -> None:
        hooks = [
            create_mock_hook(id=1, queues=["https://api.test.rossum.ai/v1/queues/10"]),
            create_mock_hook(id=2, name="Hook 2", queues=["https://api.test.rossum.ai/v1/queues/20"]),
        ]
        queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
            create_mock_queue(
                id=20,
                url="https://api.test.rossum.ai/v1/queues/20",
                workspace="https://api.test.rossum.ai/v1/workspaces/200",
            ),
        ]

        async def mock_fetch(resource, **filters):
            items = hooks if resource == Resource.Hook else queues
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_hooks(mock_client, workspace_id=100)

        assert len(result) == 1
        assert result[0].id == 1

    @pytest.mark.asyncio
    async def test_empty_queues_yields_no_workspaces(self, mock_client: AsyncMock) -> None:
        hooks = [create_mock_hook(id=1, queues=[])]

        async def mock_fetch(resource, **filters):
            for h in hooks:
                yield h

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_hooks(mock_client)

        assert len(result) == 1
        assert result[0].workspaces == []


@pytest.mark.unit
class TestListHookLogs:
    @pytest.mark.asyncio
    async def test_returns_logs(self, mock_client: AsyncMock) -> None:
        logs = [_hook_run_data(hook_id=1), _hook_run_data(hook_id=2)]

        async def mock_fetch(resource, **filters):
            for log in logs:
                yield log

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_hook_logs(mock_client)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_log_level_list_joined(self, mock_client: AsyncMock) -> None:
        """Multiple log levels are joined into a comma-separated string for the API."""
        captured_filters: dict = {}

        async def mock_fetch(resource, **filters):
            captured_filters.update(filters)
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_fetch

        await _list_hook_logs(mock_client, log_level=["INFO", "ERROR"])

        assert captured_filters["log_level"] == "INFO,ERROR"

    @pytest.mark.asyncio
    async def test_single_log_level_passed_as_is(self, mock_client: AsyncMock) -> None:
        captured_filters: dict = {}

        async def mock_fetch(resource, **filters):
            captured_filters.update(filters)
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_fetch

        await _list_hook_logs(mock_client, log_level="ERROR")

        assert captured_filters["log_level"] == "ERROR"


@pytest.mark.unit
class TestTruncateHookTemplate:
    def test_clears_large_fields(self) -> None:
        template = _hook_template()
        truncated = _truncate_hook_template_for_list(template)

        assert truncated.sideload == []
        assert truncated.metadata == {}
        assert truncated.config == {}
        assert truncated.test == {}
        assert truncated.settings == {}
        assert truncated.settings_schema is None
        assert truncated.secrets_schema is None
        assert truncated.guide is None
        assert truncated.read_more_url is None
        assert truncated.extension_image_url is None
        assert truncated.settings_description == []
        assert truncated.store_description is None
        assert truncated.external_url is None

    def test_preserves_browsing_fields(self) -> None:
        template = _hook_template(name="My Template", description="Useful hook")
        truncated = _truncate_hook_template_for_list(template)

        assert truncated.name == "My Template"
        assert truncated.url == template.url
        assert truncated.description == "Useful hook"


@pytest.mark.unit
class TestListHookTemplates:
    @pytest.mark.asyncio
    async def test_returns_truncated_templates(self, mock_client: AsyncMock) -> None:
        templates = [_hook_template(name="T1"), _hook_template(name="T2")]

        async def mock_fetch(resource, **filters):
            for t in templates:
                yield t

        mock_client._http_client.cursor_fetch_all = mock_fetch

        result = await _list_hook_templates(mock_client)

        assert len(result) == 2
        assert all(t.config == {} for t in result)
        assert all(t.guide is None for t in result)
