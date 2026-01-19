"""Pytest fixtures for rossum-agent-client tests."""

from __future__ import annotations

import pytest

from rossum_agent_client import AsyncRossumAgentClient, RossumAgentClient


@pytest.fixture
def agent_api_url() -> str:
    return "https://agent.example.com"


@pytest.fixture
def token() -> str:
    return "test-token-12345"


@pytest.fixture
def rossum_api_base_url() -> str:
    return "https://elis.rossum.ai/api/v1"


@pytest.fixture
def client(agent_api_url: str, rossum_api_base_url: str, token: str) -> RossumAgentClient:
    return RossumAgentClient(
        agent_api_url=agent_api_url,
        rossum_api_base_url=rossum_api_base_url,
        token=token,
    )


@pytest.fixture
def async_client(agent_api_url: str, rossum_api_base_url: str, token: str) -> AsyncRossumAgentClient:
    return AsyncRossumAgentClient(
        agent_api_url=agent_api_url,
        rossum_api_base_url=rossum_api_base_url,
        token=token,
    )


@pytest.fixture
def expected_headers(token: str, rossum_api_base_url: str) -> dict[str, str]:
    return {
        "X-Rossum-Token": token,
        "X-Rossum-Api-Url": rossum_api_base_url,
        "Content-Type": "application/json",
    }
