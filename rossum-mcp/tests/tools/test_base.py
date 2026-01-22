"""Tests for rossum_mcp.tools.base module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.mark.unit
class TestBuildResourceUrl:
    """Tests for build_resource_url function."""

    def test_build_resource_url_with_base_url(self, monkeypatch: MonkeyPatch) -> None:
        """Test building resource URL with configured base URL."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        result = base.build_resource_url("queues", 123)
        assert result == "https://api.test.rossum.ai/v1/queues/123"

    def test_build_resource_url_different_resources(self, monkeypatch: MonkeyPatch) -> None:
        """Test building URLs for different resource types."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        assert base.build_resource_url("schemas", 456) == "https://api.test.rossum.ai/v1/schemas/456"
        assert base.build_resource_url("workspaces", 789) == "https://api.test.rossum.ai/v1/workspaces/789"
        assert base.build_resource_url("engines", 1) == "https://api.test.rossum.ai/v1/engines/1"


@pytest.mark.unit
class TestIsReadWriteMode:
    """Tests for is_read_write_mode function."""

    def test_read_write_mode_default(self, monkeypatch: MonkeyPatch) -> None:
        """Test that default mode is read-write."""
        monkeypatch.delenv("ROSSUM_MCP_MODE", raising=False)
        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        assert base.is_read_write_mode() is True

    def test_read_write_mode_explicit(self, monkeypatch: MonkeyPatch) -> None:
        """Test explicit read-write mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        assert base.is_read_write_mode() is True

    def test_read_only_mode(self, monkeypatch: MonkeyPatch) -> None:
        """Test read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        assert base.is_read_write_mode() is False

    def test_read_write_mode_case_insensitive(self, monkeypatch: MonkeyPatch) -> None:
        """Test that mode check is case-insensitive."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "READ-WRITE")
        from rossum_mcp.tools import base

        importlib.reload(base)

        assert base.is_read_write_mode() is True


@pytest.mark.unit
class TestDeleteResource:
    """Tests for delete_resource function."""

    @pytest.mark.asyncio
    async def test_delete_resource_success(self, monkeypatch: MonkeyPatch) -> None:
        """Test successful resource deletion."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        from rossum_mcp.tools import base

        importlib.reload(base)

        mock_delete_fn = AsyncMock()
        result = await base.delete_resource("queue", 123, mock_delete_fn)

        assert result == {"message": "Queue 123 deleted successfully"}
        mock_delete_fn.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_delete_resource_custom_message(self, monkeypatch: MonkeyPatch) -> None:
        """Test deletion with custom success message."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        from rossum_mcp.tools import base

        importlib.reload(base)

        mock_delete_fn = AsyncMock()
        result = await base.delete_resource("queue", 123, mock_delete_fn, "Queue 123 scheduled for deletion")

        assert result == {"message": "Queue 123 scheduled for deletion"}

    @pytest.mark.asyncio
    async def test_delete_resource_read_only_mode(self, monkeypatch: MonkeyPatch) -> None:
        """Test deletion is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        from rossum_mcp.tools import base

        importlib.reload(base)

        mock_delete_fn = AsyncMock()
        result = await base.delete_resource("queue", 123, mock_delete_fn)

        assert result == {"error": "delete_queue is not available in read-only mode"}
        mock_delete_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_resource_propagates_exception(self, monkeypatch: MonkeyPatch) -> None:
        """Test that API exceptions are propagated."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        from rossum_mcp.tools import base

        importlib.reload(base)

        mock_delete_fn = AsyncMock(side_effect=ValueError("Not Found"))
        with pytest.raises(ValueError) as exc_info:
            await base.delete_resource("queue", 99999, mock_delete_fn)

        assert str(exc_info.value) == "Not Found"
