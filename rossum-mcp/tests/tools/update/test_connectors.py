"""Tests for rossum_mcp.tools.update.connectors module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.connector import Connector

from rossum_mcp.tools.update.handler import register_update_tools


def create_mock_connector(**kwargs) -> Connector:
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/connectors/1",
        "name": "Test Connector",
        "service_url": "https://example.com/api/validate",
        "params": None,
        "client_ssl_certificate": None,
        "authorization_token": "secret-token",
        "client_ssl_key": None,
        "queues": ["https://api.test.rossum.ai/v1/queues/10"],
        "authorization_type": "secret_key",
        "asynchronous": True,
        "metadata": {},
    }
    defaults.update(kwargs)
    return Connector(**defaults)


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.fixture
def mock_mcp() -> Mock:
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
class TestUpdateConnector:
    @pytest.mark.asyncio
    async def test_update_connector_name(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        updated_connector = create_mock_connector(id=1, name="Renamed Connector")
        mock_client._http_client.update.return_value = updated_connector
        mock_client._deserializer.return_value = updated_connector

        update_connector = mock_mcp._tools["update_connector"]
        result = await update_connector(connector_id=1, name="Renamed Connector")

        assert result.name == "Renamed Connector"
        mock_client._http_client.update.assert_called_once_with(
            Resource.Connector, 1, {"name": "Renamed Connector"}
        )

    @pytest.mark.asyncio
    async def test_update_connector_service_url(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        updated_connector = create_mock_connector(id=1, service_url="https://new.example.com/api")
        mock_client._http_client.update.return_value = updated_connector
        mock_client._deserializer.return_value = updated_connector

        update_connector = mock_mcp._tools["update_connector"]
        await update_connector(connector_id=1, service_url="https://new.example.com/api")

        mock_client._http_client.update.assert_called_once_with(
            Resource.Connector, 1, {"service_url": "https://new.example.com/api"}
        )

    @pytest.mark.asyncio
    async def test_update_connector_excludes_none(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_update_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        updated_connector = create_mock_connector(id=1)
        mock_client._http_client.update.return_value = updated_connector
        mock_client._deserializer.return_value = updated_connector

        update_connector = mock_mcp._tools["update_connector"]
        await update_connector(connector_id=1, name="Only Name")

        _, _, patch_data = mock_client._http_client.update.call_args[0]
        assert "service_url" not in patch_data
        assert "authorization_token" not in patch_data
