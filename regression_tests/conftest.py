"""Pytest configuration and fixtures for regression tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from dotenv import dotenv_values
from rossum_agent.agent.core import RossumAgent
from rossum_agent.agent.models import AgentConfig
from rossum_agent.bedrock_client import create_bedrock_client
from rossum_agent.prompts import get_system_prompt
from rossum_agent.rossum_mcp_integration import connect_mcp_server
from rossum_agent.url_context import extract_url_context, format_context_for_prompt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from regression_tests.framework.models import RegressionTestCase

ENV_FILE = Path(__file__).parent / ".env"


def _load_env_tokens() -> dict[str, str]:
    """Load API tokens from .env file."""
    if ENV_FILE.exists():
        return {k: v for k, v in dotenv_values(ENV_FILE).items() if v is not None}
    return {}


def _get_token_for_test(test_name: str, env_tokens: dict[str, str]) -> str | None:
    """Get API token for a specific test from .env file.

    Looks for: TEST_NAME_API_TOKEN (uppercase, underscores)
    Falls back to: DEFAULT_API_TOKEN
    """
    key = f"{test_name.upper().replace('-', '_')}_API_TOKEN"
    return env_tokens.get(key) or env_tokens.get("DEFAULT_API_TOKEN")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add command-line options for regression tests."""
    parser.addoption(
        "--api-token",
        action="store",
        default=None,
        help="Rossum API token (overrides all other sources)",
    )
    parser.addoption(
        "--show-answer",
        action="store_true",
        default=False,
        help="Show the full final answer in test output",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "regression: mark test as a regression test")


@pytest.fixture(scope="session")
def env_tokens() -> dict[str, str]:
    """Load tokens from .env file once per session."""
    return _load_env_tokens()


@pytest.fixture(scope="session")
def api_token_override(request: pytest.FixtureRequest) -> str | None:
    """Get API token from command line (highest priority)."""
    return request.config.getoption("--api-token")


@pytest.fixture(scope="session")
def show_answer(request: pytest.FixtureRequest) -> bool:
    """Whether to show full final answer in output."""
    return request.config.getoption("--show-answer")


def get_token_for_case(
    case: RegressionTestCase,
    env_tokens: dict[str, str],
    api_token_override: str | None,
) -> str:
    """Resolve API token for a test case.

    Priority: --api-token flag > .env TEST_NAME_API_TOKEN > .env DEFAULT_API_TOKEN > case.api_token
    """
    if api_token_override:
        return api_token_override

    env_token = _get_token_for_test(case.name, env_tokens)
    if env_token:
        return env_token

    if case.api_token:
        return case.api_token

    raise ValueError(
        f"No API token for test '{case.name}'. Add {case.name.upper().replace('-', '_')}_API_TOKEN "
        "to .env file, set DEFAULT_API_TOKEN, use --api-token flag, or set api_token in test case."
    )


@pytest.fixture
def create_live_agent(
    env_tokens: dict[str, str],
    api_token_override: str | None,
) -> Callable[[RegressionTestCase], AsyncIterator[RossumAgent]]:
    """Factory fixture to create a live RossumAgent for a test case.

    Usage:
        async with create_live_agent(case) as agent:
            # run tests with agent

    Token priority: --api-token flag > .env TEST_NAME_API_TOKEN > .env DEFAULT_API_TOKEN > case.api_token
    """

    @asynccontextmanager
    async def _create_agent(case: RegressionTestCase) -> AsyncIterator[RossumAgent]:
        token = get_token_for_case(case, env_tokens, api_token_override)

        config = AgentConfig(
            max_tokens=128000,
            max_steps=50,
            temperature=0.0,
            request_delay=3.0,
        )

        async with connect_mcp_server(
            rossum_api_token=token,
            rossum_api_base_url=case.api_base_url,
            mcp_mode="read-write",
        ) as mcp_connection:
            client = create_bedrock_client()
            system_prompt = get_system_prompt()

            if case.rossum_url:
                url_context = extract_url_context(case.rossum_url)
                if not url_context.is_empty():
                    context_section = format_context_for_prompt(url_context)
                    system_prompt = system_prompt + "\n\n---\n" + context_section

            agent = RossumAgent(
                client=client,
                mcp_connection=mcp_connection,
                system_prompt=system_prompt,
                config=config,
            )
            yield agent

    return _create_agent
