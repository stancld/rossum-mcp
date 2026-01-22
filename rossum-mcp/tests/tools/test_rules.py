"""Tests for rossum_mcp.tools.rules module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.rule import Rule
from rossum_mcp.tools import base

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def create_mock_rule(**kwargs) -> Rule:
    """Create a mock Rule dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/rules/1",
        "name": "Test Rule",
        "enabled": True,
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "schema": "https://api.test.rossum.ai/v1/schemas/1",
        "trigger_condition": {},
        "created_by": "https://api.test.rossum.ai/v1/users/1",
        "created_at": "2025-01-01T00:00:00Z",
        "modified_by": None,
        "modified_at": "2025-01-01T00:00:00Z",
        "rule_template": None,
        "synchronized_from_template": False,
        "actions": [],
    }
    defaults.update(kwargs)
    return Rule(**defaults)


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
class TestGetRule:
    """Tests for get_rule tool."""

    @pytest.mark.asyncio
    async def test_get_rule_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful rule retrieval."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        mock_rule = create_mock_rule(id=123, name="Validation Rule", enabled=True)
        mock_client.retrieve_rule.return_value = mock_rule

        get_rule = mock_mcp._tools["get_rule"]
        result = await get_rule(rule_id=123)

        assert result.id == 123
        assert result.name == "Validation Rule"
        assert result.enabled is True
        mock_client.retrieve_rule.assert_called_once_with(123)


@pytest.mark.unit
class TestListRules:
    """Tests for list_rules tool."""

    @pytest.mark.asyncio
    async def test_list_rules_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful rules listing."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        mock_rule1 = create_mock_rule(id=1, name="Rule 1")
        mock_rule2 = create_mock_rule(id=2, name="Rule 2")

        async def async_iter():
            for item in [mock_rule1, mock_rule2]:
                yield item

        mock_client.list_rules = Mock(side_effect=lambda **kwargs: async_iter())

        list_rules = mock_mcp._tools["list_rules"]
        result = await list_rules()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_rules_with_schema_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test rules listing filtered by schema."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        mock_rule = create_mock_rule(id=1, name="Schema Rule")

        async def async_iter():
            yield mock_rule

        mock_client.list_rules = Mock(side_effect=lambda **kwargs: async_iter())

        list_rules = mock_mcp._tools["list_rules"]
        result = await list_rules(schema_id=50)

        assert len(result) == 1
        mock_client.list_rules.assert_called_once_with(schema=50)

    @pytest.mark.asyncio
    async def test_list_rules_with_organization_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test rules listing filtered by organization."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        mock_rule = create_mock_rule(id=1, name="Org Rule")

        async def async_iter():
            yield mock_rule

        mock_client.list_rules = Mock(side_effect=lambda **kwargs: async_iter())

        list_rules = mock_mcp._tools["list_rules"]
        result = await list_rules(organization_id=100)

        assert len(result) == 1
        mock_client.list_rules.assert_called_once_with(organization=100)

    @pytest.mark.asyncio
    async def test_list_rules_with_enabled_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test rules listing filtered by enabled status."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        mock_rule = create_mock_rule(id=1, enabled=True)

        async def async_iter():
            yield mock_rule

        mock_client.list_rules = Mock(side_effect=lambda **kwargs: async_iter())

        list_rules = mock_mcp._tools["list_rules"]
        result = await list_rules(enabled=True)

        assert len(result) == 1
        mock_client.list_rules.assert_called_once_with(enabled=True)

    @pytest.mark.asyncio
    async def test_list_rules_empty(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test rules listing when none exist."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        async def async_iter():
            return
            yield

        mock_client.list_rules = Mock(side_effect=lambda **kwargs: async_iter())

        list_rules = mock_mcp._tools["list_rules"]
        result = await list_rules()

        assert len(result) == 0
        assert result == []


@pytest.mark.unit
class TestDeleteRule:
    """Tests for delete_rule tool."""

    @pytest.mark.asyncio
    async def test_delete_rule_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful rule deletion."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        mock_client.delete_rule.return_value = None

        delete_rule = mock_mcp._tools["delete_rule"]
        result = await delete_rule(rule_id=123)

        assert "deleted successfully" in result["message"]
        assert "123" in result["message"]
        mock_client.delete_rule.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_delete_rule_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test delete_rule is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        delete_rule = mock_mcp._tools["delete_rule"]
        result = await delete_rule(rule_id=123)

        assert result["error"] == "delete_rule is not available in read-only mode"
        mock_client.delete_rule.assert_not_called()
