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
    RulesHandler,
    SchemasHandler,
)

if TYPE_CHECKING:
    from typing import Literal

    from rossum_mcp.handlers.base import BaseHandler

# Set up logging to a file (since stdout is used for MCP)
logging.basicConfig(
    filename="/tmp/rossum_mcp_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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
            "get_annotation",
            "list_annotations",
            "get_queue",
            "get_schema",
            "get_queue_schema",
            "get_queue_engine",
            "list_hooks",
            "list_rules",
        }

        # Initialize handlers
        self.annotations_handler = AnnotationsHandler(self.client, self.base_url)
        self.queues_handler = QueuesHandler(self.client, self.base_url)
        self.schemas_handler = SchemasHandler(self.client, self.base_url)
        self.engines_handler = EnginesHandler(self.client, self.base_url)
        self.hooks_handler = HooksHandler(self.client, self.base_url)
        self.rules_handler = RulesHandler(self.client, self.base_url)

        self.handlers: list[BaseHandler] = [
            self.annotations_handler,
            self.queues_handler,
            self.schemas_handler,
            self.engines_handler,
            self.hooks_handler,
            self.rules_handler,
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

    # Convenience delegation methods for backward compatibility with tests
    async def upload_document(self, file_path: str, queue_id: int) -> dict:
        """Delegate to annotations handler."""
        return await self.annotations_handler.upload_document(file_path, queue_id)

    async def get_annotation(self, annotation_id: int, sideloads=()) -> dict:
        """Delegate to annotations handler."""
        return await self.annotations_handler.get_annotation(annotation_id, sideloads)

    async def list_annotations(
        self, queue_id: int, status: str | None = "importing,to_review,confirmed,exported"
    ) -> dict:
        """Delegate to annotations handler."""
        return await self.annotations_handler.list_annotations(queue_id, status)

    async def start_annotation(self, annotation_id: int) -> dict:
        """Delegate to annotations handler."""
        return await self.annotations_handler.start_annotation(annotation_id)

    async def bulk_update_annotation_fields(self, annotation_id: int, operations: list[dict]) -> dict:
        """Delegate to annotations handler."""
        return await self.annotations_handler.bulk_update_annotation_fields(annotation_id, operations)

    async def confirm_annotation(self, annotation_id: int) -> dict:
        """Delegate to annotations handler."""
        return await self.annotations_handler.confirm_annotation(annotation_id)

    async def get_queue(self, queue_id: int) -> dict:
        """Delegate to queues handler."""
        return await self.queues_handler.get_queue(queue_id)

    async def create_queue(self, name: str, workspace_id: int, schema_id: int, **kwargs) -> dict:
        """Delegate to queues handler."""
        return await self.queues_handler.create_queue(name, workspace_id, schema_id, **kwargs)

    async def update_queue(self, queue_id: int, queue_data: dict) -> dict:
        """Delegate to queues handler."""
        return await self.queues_handler.update_queue(queue_id, queue_data)

    async def get_schema(self, schema_id: int) -> dict:
        """Delegate to schemas handler."""
        return await self.schemas_handler.get_schema(schema_id)

    async def get_queue_schema(self, queue_id: int) -> dict:
        """Delegate to queues handler."""
        return await self.queues_handler.get_queue_schema(queue_id)

    async def create_schema(self, name: str, content: list[dict]) -> dict:
        """Delegate to schemas handler."""
        return await self.schemas_handler.create_schema(name, content)

    async def update_schema(self, schema_id: int, schema_data: dict) -> dict:
        """Delegate to schemas handler."""
        return await self.schemas_handler.update_schema(schema_id, schema_data)

    async def get_queue_engine(self, queue_id: int) -> dict:
        """Delegate to queues handler."""
        return await self.queues_handler.get_queue_engine(queue_id)

    async def create_engine(self, name: str, organization_id: int, engine_type: str) -> dict:
        """Delegate to engines handler."""
        return await self.engines_handler.create_engine(name, organization_id, engine_type)

    async def update_engine(self, engine_id: int, engine_data: dict) -> dict:
        """Delegate to engines handler."""
        return await self.engines_handler.update_engine(engine_id, engine_data)

    async def create_engine_field(
        self,
        engine_id: int,
        name: str,
        label: str,
        field_type: str,
        schema_ids: list[int],
        tabular: bool = False,
        multiline: str = "false",
        subtype: str | None = None,
        pre_trained_field_id: str | None = None,
    ) -> dict:
        """Delegate to engines handler."""
        return await self.engines_handler.create_engine_field(
            engine_id, name, label, field_type, schema_ids, tabular, multiline, subtype, pre_trained_field_id
        )

    async def list_hooks(self, queue_id: int | None = None, active: bool | None = None) -> dict:
        """Delegate to hooks handler."""
        return await self.hooks_handler.list_hooks(queue_id, active)

    async def create_hook(
        self,
        name: str,
        type: Literal["webhook", "function"],
        queues: list[str] | None = None,
        events: list[str] | None = None,
        config: dict | None = None,
        settings: dict | None = None,
        secret: str | None = None,
    ) -> dict:
        """Delegate to hooks handler."""
        return await self.hooks_handler.create_hook(name, type, queues, events, config, settings, secret)

    async def list_rules(self, queue_id: int | None = None, enabled: bool | None = None) -> dict:
        """Delegate to rules handler."""
        return await self.rules_handler.list_rules(queue_id, enabled)

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
