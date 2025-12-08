"""Tests for rossum_agent.mcp_tools module."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.mcp_tools import (
    MCPConnection,
    connect_mcp_server,
    create_mcp_transport,
    mcp_tool_to_anthropic_format,
    mcp_tools_to_anthropic_format,
)


class TestCreateMCPTransport:
    """Test create_mcp_transport function."""

    def test_creates_transport_with_required_params(self, monkeypatch):
        """Test creating transport with required parameters."""
        monkeypatch.delenv("ROSSUM_API_TOKEN", raising=False)
        monkeypatch.delenv("ROSSUM_API_BASE_URL", raising=False)

        transport = create_mcp_transport(
            rossum_api_token="test_token",
            rossum_api_base_url="https://api.rossum.ai",
        )

        assert transport.command == "rossum-mcp"
        assert transport.args == []
        assert transport.env["ROSSUM_API_TOKEN"] == "test_token"
        assert transport.env["ROSSUM_API_BASE_URL"] == "https://api.rossum.ai"
        assert transport.env["ROSSUM_MCP_MODE"] == "read-only"

    def test_creates_transport_with_read_write_mode(self, monkeypatch):
        """Test creating transport with read-write mode."""
        monkeypatch.delenv("ROSSUM_MCP_MODE", raising=False)

        transport = create_mcp_transport(
            rossum_api_token="test_token",
            rossum_api_base_url="https://api.rossum.ai",
            mcp_mode="read-write",
        )

        assert transport.env["ROSSUM_MCP_MODE"] == "read-write"

    def test_inherits_environment_variables(self):
        """Test that transport inherits current environment variables."""
        with patch.dict(os.environ, {"CUSTOM_VAR": "custom_value"}):
            transport = create_mcp_transport(
                rossum_api_token="test_token",
                rossum_api_base_url="https://api.rossum.ai",
            )

            assert transport.env["CUSTOM_VAR"] == "custom_value"


class TestMCPToolToAnthropicFormat:
    """Test mcp_tool_to_anthropic_format function."""

    def test_converts_tool_with_all_fields(self):
        """Test converting a tool with all fields populated."""
        mock_tool = MagicMock()
        mock_tool.name = "list_queues"
        mock_tool.description = "List all queues in the workspace"
        mock_tool.inputSchema = {
            "type": "object",
            "properties": {
                "workspace_url": {"type": "string", "description": "URL of the workspace"},
            },
            "required": ["workspace_url"],
        }

        result = mcp_tool_to_anthropic_format(mock_tool)

        assert result == {
            "name": "list_queues",
            "description": "List all queues in the workspace",
            "input_schema": {
                "type": "object",
                "properties": {
                    "workspace_url": {"type": "string", "description": "URL of the workspace"},
                },
                "required": ["workspace_url"],
            },
        }

    def test_handles_empty_description(self):
        """Test converting a tool with no description."""
        mock_tool = MagicMock()
        mock_tool.name = "simple_tool"
        mock_tool.description = None
        mock_tool.inputSchema = {"type": "object", "properties": {}}

        result = mcp_tool_to_anthropic_format(mock_tool)

        assert result["description"] == ""

    def test_handles_minimal_input_schema(self):
        """Test converting a tool with minimal inputSchema."""
        mock_tool = MagicMock()
        mock_tool.name = "minimal_schema_tool"
        mock_tool.description = "A tool with minimal schema"
        mock_tool.inputSchema = {"type": "object", "properties": {}}

        result = mcp_tool_to_anthropic_format(mock_tool)

        assert result["input_schema"] == {"type": "object", "properties": {}}


class TestMCPToolsToAnthropicFormat:
    """Test mcp_tools_to_anthropic_format function."""

    def test_converts_multiple_tools(self):
        """Test converting a list of tools."""
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"
        mock_tool1.description = "First tool"
        mock_tool1.inputSchema = {"type": "object", "properties": {}}

        mock_tool2 = MagicMock()
        mock_tool2.name = "tool2"
        mock_tool2.description = "Second tool"
        mock_tool2.inputSchema = {"type": "object", "properties": {"param": {"type": "string"}}}

        result = mcp_tools_to_anthropic_format([mock_tool1, mock_tool2])

        assert len(result) == 2
        assert result[0]["name"] == "tool1"
        assert result[1]["name"] == "tool2"

    def test_handles_empty_list(self):
        """Test converting an empty list of tools."""
        result = mcp_tools_to_anthropic_format([])

        assert result == []


class TestMCPConnection:
    """Test MCPConnection class."""

    @pytest.mark.asyncio
    async def test_get_tools_caches_result(self):
        """Test that get_tools caches the result after first call."""
        mock_client = AsyncMock()
        mock_tools = [MagicMock(name="tool1"), MagicMock(name="tool2")]
        mock_client.list_tools.return_value = mock_tools

        connection = MCPConnection(client=mock_client)

        result1 = await connection.get_tools()
        result2 = await connection.get_tools()

        assert result1 == mock_tools
        assert result2 == mock_tools
        mock_client.list_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_returns_data_property(self):
        """Test that call_tool returns the data property when available."""
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.data = {"queues": [{"id": 1, "name": "Test Queue"}]}
        mock_result.content = []
        mock_client.call_tool.return_value = mock_result

        connection = MCPConnection(client=mock_client)

        result = await connection.call_tool("list_queues", {"workspace_url": "https://example.com"})

        assert result == {"queues": [{"id": 1, "name": "Test Queue"}]}
        mock_client.call_tool.assert_called_once_with("list_queues", {"workspace_url": "https://example.com"})

    @pytest.mark.asyncio
    async def test_call_tool_returns_text_content_when_no_data(self):
        """Test that call_tool returns text content when data is None."""
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.data = None
        mock_text_block = MagicMock()
        mock_text_block.text = "Tool executed successfully"
        mock_result.content = [mock_text_block]
        mock_client.call_tool.return_value = mock_result

        connection = MCPConnection(client=mock_client)

        result = await connection.call_tool("simple_tool")

        assert result == "Tool executed successfully"

    @pytest.mark.asyncio
    async def test_call_tool_joins_multiple_text_blocks(self):
        """Test that call_tool joins multiple text content blocks."""
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.data = None

        mock_text1 = MagicMock()
        mock_text1.text = "Line 1"
        mock_text2 = MagicMock()
        mock_text2.text = "Line 2"
        mock_result.content = [mock_text1, mock_text2]
        mock_client.call_tool.return_value = mock_result

        connection = MCPConnection(client=mock_client)

        result = await connection.call_tool("multi_output_tool")

        assert result == "Line 1\nLine 2"

    @pytest.mark.asyncio
    async def test_call_tool_handles_empty_arguments(self):
        """Test that call_tool handles missing arguments."""
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.data = "result"
        mock_client.call_tool.return_value = mock_result

        connection = MCPConnection(client=mock_client)

        await connection.call_tool("no_args_tool")

        mock_client.call_tool.assert_called_once_with("no_args_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_returns_none_for_empty_response(self):
        """Test that call_tool returns None when no data or content."""
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.data = None
        mock_result.content = []
        mock_client.call_tool.return_value = mock_result

        connection = MCPConnection(client=mock_client)

        result = await connection.call_tool("void_tool")

        assert result is None


class TestConnectMCPServer:
    """Test connect_mcp_server context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_yields_connection(self):
        """Test that connect_mcp_server yields an MCPConnection."""
        mock_client_instance = AsyncMock()
        mock_tools = [MagicMock(name="tool1")]
        mock_client_instance.list_tools.return_value = mock_tools

        with patch("rossum_agent.mcp_tools.Client") as mock_client_class:
            mock_client_class.return_value = mock_client_instance
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)

            async with connect_mcp_server(
                rossum_api_token="token",
                rossum_api_base_url="https://api.rossum.ai",
            ) as connection:
                assert isinstance(connection, MCPConnection)
                tools = await connection.get_tools()
                assert tools == mock_tools

    @pytest.mark.asyncio
    async def test_context_manager_configures_transport(self):
        """Test that connect_mcp_server configures the transport correctly."""
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("rossum_agent.mcp_tools.Client") as mock_client_class,
            patch("rossum_agent.mcp_tools.create_mcp_transport") as mock_create_transport,
        ):
            mock_transport = MagicMock()
            mock_create_transport.return_value = mock_transport
            mock_client_class.return_value = mock_client_instance

            async with connect_mcp_server(
                rossum_api_token="test_token",
                rossum_api_base_url="https://api.rossum.ai",
                mcp_mode="read-write",
            ):
                pass

            mock_create_transport.assert_called_once_with(
                rossum_api_token="test_token",
                rossum_api_base_url="https://api.rossum.ai",
                mcp_mode="read-write",
            )
            mock_client_class.assert_called_once_with(mock_transport)
