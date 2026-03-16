"""Tests for rossum_mcp.tools.update.rules module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from fastmcp.exceptions import ToolError
from rossum_api.models.rule import Rule
from rossum_mcp.tools.update.handler import register_update_tools


def create_mock_rule(**kwargs) -> Rule:
    """Create a mock Rule dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/rules/1",
        "name": "Test Rule",
        "enabled": True,
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "schema": "https://api.test.rossum.ai/v1/schemas/1",
        "trigger_condition": "True",
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
class TestPatchRule:
    """Tests for patch_rule tool."""

    @pytest.mark.asyncio
    async def test_patch_rule_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful rule patch (PATCH)."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        updated_rule = create_mock_rule(id=123, name="Patched Name", enabled=True)
        mock_client.update_part_rule.return_value = updated_rule

        patch_rule = mock_mcp._tools["patch_rule"]
        result = await patch_rule(rule_id=123, name="Patched Name")

        assert result.id == 123
        assert result.name == "Patched Name"
        mock_client.update_part_rule.assert_called_once_with(123, {"name": "Patched Name"})

    @pytest.mark.asyncio
    async def test_patch_rule_multiple_fields(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test patching multiple fields at once."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        updated_rule = create_mock_rule(id=123, enabled=False, trigger_condition="field.x > 0")
        mock_client.update_part_rule.return_value = updated_rule

        patch_rule = mock_mcp._tools["patch_rule"]
        result = await patch_rule(rule_id=123, enabled=False, trigger_condition="field.x > 0")

        assert result.enabled is False
        mock_client.update_part_rule.assert_called_once_with(
            123, {"trigger_condition": "field.x > 0", "enabled": False}
        )

    @pytest.mark.asyncio
    async def test_patch_rule_no_fields(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test patch_rule with no fields returns error."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        patch_rule = mock_mcp._tools["patch_rule"]
        with pytest.raises(ToolError, match="No fields provided to update"):
            await patch_rule(rule_id=123)

        mock_client.update_part_rule.assert_not_called()

    @pytest.mark.asyncio
    async def test_patch_rule_with_queue_ids(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test patching rule with queue_ids."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        updated_rule = create_mock_rule(id=123)
        mock_client.update_part_rule.return_value = updated_rule

        patch_rule = mock_mcp._tools["patch_rule"]
        await patch_rule(rule_id=123, queue_ids=[201, 202])

        mock_client.update_part_rule.assert_called_once_with(
            123,
            {
                "queues": [
                    "https://api.test.rossum.ai/v1/queues/201",
                    "https://api.test.rossum.ai/v1/queues/202",
                ]
            },
        )

    @pytest.mark.asyncio
    async def test_patch_rule_clear_queues(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test clearing rule queues with empty list."""
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        updated_rule = create_mock_rule(id=123)
        mock_client.update_part_rule.return_value = updated_rule

        patch_rule = mock_mcp._tools["patch_rule"]
        await patch_rule(rule_id=123, queue_ids=[])

        mock_client.update_part_rule.assert_called_once_with(123, {"queues": []})
