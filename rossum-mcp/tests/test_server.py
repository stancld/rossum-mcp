"""Tests for rossum_mcp.server module."""

from __future__ import annotations

import pytest
from rossum_mcp.logging_config import LogLevel
from rossum_mcp.server import RossumMCPServer
from rossum_mcp.tools.base import MCPMode


class TestConfigFromEnv:
    """Tests for RossumMCPServer.Config.from_env()."""

    def test_reads_required_env_vars(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1/")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")

        config = RossumMCPServer.Config.from_env()

        assert config.base_url == "https://example.rossum.app/api/v1"
        assert config.api_token == "tok_123"

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")

        config = RossumMCPServer.Config.from_env()

        assert config.mode == MCPMode.READ_WRITE
        assert config.log_level == LogLevel.INFO

    def test_reads_optional_mode(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")

        config = RossumMCPServer.Config.from_env()

        assert config.mode == MCPMode.READ_ONLY

    def test_reads_optional_log_level(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")
        monkeypatch.setenv("ROSSUM_MCP_LOG_LEVEL", "DEBUG")

        config = RossumMCPServer.Config.from_env()

        assert config.log_level == LogLevel.DEBUG

    def test_missing_base_url_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("ROSSUM_API_BASE_URL", raising=False)
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")

        with pytest.raises(KeyError, match="ROSSUM_API_BASE_URL"):
            RossumMCPServer.Config.from_env()

    def test_missing_api_token_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        monkeypatch.delenv("ROSSUM_API_TOKEN", raising=False)

        with pytest.raises(KeyError, match="ROSSUM_API_TOKEN"):
            RossumMCPServer.Config.from_env()

    def test_invalid_mode_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "bogus")

        with pytest.raises(ValueError, match="bogus"):
            RossumMCPServer.Config.from_env()

    def test_invalid_log_level_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")
        monkeypatch.setenv("ROSSUM_MCP_LOG_LEVEL", "BOGUS")

        with pytest.raises(ValueError, match="BOGUS"):
            RossumMCPServer.Config.from_env()

    def test_mode_is_case_insensitive(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "READ-ONLY")

        config = RossumMCPServer.Config.from_env()

        assert config.mode == MCPMode.READ_ONLY

    def test_log_level_is_case_insensitive(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")
        monkeypatch.setenv("ROSSUM_MCP_LOG_LEVEL", "debug")

        config = RossumMCPServer.Config.from_env()

        assert config.log_level == LogLevel.DEBUG

    def test_strips_trailing_slash_from_base_url(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1/")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")

        config = RossumMCPServer.Config.from_env()

        assert config.base_url == "https://example.rossum.app/api/v1"
