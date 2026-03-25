"""Tests for rossum_mcp.tools.create.inboxes module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.inbox import Inbox

from rossum_mcp.tools.create.handler import register_create_tools


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
class TestCreateInbox:
    @pytest.mark.asyncio
    async def test_create_inbox_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_inbox = create_mock_inbox(id=100, name="Invoice Inbox")
        mock_client.create_new_inbox.return_value = mock_inbox

        create_inbox = mock_mcp._tools["create_inbox"]
        result = await create_inbox(name="Invoice Inbox", queue_id=10)

        assert result.id == 100
        assert result.name == "Invoice Inbox"
        call_args = mock_client.create_new_inbox.call_args[0][0]
        assert call_args["queues"] == ["https://api.test.rossum.ai/v1/queues/10"]

    @pytest.mark.asyncio
    async def test_create_inbox_with_email_prefix(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_inbox = create_mock_inbox(id=101, email_prefix="invoices")
        mock_client.create_new_inbox.return_value = mock_inbox

        create_inbox = mock_mcp._tools["create_inbox"]
        result = await create_inbox(name="Test", queue_id=10, email_prefix="invoices")

        call_args = mock_client.create_new_inbox.call_args[0][0]
        assert call_args["email_prefix"] == "invoices"

    @pytest.mark.asyncio
    async def test_create_inbox_with_dmarc_drop(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_inbox = create_mock_inbox(id=102, dmarc_check_action="drop")
        mock_client.create_new_inbox.return_value = mock_inbox

        create_inbox = mock_mcp._tools["create_inbox"]
        result = await create_inbox(name="Secure Inbox", queue_id=10, dmarc_check_action="drop")

        call_args = mock_client.create_new_inbox.call_args[0][0]
        assert call_args["dmarc_check_action"] == "drop"

    @pytest.mark.asyncio
    async def test_create_inbox_with_metadata(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_inbox = create_mock_inbox(id=103)
        mock_client.create_new_inbox.return_value = mock_inbox

        create_inbox = mock_mcp._tools["create_inbox"]
        await create_inbox(name="Test", queue_id=10, metadata={"region": "eu"})

        call_args = mock_client.create_new_inbox.call_args[0][0]
        assert call_args["metadata"] == {"region": "eu"}
