"""Tests for rossum_mcp.tools.create.connectors module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.connector import Connector

from rossum_mcp.tools.create.handler import register_create_tools


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
class TestCreateConnector:
    @pytest.mark.asyncio
    async def test_create_connector_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_connector = create_mock_connector(id=200, name="ERP Connector")
        mock_client.create_new_connector.return_value = mock_connector

        create_connector = mock_mcp._tools["create_connector"]
        result = await create_connector(
            name="ERP Connector",
            queue_id=10,
            service_url="https://erp.example.com/api",
        )

        assert result.id == 200
        assert result.name == "ERP Connector"
        call_args = mock_client.create_new_connector.call_args[0][0]
        assert call_args["queues"] == ["https://api.test.rossum.ai/v1/queues/10"]
        assert call_args["service_url"] == "https://erp.example.com/api"

    @pytest.mark.asyncio
    async def test_create_connector_with_auth(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_connector = create_mock_connector(id=201)
        mock_client.create_new_connector.return_value = mock_connector

        create_connector = mock_mcp._tools["create_connector"]
        await create_connector(
            name="Secure Connector",
            queue_id=10,
            service_url="https://secure.example.com/api",
            authorization_token="my-secret-token",
        )

        call_args = mock_client.create_new_connector.call_args[0][0]
        assert call_args["authorization_token"] == "my-secret-token"

    @pytest.mark.asyncio
    async def test_create_connector_sync_mode(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_connector = create_mock_connector(id=202, asynchronous=False)
        mock_client.create_new_connector.return_value = mock_connector

        create_connector = mock_mcp._tools["create_connector"]
        await create_connector(
            name="Sync Connector",
            queue_id=10,
            service_url="https://example.com/api",
            asynchronous=False,
        )

        call_args = mock_client.create_new_connector.call_args[0][0]
        assert call_args["asynchronous"] is False

    @pytest.mark.asyncio
    async def test_create_connector_with_ssl(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        mock_connector = create_mock_connector(id=203)
        mock_client.create_new_connector.return_value = mock_connector

        create_connector = mock_mcp._tools["create_connector"]
        await create_connector(
            name="SSL Connector",
            queue_id=10,
            service_url="https://example.com/api",
            client_ssl_certificate="-----BEGIN CERTIFICATE-----\nMIIC...\n-----END CERTIFICATE-----",
            client_ssl_key="-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----",
        )

        call_args = mock_client.create_new_connector.call_args[0][0]
        assert "client_ssl_certificate" in call_args
        assert "client_ssl_key" in call_args
