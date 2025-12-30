from __future__ import annotations

from typing import TYPE_CHECKING

from regression_tests.framework.assertions import assert_success, assert_tokens_within_budget, assert_tools_match
from regression_tests.framework.models import RegressionRun, RegressionTestCase

if TYPE_CHECKING:
    from rossum_agent.agent.core import RossumAgent
    from rossum_agent.agent.models import AgentStep


async def run_agent_and_collect(agent: RossumAgent, prompt: str) -> RegressionRun:
    """Run the agent once and collect all steps + aggregated metrics.

    Args:
        agent: The RossumAgent instance to run.
        prompt: The prompt to send to the agent.

    Returns:
        RegressionRun with all steps and aggregated metrics.
    """
    steps: list[AgentStep] = []

    async for step in agent.run(prompt):
        steps.append(step)

    all_tools: list[str] = []
    for step in steps:
        if not step.is_streaming and step.tool_calls:
            all_tools.extend(tc.name for tc in step.tool_calls)

    total_input_tokens = sum(s.input_tokens for s in steps if not s.is_streaming)
    total_output_tokens = sum(s.output_tokens for s in steps if not s.is_streaming)

    final_steps = [s for s in steps if s.is_final]
    is_successful = bool(final_steps) and not any(s.error for s in steps)
    final_answer = final_steps[-1].final_answer if final_steps else None
    error = next((s.error for s in steps if s.error), None)

    return RegressionRun(
        steps=steps,
        all_tools=all_tools,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        is_successful=is_successful,
        final_answer=final_answer,
        error=error,
    )


async def run_regression_test(agent: RossumAgent, case: RegressionTestCase) -> RegressionRun:
    """Run a complete regression test case.

    Runs the agent, collects metrics, and asserts all expectations.

    Args:
        agent: The RossumAgent instance to test.
        case: The regression test case to run.

    Returns:
        RegressionRun with collected metrics (after assertions pass).

    Raises:
        AssertionError: If any expectation is not met.
    """
    run = await run_agent_and_collect(agent, case.prompt)

    assert_tools_match(run, case.tool_expectation)
    assert_tokens_within_budget(run, case.token_budget)
    assert_success(run, case.success_criteria)

    return run
