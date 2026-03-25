"""Tests for rossum_mcp.tools.update.inboxes module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.inbox import Inbox

from rossum_mcp.tools.update.handler import register_update_tools


def create_mock_inbox(**kwargs) -> Inbox:
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/inboxes/1",
        "name": "Test Inbox",
        "queues": ["https://api.test.rossum.ai/v1/queues/10"],
        "email": "test-a1b2c3@example.rossum.app",
        "email_prefix": "test",
        "bounce_email_to": None,
        "bounce_unprocessable_attachments": False,
        "bounce_postponed_annotations": False,
        "bounce_deleted_annotations": False,
        "bounce_email_with_no_attachments": True,
        "metadata": {},
        "filters": {},
        "dmarc_check_action": "accept",
    }
    defaults.update(kwargs)
    return Inbox(**defaults)


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.fixture
def mock_mcp() -> Mock:
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
class TestUpdateInbox:
    @pytest.mark.asyncio
    async def test_update_inbox_name(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        updated_inbox = create_mock_inbox(id=1, name="Renamed Inbox")
        mock_client._http_client.update.return_value = updated_inbox
        mock_client._deserializer.return_value = updated_inbox

        update_inbox = mock_mcp._tools["update_inbox"]
        result = await update_inbox(inbox_id=1, name="Renamed Inbox")

        assert result.name == "Renamed Inbox"
        mock_client._http_client.update.assert_called_once_with(Resource.Inbox, 1, {"name": "Renamed Inbox"})

    @pytest.mark.asyncio
    async def test_update_inbox_dmarc(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        updated_inbox = create_mock_inbox(id=1, dmarc_check_action="drop")
        mock_client._http_client.update.return_value = updated_inbox
        mock_client._deserializer.return_value = updated_inbox

        update_inbox = mock_mcp._tools["update_inbox"]
        await update_inbox(inbox_id=1, dmarc_check_action="drop")

        mock_client._http_client.update.assert_called_once_with(
            Resource.Inbox, 1, {"dmarc_check_action": "drop"}
        )

    @pytest.mark.asyncio
    async def test_update_inbox_excludes_none(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        updated_inbox = create_mock_inbox(id=1)
        mock_client._http_client.update.return_value = updated_inbox
        mock_client._deserializer.return_value = updated_inbox

        update_inbox = mock_mcp._tools["update_inbox"]
        await update_inbox(inbox_id=1, name="Only Name")

        _, _, patch_data = mock_client._http_client.update.call_args[0]
        assert "email_prefix" not in patch_data
        assert "metadata" not in patch_data
