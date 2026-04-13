"""Tests for rossum_mcp.server module."""

from __future__ import annotations

import pytest
from rossum_mcp.logging_config import LogFormat, LogLevel
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
        assert config.log_format == LogFormat.CONSOLE

    @pytest.mark.parametrize(
        ("env_var", "value", "attr", "expected"),
        [
            ("ROSSUM_MCP_MODE", "read-only", "mode", MCPMode.READ_ONLY),
            ("ROSSUM_MCP_MODE", "READ-ONLY", "mode", MCPMode.READ_ONLY),
            ("ROSSUM_MCP_LOG_LEVEL", "DEBUG", "log_level", LogLevel.DEBUG),
            ("ROSSUM_MCP_LOG_LEVEL", "debug", "log_level", LogLevel.DEBUG),
            ("ROSSUM_MCP_LOG_FORMAT", "json", "log_format", LogFormat.JSON),
            ("ROSSUM_MCP_LOG_FORMAT", "JSON", "log_format", LogFormat.JSON),
            ("ROSSUM_MCP_LOG_FORMAT", "console", "log_format", LogFormat.CONSOLE),
        ],
    )
    def test_reads_optional_env_var(
        self, monkeypatch: pytest.MonkeyPatch, env_var: str, value: str, attr: str, expected
    ):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")
        monkeypatch.setenv(env_var, value)

        config = RossumMCPServer.Config.from_env()

        assert getattr(config, attr) == expected

    @pytest.mark.parametrize("missing_var", ["ROSSUM_API_BASE_URL", "ROSSUM_API_TOKEN"])
    def test_missing_required_env_var_raises(self, monkeypatch: pytest.MonkeyPatch, missing_var: str):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")
        monkeypatch.delenv(missing_var, raising=False)

        with pytest.raises(KeyError, match=missing_var):
            RossumMCPServer.Config.from_env()

    @pytest.mark.parametrize(
        ("env_var", "value"),
        [
            ("ROSSUM_MCP_MODE", "bogus"),
            ("ROSSUM_MCP_LOG_LEVEL", "BOGUS"),
            ("ROSSUM_MCP_LOG_FORMAT", "yaml"),
        ],
    )
    def test_invalid_optional_env_var_raises(self, monkeypatch: pytest.MonkeyPatch, env_var: str, value: str):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")
        monkeypatch.setenv(env_var, value)

        with pytest.raises(ValueError, match=value):
            RossumMCPServer.Config.from_env()

    def test_strips_trailing_slash_from_base_url(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1/")
        monkeypatch.setenv("ROSSUM_API_TOKEN", "tok_123")

        config = RossumMCPServer.Config.from_env()

        assert config.base_url == "https://example.rossum.app/api/v1"
