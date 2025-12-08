"""Tests for rossum_mcp.tools.base module."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
        import importlib

        from rossum_mcp.tools import base

        importlib.reload(base)

        assert base.is_read_write_mode() is True
