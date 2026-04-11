from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from fastmcp import FastMCP
from rossum_api import AsyncRossumAPIClient
from rossum_api.dtos import Token

from rossum_mcp import __version__
from rossum_mcp.logging_config import LogFormat, LogLevel, setup_logging
from rossum_mcp.middleware import ObservabilityMiddleware
from rossum_mcp.tools import (
    register_create_tools,
    register_delete_tools,
    register_discovery_tools,
    register_get_tools,
    register_search_tools,
    register_update_tools,
)
from rossum_mcp.tools.base import MCPMode

logger = logging.getLogger(__name__)


class RossumMCPServer:
    @dataclass(frozen=True)
    class Config:
        base_url: str
        api_token: str
        mode: MCPMode = MCPMode.READ_WRITE
        log_level: LogLevel = LogLevel.INFO
        log_format: LogFormat = LogFormat.CONSOLE

        @classmethod
        def from_env(cls) -> RossumMCPServer.Config:
            return cls(
                base_url=os.environ["ROSSUM_API_BASE_URL"].rstrip("/"),
                api_token=os.environ["ROSSUM_API_TOKEN"],
                mode=MCPMode(os.environ.get("ROSSUM_MCP_MODE", "read-write").lower()),
                log_level=LogLevel(os.environ.get("ROSSUM_MCP_LOG_LEVEL", "INFO").upper()),
                log_format=LogFormat(os.environ.get("ROSSUM_MCP_LOG_FORMAT", "console").lower()),
            )

    def __init__(self, config: Config) -> None:
        setup_logging(log_level=config.log_level, log_format=config.log_format)
        self.config = config
        self.client = AsyncRossumAPIClient(base_url=config.base_url, credentials=Token(token=config.api_token))
        self.mcp = self._create_app()

    def _create_app(self) -> FastMCP:
        logger.info(f"Rossum MCP Server {__version__} starting in {self.config.mode} mode")

        mcp = FastMCP("rossum-mcp-server")
        mcp.add_middleware(ObservabilityMiddleware())

        register_discovery_tools(mcp, self.config.mode)
        register_get_tools(mcp, self.client)
        register_search_tools(mcp, self.client)
        register_delete_tools(mcp, self.client)
        register_create_tools(mcp, self.client, self.config.base_url)
        register_update_tools(mcp, self.client, self.config.base_url)

        if self.config.mode == MCPMode.READ_ONLY:
            mcp.disable(tags={"write"})

        return mcp

    def run(self) -> None:
        self.mcp.run()
