"""Regression test runner with retry logic.

Runs each test case up to 3 times until the first success.
Waits 5s after success, 15s after failure before the next test.

Usage:
    python -m regression_tests.run_all [--show-answer] [--api-token TOKEN]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from dotenv import dotenv_values
from rossum_agent.agent.core import RossumAgent
from rossum_agent.agent.models import AgentConfig
from rossum_agent.bedrock_client import create_bedrock_client
from rossum_agent.change_tracking.store import CommitStore
from rossum_agent.system_prompt import get_system_prompt
from rossum_agent.rossum_mcp_integration import connect_mcp_server
from rossum_agent.tools.core import AgentContext, reset_context, set_context
from rossum_agent.tools.dynamic_tools import get_write_tools_async
from rossum_agent.tools.task_tracker import TaskTracker
from rossum_agent.url_context import extract_url_context, format_context_for_prompt

from regression_tests.conftest import try_connect_redis
from regression_tests.framework.runner import run_regression_test
from regression_tests.test_cases import REGRESSION_TEST_CASES
from regression_tests.test_regressions import _evaluate_criteria

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from regression_tests.framework.models import RegressionTestCase

_ENV_FILE = Path(__file__).parent / ".env"

MAX_ATTEMPTS = 3
DELAY_AFTER_SUCCESS = 15
DELAY_AFTER_FAILURE = 30


@dataclass
class AttemptResult:
    passed: bool
    failures: list[str]
    error: str | None = None


@dataclass
class TestResult:
    name: str
    attempts: list[AttemptResult]

    @property
    def passed(self) -> bool:
        return any(a.passed for a in self.attempts)

    @property
    def failure_reason(self) -> str:
        if self.passed:
            return ""
        last = self.attempts[-1]
        if last.error:
            return last.error
        return "; ".join(last.failures) if last.failures else "Unknown"


def _load_env_tokens() -> dict[str, str]:
    if _ENV_FILE.exists():
        return {k: v for k, v in dotenv_values(_ENV_FILE).items() if v is not None}
    return {}


def _create_commit_store() -> CommitStore | None:
    """Create a CommitStore if Redis is reachable."""
    client = try_connect_redis()
    return CommitStore(client) if client else None


def _get_token(case: RegressionTestCase, env_tokens: dict[str, str], cli_token: str | None) -> str:
    if cli_token:
        return cli_token

    key = f"{case.name.upper().replace('-', '_')}_API_TOKEN"
    if token := env_tokens.get(key):
        return token
    if token := env_tokens.get("DEFAULT_API_TOKEN"):
        return token
    if case.api_token:
        return case.api_token

    raise ValueError(f"No API token for test '{case.name}'")


@asynccontextmanager
async def create_agent(case: RegressionTestCase, api_token: str, output_dir: Path) -> AsyncIterator[RossumAgent]:
    config = AgentConfig(max_output_tokens=64000, max_steps=50, temperature=1.0, request_delay=3.0)

    async with connect_mcp_server(
        rossum_api_token=api_token, rossum_api_base_url=case.api_base_url, mcp_mode=case.mode
    ) as mcp_connection:
        commit_store = None
        environment = None
        if case.requires_redis:
            commit_store = _create_commit_store()
            if commit_store:
                write_tools = await get_write_tools_async(mcp_connection)
                chat_id = f"regression-test-{case.name}"
                environment = case.api_base_url.rstrip("/")
                mcp_connection.setup_change_tracking(write_tools, chat_id, environment, commit_store)

        ctx = AgentContext(
            mcp_connection=mcp_connection,
            mcp_event_loop=asyncio.get_event_loop(),
            mcp_mode=case.mode,
            rossum_credentials=(case.api_base_url, api_token),
            rossum_environment=environment,
            output_dir=output_dir,
            commit_store=commit_store,
            task_tracker=TaskTracker(),
        )
        token_ref = set_context(ctx)

        client = create_bedrock_client()
        system_prompt = get_system_prompt()

        if case.rossum_url:
            url_context = extract_url_context(case.rossum_url)
            if not url_context.is_empty():
                context_section = format_context_for_prompt(url_context)
                system_prompt = system_prompt + "\n\n---\n" + context_section

        agent = RossumAgent(client=client, mcp_connection=mcp_connection, system_prompt=system_prompt, config=config)

        try:
            yield agent
        finally:
            reset_context(token_ref)


async def run_single_attempt(case: RegressionTestCase, api_token: str, output_dir: Path) -> AttemptResult:
    try:
        async with create_agent(case, api_token, output_dir) as agent:
            prompt = case.prompt
            if case.setup_fn:
                placeholders = case.setup_fn(case.api_base_url, api_token)
                for key, value in placeholders.items():
                    prompt = prompt.replace(f"{{{key}}}", value)

            run = await run_regression_test(agent, prompt)

            print(f"  Steps: {run.step_count} | Tools: {run.all_tools}")
            print(f"  Tokens: {run.total_tokens} (in={run.total_input_tokens}, out={run.total_output_tokens})")

            all_passed, failures = _evaluate_criteria(run, case, api_token, output_dir)
            return AttemptResult(passed=all_passed, failures=failures)
    except Exception as e:
        print(f"  Exception: {e}")
        return AttemptResult(passed=False, failures=[], error=str(e))


async def run_all(cli_token: str | None = None) -> list[TestResult]:
    env_tokens = _load_env_tokens()
    redis_available = try_connect_redis() is not None
    results: list[TestResult] = []

    for i, case in enumerate(REGRESSION_TEST_CASES):
        print(f"\n{'=' * 70}")
        print(f"[{i + 1}/{len(REGRESSION_TEST_CASES)}] {case.name}")
        if case.description:
            print(f"  {case.description}")
        print(f"{'=' * 70}")

        if case.requires_redis and not redis_available:
            print("  SKIPPED (Redis not available)")
            results.append(
                TestResult(
                    name=case.name,
                    attempts=[AttemptResult(passed=False, failures=[], error="Redis not available")],
                )
            )
            continue

        try:
            api_token = _get_token(case, env_tokens, cli_token)
        except ValueError as e:
            print(f"  SKIPPED ({e})")
            results.append(
                TestResult(
                    name=case.name,
                    attempts=[AttemptResult(passed=False, failures=[], error=str(e))],
                )
            )
            continue

        test_result = TestResult(name=case.name, attempts=[])

        for attempt in range(MAX_ATTEMPTS):
            print(f"\n  --- Attempt {attempt + 1}/{MAX_ATTEMPTS} ---")

            with TemporaryDirectory() as tmp:
                output_dir = Path(tmp) / "outputs"
                output_dir.mkdir()
                result = await run_single_attempt(case, api_token, output_dir)

            test_result.attempts.append(result)

            if result.passed:
                print(f"  PASSED on attempt {attempt + 1}")
                break

            reason = result.error or "; ".join(result.failures)
            print(f"  FAILED: {reason}")

        is_last_test = i == len(REGRESSION_TEST_CASES) - 1
        if not is_last_test:
            delay = DELAY_AFTER_SUCCESS if test_result.passed else DELAY_AFTER_FAILURE
            print(f"  Waiting {delay}s before next test...")
            await asyncio.sleep(delay)

        results.append(test_result)

    return results


def _status_symbol(result: AttemptResult | None) -> str:
    if result is None:
        return "-"
    return "\u2713" if result.passed else "\u2717"


def print_summary(results: list[TestResult]) -> None:
    print(f"\n\n{'=' * 100}")
    print("REGRESSION TEST SUMMARY")
    print(f"{'=' * 100}")

    name_w = max(len(r.name) for r in results)
    name_w = max(name_w, len("Test case"))
    col_w = 6

    header = f"{'Test case':<{name_w}} | {'1st':^{col_w}} | {'2nd':^{col_w}} | {'3rd':^{col_w}} | Reason to fail"
    print(header)
    print("-" * len(header) + "-" * 40)

    for r in results:
        attempts = [r.attempts[i] if i < len(r.attempts) else None for i in range(MAX_ATTEMPTS)]
        row = (
            f"{r.name:<{name_w}} | "
            f"{_status_symbol(attempts[0]):^{col_w}} | "
            f"{_status_symbol(attempts[1]):^{col_w}} | "
            f"{_status_symbol(attempts[2]):^{col_w}} | "
            f"{r.failure_reason}"
        )
        print(row)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print(f"\n{passed}/{total} passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run regression tests with retry logic")
    parser.add_argument("--api-token", help="Rossum API token (overrides .env)")
    args = parser.parse_args()

    results = asyncio.run(run_all(cli_token=args.api_token))
    print_summary(results)

    all_passed = all(r.passed for r in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
