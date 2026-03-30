"""Tests for rossum_mcp.tools.create.rules module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_rule
from rossum_api.models.rule import RuleAction, ShowMessagePayload
from rossum_mcp.tools.create.handler import register_create_tools
from rossum_mcp.tools.validation import actions_to_dicts


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
class TestCreateRule:
    """Tests for create_rule tool."""

    @pytest.mark.asyncio
    async def test_create_rule_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful rule creation."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        test_action = {
            "id": "action1",
            "type": "show_message",
            "event": "validation",
            "payload": {"type": "error", "content": "High value!", "schema_id": "amount"},
        }
        mock_rule = create_mock_rule(
            id=456,
            name="New Validation Rule",
            enabled=True,
            trigger_condition="field.amount > 1000",
            actions=[test_action],
        )
        mock_client.create_new_rule.return_value = mock_rule

        create_rule = mock_mcp._tools["create_rule"]
        result = await create_rule(
            name="New Validation Rule",
            trigger_condition="field.amount > 1000",
            actions=[test_action],
            enabled=True,
            queue_ids=[100],
        )

        assert result.id == 456
        assert result.name == "New Validation Rule"
        assert result.enabled is True
        mock_client.create_new_rule.assert_called_once()

        call_args = mock_client.create_new_rule.call_args[0][0]
        assert call_args["name"] == "New Validation Rule"
        assert call_args["queues"] == ["https://api.test.rossum.ai/v1/queues/100"]
        assert call_args["trigger_condition"] == "field.amount > 1000"
        assert call_args["actions"] == [test_action]
        assert call_args["enabled"] is True

    @pytest.mark.asyncio
    async def test_create_rule_without_queue_ids(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test creating a rule without queue_ids (org-wide)."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_rule = create_mock_rule(id=457, name="Org-wide Rule", enabled=True)
        mock_client.create_new_rule.return_value = mock_rule

        create_rule = mock_mcp._tools["create_rule"]
        result = await create_rule(
            name="Org-wide Rule",
            trigger_condition="field.amount > 500",
            actions=[],
        )

        assert result.id == 457
        call_args = mock_client.create_new_rule.call_args[0][0]
        assert "queues" not in call_args

    @pytest.mark.asyncio
    async def test_create_rule_with_disabled(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test creating a disabled rule."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_rule = create_mock_rule(id=789, name="Disabled Rule", enabled=False)
        mock_client.create_new_rule.return_value = mock_rule

        create_rule = mock_mcp._tools["create_rule"]
        result = await create_rule(
            name="Disabled Rule",
            trigger_condition="field.vendor_name.changed",
            actions=[],
            enabled=False,
        )

        assert result.id == 789
        assert result.enabled is False

        call_args = mock_client.create_new_rule.call_args[0][0]
        assert call_args["enabled"] is False

    @pytest.mark.asyncio
    async def test_create_rule_with_queue_ids(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test creating a rule with queue_ids."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_rule = create_mock_rule(id=999, name="Queue Rule")
        mock_client.create_new_rule.return_value = mock_rule

        create_rule = mock_mcp._tools["create_rule"]
        result = await create_rule(
            name="Queue Rule",
            trigger_condition="True",
            actions=[],
            queue_ids=[101, 102],
        )

        assert result.id == 999
        call_args = mock_client.create_new_rule.call_args[0][0]
        assert call_args["queues"] == [
            "https://api.test.rossum.ai/v1/queues/101",
            "https://api.test.rossum.ai/v1/queues/102",
        ]


@pytest.mark.unit
class TestActionsToDict:
    """Tests for actions_to_dicts helper."""

    def test_converts_dataclass_instances(self) -> None:
        action = RuleAction(
            id="act1",
            type="show_message",
            event="validation",
            payload=ShowMessagePayload(type="error", content="Bad value", schema_id="amount"),
        )
        result = actions_to_dicts([action])

        assert result == [
            {
                "id": "act1",
                "type": "show_message",
                "event": "validation",
                "enabled": True,
                "payload": {"type": "error", "content": "Bad value", "schema_id": "amount"},
            }
        ]

    def test_passes_through_raw_dicts(self) -> None:
        raw = {
            "id": "act1",
            "type": "show_message",
            "event": "validation",
            "payload": {"type": "error", "content": "X"},
        }
        result = actions_to_dicts([raw])

        assert result == [raw]

    def test_handles_mixed_list(self) -> None:
        dataclass_action = RuleAction(
            id="act1",
            type="show_message",
            event="validation",
            payload=ShowMessagePayload(type="info", content="OK"),
        )
        dict_action = {"id": "act2", "type": "custom", "event": "validation", "payload": {}}
        result = actions_to_dicts([dataclass_action, dict_action])

        assert len(result) == 2
        assert result[0] == {
            "id": "act1",
            "type": "show_message",
            "event": "validation",
            "enabled": True,
            "payload": {"type": "info", "content": "OK", "schema_id": None},
        }
        assert result[1] is dict_action
