#!/usr/bin/env python3
"""Rossum MCP Server

Provides tools for uploading documents and retrieving annotations using Rossum API
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import sys
import traceback
from typing import TYPE_CHECKING

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from rossum_api import AsyncRossumAPIClient
from rossum_api.dtos import Token

from rossum_mcp.handlers import (
    AnnotationsHandler,
    EnginesHandler,
    HooksHandler,
    QueuesHandler,
    RelationsHandler,
    RulesHandler,
    SchemasHandler,
    WorkspacesHandler,
)
from rossum_mcp.logging_config import setup_logging

if TYPE_CHECKING:
    from rossum_mcp.handlers.base import BaseHandler

setup_logging(
    app_name="rossum-mcp-server",
    log_level="DEBUG",
    log_file="/tmp/rossum_mcp_debug.log",
    use_console=False,
)

logger = logging.getLogger(__name__)


class RossumMCPServer:
    """MCP Server for Rossum API integration"""

    def __init__(self) -> None:
        self.server = Server("rossum-mcp-server")
        self.base_url = os.environ["ROSSUM_API_BASE_URL"]
        self.api_token = os.environ["ROSSUM_API_TOKEN"]

        # Read-only mode configuration: "read-only" or "read-write" (default)
        self.mode = os.environ.get("ROSSUM_MCP_MODE", "read-write").lower()
        if self.mode not in ("read-only", "read-write"):
            raise ValueError(f"Invalid ROSSUM_MCP_MODE: {self.mode}. Must be 'read-only' or 'read-write'")

        logger.info(f"Rossum MCP Server starting in {self.mode} mode")

        self.client = AsyncRossumAPIClient(base_url=self.base_url, credentials=Token(token=self.api_token))

        # Define read-only tool names (GET/LIST operations)
        self._read_only_tools = {
            # AnnotationsHandler
            "get_annotation",
            "list_annotations",
            # QueuesHandler
            "get_queue",
            "get_queue_schema",
            "get_queue_engine",
            # SchemasHandler
            "get_schema",
            # EnginesHandler
            "get_engine",
            "list_engines",
            "get_engine_fields",
            # HooksHandler
            "get_hook",
            "list_hooks",
            # RelationsHandler
            "get_relation",
            "list_relations",
            # RulesHandler
            "get_rule",
            "list_rules",
            # WorkspacesHandler
            "get_workspace",
            "list_workspaces",
        }

        # Initialize handlers
        self.annotations_handler = AnnotationsHandler(self.client, self.base_url)
        self.queues_handler = QueuesHandler(self.client, self.base_url)
        self.schemas_handler = SchemasHandler(self.client, self.base_url)
        self.engines_handler = EnginesHandler(self.client, self.base_url)
        self.hooks_handler = HooksHandler(self.client, self.base_url)
        self.relations_handler = RelationsHandler(self.client, self.base_url)
        self.rules_handler = RulesHandler(self.client, self.base_url)
        self.workspaces_handler = WorkspacesHandler(self.client, self.base_url)

        self.handlers: list[BaseHandler] = [
            self.annotations_handler,
            self.queues_handler,
            self.schemas_handler,
            self.engines_handler,
            self.hooks_handler,
            self.relations_handler,
            self.rules_handler,
            self.workspaces_handler,
        ]

        # Setup tool registry mapping tool names to handler methods
        self._tool_registry = self._build_tool_registry()

        self.setup_handlers()

    def _is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed based on current mode.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if the tool is allowed in current mode, False otherwise
        """
        if self.mode == "read-write":
            return True
        # In read-only mode, only allow read-only tools
        return tool_name in self._read_only_tools

    def _build_tool_registry(self) -> dict:
        """Build registry mapping tool names to their handler methods.

        Automatically collects all tools from handlers and filters based on mode.

        Returns:
            Dictionary mapping tool names to async handler callables

        Raises:
            ValueError: If duplicate tool names are found or invalid tool mappings exist
        """
        tool_registry = {}

        for handler in self.handlers:
            # Get tool-to-method mapping from handler
            mapping = handler.get_tool_registry()

            for tool_name, method_name in mapping.items():
                # Skip tools that aren't allowed in current mode
                if not self._is_tool_allowed(tool_name):
                    continue

                # Check for duplicate tool names
                if tool_name in tool_registry:
                    prev_method = tool_registry[tool_name]
                    prev_name = f"{prev_method.__self__.__class__.__name__}.{prev_method.__name__}"
                    curr_name = f"{handler.__class__.__name__}.{method_name}"
                    logger.error(f"Duplicate tool name '{tool_name}': {curr_name} conflicts with {prev_name}")
                    raise ValueError(f"Duplicate tool name: {tool_name}")

                # Get the actual method from the handler
                method = getattr(handler, method_name, None)

                # Validate method exists and is async
                if method is None:
                    logger.error(
                        f"{handler.__class__.__name__} maps tool '{tool_name}' to missing method '{method_name}'"
                    )
                    raise ValueError(f"Invalid tool mapping: {tool_name} -> {method_name}")

                if not inspect.iscoroutinefunction(method):
                    logger.error(
                        f"{handler.__class__.__name__} maps tool '{tool_name}' to non-async method '{method_name}'"
                    )
                    raise ValueError(f"Tool method must be async: {tool_name} -> {method_name}")

                tool_registry[tool_name] = method

        return tool_registry

    def _get_tool_definitions(self) -> list[Tool]:
        """Get list of tool definitions for MCP protocol.

        Automatically collects all tool definitions from handlers and filters based on mode.

        Returns:
            List of Tool objects with their schemas and descriptions
        """
        tool_definitions = []

        for handler in self.handlers:
            # Get tool definitions from each handler
            handler_tools = handler.get_tool_definitions()

            # Filter based on mode
            for tool in handler_tools:
                if self._is_tool_allowed(tool.name):
                    tool_definitions.append(tool)

        return tool_definitions

    def setup_handlers(self) -> None:
        """Setup MCP protocol handlers.

        Registers the list_tools and call_tool handlers for the MCP server.
        These handlers define the available tools and their execution logic.

        All MCP tools return JSON strings that clients must parse with json.loads().
        This is the standard MCP protocol behavior - tools return TextContent with JSON.
        """

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return self._get_tool_definitions()

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            try:
                logger.info(f"Tool called: {name} with arguments: {arguments}")

                # Use registry to dispatch to appropriate handler
                if name not in self._tool_registry:
                    raise ValueError(f"Unknown tool: {name}")

                handler = self._tool_registry[name]
                # Unpack arguments dict into keyword arguments for type safety
                result = await handler(**arguments)

                logger.info(f"Tool {name} completed successfully")
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Tool {name} failed: {e!s}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                error_result = {"error": str(e), "traceback": traceback.format_exc()}
                return [TextContent(type="text", text=json.dumps(error_result, indent=2))]

    async def run(self) -> None:
        """Start the MCP server.

        Runs the server using stdio transport for communication with MCP clients.
        """
        async with stdio_server() as (read_stream, write_stream):
            print("Rossum MCP Server running on stdio", file=sys.stderr)
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())


async def async_main() -> None:
    """Async main entry point.

    Creates and runs the RossumMCPServer instance.
    """
    server = RossumMCPServer()
    await server.run()


def main() -> None:
    """Main entry point for console script.

    This is the entry point used when running the server as a command-line tool.
    It initializes the async event loop and starts the server.
    """
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
