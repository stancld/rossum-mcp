"""Base handler class for Rossum MCP Server handlers"""

from __future__ import annotations

import inspect
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.types import Tool
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


class BaseHandler:
    """Base handler class providing shared functionality for all handlers"""

    def __init__(self, client: AsyncRossumAPIClient, base_url: str) -> None:
        """Initialize the base handler.

        Args:
            client: AsyncRossumAPIClient instance
            base_url: Base URL for the Rossum API
        """
        self.client = client
        self.base_url = base_url
        self._validate_tool_definitions()

    def _build_resource_url(self, resource_type: str, resource_id: int) -> str:
        """Build a full URL for a Rossum API resource.

        Args:
            resource_type: The resource type (e.g., 'workspaces', 'schemas', 'queues')
            resource_id: The resource ID

        Returns:
            Full URL string for the resource
        """
        return f"{self.base_url}/{resource_type}/{resource_id}"

    @classmethod
    def get_tool_definitions(cls) -> list[Tool]:
        """Get list of tool definitions for this handler.

        This method should be overridden by subclasses to return their tool definitions.

        Returns:
            List of Tool objects with their schemas and descriptions
        """
        return []

    def _validate_tool_definitions(self) -> None:
        """Validate that all public methods have corresponding tool definitions.

        Raises:
            ValueError: If a public method is missing a tool definition
        """
        # Get all public async methods (excluding magic methods and private methods)
        public_methods = {
            name
            for name, method in inspect.getmembers(self.__class__, predicate=inspect.iscoroutinefunction)
            if not name.startswith("_")
        }

        # Get all tool names from tool definitions
        tool_definitions = self.get_tool_definitions()
        tool_names = {tool.name for tool in tool_definitions}

        # Check if all public methods have tool definitions
        missing_tools = public_methods - tool_names
        if missing_tools:
            logger.warning(
                f"{self.__class__.__name__}: Public methods without tool definitions: {', '.join(sorted(missing_tools))}"
            )

        # Check if all tool definitions have corresponding methods
        missing_methods = tool_names - public_methods
        if missing_methods:
            logger.warning(
                f"{self.__class__.__name__}: Tool definitions without corresponding methods: {', '.join(sorted(missing_methods))}"
            )

    @classmethod
    def get_tool_registry(cls) -> dict[str, str]:
        """Get mapping of tool names to method names.

        By default, tool names map directly to method names.
        Override this if your tool names differ from method names.

        Returns:
            Dictionary mapping tool names to method names
        """
        tool_definitions = cls.get_tool_definitions()
        return {tool.name: tool.name for tool in tool_definitions}
