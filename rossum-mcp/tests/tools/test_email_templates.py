"""Tests for rossum_mcp.tools.email_templates module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.email_template import EmailTemplate
from rossum_mcp.tools import base
from rossum_mcp.tools.email_templates import register_email_template_tools

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def create_mock_email_template(**kwargs) -> EmailTemplate:
    """Create a mock EmailTemplate dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/email_templates/1",
        "name": "Test Email Template",
        "queue": "https://api.test.rossum.ai/v1/queues/1",
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "subject": "Test Subject",
        "message": "<p>Test Message</p>",
        "type": "custom",
        "enabled": True,
        "automate": False,
        "triggers": [],
        "to": [],
        "cc": [],
        "bcc": [],
    }
    defaults.update(kwargs)
    return EmailTemplate(**defaults)


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
class TestGetEmailTemplate:
    """Tests for get_email_template tool."""

    @pytest.mark.asyncio
    async def test_get_email_template_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful email template retrieval."""
        register_email_template_tools(mock_mcp, mock_client)

        mock_template = create_mock_email_template(id=123, name="Rejection Email", type="rejection")
        mock_client.retrieve_email_template.return_value = mock_template

        get_email_template = mock_mcp._tools["get_email_template"]
        result = await get_email_template(email_template_id=123)

        assert result.id == 123
        assert result.name == "Rejection Email"
        assert result.type == "rejection"
        mock_client.retrieve_email_template.assert_called_once_with(123)


@pytest.mark.unit
class TestListEmailTemplates:
    """Tests for list_email_templates tool."""

    @pytest.mark.asyncio
    async def test_list_email_templates_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful email templates listing."""
        register_email_template_tools(mock_mcp, mock_client)

        mock_template1 = create_mock_email_template(id=1, name="Template 1")
        mock_template2 = create_mock_email_template(id=2, name="Template 2")

        async def async_iter():
            for item in [mock_template1, mock_template2]:
                yield item

        mock_client.list_email_templates = Mock(side_effect=lambda **kwargs: async_iter())

        list_email_templates = mock_mcp._tools["list_email_templates"]
        result = await list_email_templates()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_email_templates_with_queue_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test email templates listing filtered by queue."""
        register_email_template_tools(mock_mcp, mock_client)

        mock_template = create_mock_email_template(id=1, name="Queue Template")

        async def async_iter():
            yield mock_template

        mock_client.list_email_templates = Mock(side_effect=lambda **kwargs: async_iter())

        list_email_templates = mock_mcp._tools["list_email_templates"]
        result = await list_email_templates(queue_id=100)

        assert len(result) == 1
        mock_client.list_email_templates.assert_called_once_with(queue=100)

    @pytest.mark.asyncio
    async def test_list_email_templates_with_type_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test email templates listing filtered by type."""
        register_email_template_tools(mock_mcp, mock_client)

        mock_template = create_mock_email_template(id=1, type="rejection")

        async def async_iter():
            yield mock_template

        mock_client.list_email_templates = Mock(side_effect=lambda **kwargs: async_iter())

        list_email_templates = mock_mcp._tools["list_email_templates"]
        result = await list_email_templates(type="rejection")

        assert len(result) == 1
        mock_client.list_email_templates.assert_called_once_with(type="rejection")

    @pytest.mark.asyncio
    async def test_list_email_templates_with_name_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test email templates listing filtered by name."""
        register_email_template_tools(mock_mcp, mock_client)

        mock_template = create_mock_email_template(id=1, name="Custom Notification")

        async def async_iter():
            yield mock_template

        mock_client.list_email_templates = Mock(side_effect=lambda **kwargs: async_iter())

        list_email_templates = mock_mcp._tools["list_email_templates"]
        result = await list_email_templates(name="Custom Notification")

        assert len(result) == 1
        mock_client.list_email_templates.assert_called_once_with(name="Custom Notification")

    @pytest.mark.asyncio
    async def test_list_email_templates_with_first_n(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test email templates listing with first_n limit."""
        register_email_template_tools(mock_mcp, mock_client)

        mock_template1 = create_mock_email_template(id=1, name="Template 1")
        mock_template2 = create_mock_email_template(id=2, name="Template 2")
        mock_template3 = create_mock_email_template(id=3, name="Template 3")

        async def async_iter():
            for item in [mock_template1, mock_template2, mock_template3]:
                yield item

        mock_client.list_email_templates = Mock(side_effect=lambda **kwargs: async_iter())

        list_email_templates = mock_mcp._tools["list_email_templates"]
        result = await list_email_templates(first_n=2)

        assert len(result) == 2


@pytest.mark.unit
class TestCreateEmailTemplate:
    """Tests for create_email_template tool."""

    @pytest.mark.asyncio
    async def test_create_email_template_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful email template creation."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        importlib.reload(base)

        register_email_template_tools(mock_mcp, mock_client)

        mock_template = create_mock_email_template(
            id=200, name="New Template", subject="Welcome", message="<p>Hello</p>"
        )
        mock_client.create_new_email_template.return_value = mock_template

        create_email_template = mock_mcp._tools["create_email_template"]
        result = await create_email_template(
            name="New Template",
            queue="https://api.test.rossum.ai/v1/queues/1",
            subject="Welcome",
            message="<p>Hello</p>",
        )

        assert result.id == 200
        assert result.name == "New Template"
        mock_client.create_new_email_template.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_email_template_with_all_fields(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test email template creation with all optional fields."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        importlib.reload(base)

        register_email_template_tools(mock_mcp, mock_client)

        mock_template = create_mock_email_template(id=200, name="Full Template")
        mock_client.create_new_email_template.return_value = mock_template

        create_email_template = mock_mcp._tools["create_email_template"]
        result = await create_email_template(
            name="Full Template",
            queue="https://api.test.rossum.ai/v1/queues/1",
            subject="Subject",
            message="<p>Message</p>",
            type="rejection",
            automate=True,
            to=[{"type": "constant", "value": "recipient@example.com"}],
            cc=[{"type": "annotator", "value": ""}],
            bcc=[{"type": "datapoint", "value": "email_field"}],
            triggers=["https://api.test.rossum.ai/v1/triggers/1"],
        )

        assert result.id == 200
        call_args = mock_client.create_new_email_template.call_args[0][0]
        assert call_args["name"] == "Full Template"
        assert call_args["type"] == "rejection"
        assert call_args["automate"] is True
        assert call_args["to"] == [{"type": "constant", "value": "recipient@example.com"}]
        assert call_args["cc"] == [{"type": "annotator", "value": ""}]
        assert call_args["bcc"] == [{"type": "datapoint", "value": "email_field"}]
        assert call_args["triggers"] == ["https://api.test.rossum.ai/v1/triggers/1"]

    @pytest.mark.asyncio
    async def test_create_email_template_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_email_template is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")

        importlib.reload(base)

        register_email_template_tools(mock_mcp, mock_client)

        create_email_template = mock_mcp._tools["create_email_template"]
        result = await create_email_template(
            name="New Template",
            queue="https://api.test.rossum.ai/v1/queues/1",
            subject="Subject",
            message="Message",
        )

        assert result["error"] == "create_email_template is not available in read-only mode"
        mock_client.create_new_email_template.assert_not_called()
