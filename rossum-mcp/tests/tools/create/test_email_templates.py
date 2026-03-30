"""Tests for rossum_mcp.tools.create.email_templates module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_email_template
from rossum_mcp.tools.create.handler import register_create_tools


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
class TestCreateEmailTemplate:
    """Tests for create_email_template tool."""

    @pytest.mark.asyncio
    async def test_create_email_template_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful email template creation."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_template = create_mock_email_template(
            id=200, name="New Template", subject="Welcome", message="<p>Hello</p>"
        )
        mock_client.create_new_email_template.return_value = mock_template

        create_email_template = mock_mcp._tools["create_email_template"]
        result = await create_email_template(
            name="New Template",
            queue=1,
            subject="Welcome",
            message="<p>Hello</p>",
        )

        assert result.id == 200
        assert result.name == "New Template"
        call_args = mock_client.create_new_email_template.call_args[0][0]
        assert call_args["queue"] == "https://api.test.rossum.ai/v1/queues/1"

    @pytest.mark.asyncio
    async def test_create_email_template_with_all_fields(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test email template creation with all optional fields."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_template = create_mock_email_template(id=200, name="Full Template")
        mock_client.create_new_email_template.return_value = mock_template

        create_email_template = mock_mcp._tools["create_email_template"]
        result = await create_email_template(
            name="Full Template",
            queue=1,
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
