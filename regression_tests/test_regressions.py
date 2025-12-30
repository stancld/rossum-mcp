"""Regression test runner.

This module runs all regression test cases defined in test_cases.py.
Tests are parameterized so each case runs as a separate test.

Run with: pytest regression_tests/ -v -s
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from regression_tests.framework.assertions import assert_files_created, assert_tokens_within_budget, assert_tools_match
from regression_tests.framework.mermaid_analyzer import extract_mermaid_diagrams, validate_mermaid_diagrams
from regression_tests.framework.runner import run_regression_test
from regression_tests.test_cases import REGRESSION_TEST_CASES

if TYPE_CHECKING:
    from regression_tests.framework.models import RegressionRun, RegressionTestCase


def _check(name: str, condition: bool, message: str = "") -> bool:
    """Print check result. Returns True if passed."""
    if condition:
        print(f"  ✓ {name}")
        return True
    print(f"  ✗ {name}: {message}")
    return False


def _check_assertion(name: str, check_fn) -> bool:
    """Run an assertion function and print result. Returns True if passed."""
    try:
        check_fn()
        print(f"  ✓ {name}")
        return True
    except AssertionError as e:
        print(f"  ✗ {name}: {e}")
        return False


def _evaluate_criteria(run: RegressionRun, case: RegressionTestCase) -> bool:
    """Evaluate all success criteria and print results. Returns True if all pass."""
    all_passed = True

    all_passed &= _check_assertion("Tool expectation", lambda: assert_tools_match(run, case.tool_expectation))
    all_passed &= _check_assertion("Token budget", lambda: assert_tokens_within_budget(run, case.token_budget))

    criteria = case.success_criteria
    final_steps = [s for s in run.steps if s.is_final]
    final_step = final_steps[-1] if final_steps else None
    final_answer = final_step.final_answer if final_step else ""

    if criteria.require_final_answer:
        all_passed &= _check("Final answer present", bool(final_answer), "No final answer")

    if criteria.forbid_error:
        errors = [s.error for s in run.steps if s.error]
        all_passed &= _check("No agent errors", not errors, f"Errors: {errors}")

    if criteria.forbid_tool_errors:
        tool_errors = [f"{tr.name}: {tr.content}" for s in run.steps for tr in s.tool_results if tr.is_error]
        all_passed &= _check("No tool errors", not tool_errors, f"Tool errors: {tool_errors}")

    if criteria.required_keywords:
        answer_lower = (final_answer or "").lower()
        missing = [kw for kw in criteria.required_keywords if kw.lower() not in answer_lower]
        all_passed &= _check(
            f"Required keywords ({len(criteria.required_keywords)})",
            not missing,
            f"Missing: {missing}",
        )

    if criteria.max_steps is not None:
        all_passed &= _check(
            f"Max steps ({criteria.max_steps})",
            run.step_count <= criteria.max_steps,
            f"Got {run.step_count}",
        )

    all_passed &= _evaluate_mermaid(final_answer or "", criteria.mermaid_expectation)

    if criteria.file_expectation.expected_files:
        all_passed &= _check_assertion("File expectation", lambda: assert_files_created(criteria.file_expectation))
    else:
        print("  - File expectation: (none expected)")

    return all_passed


def _evaluate_mermaid(final_answer: str, mermaid_exp) -> bool:
    """Evaluate mermaid diagram expectations. Returns True if all pass."""
    if not mermaid_exp.descriptions and mermaid_exp.min_diagrams == 0:
        return True

    all_passed = True
    diagrams = extract_mermaid_diagrams(final_answer)
    print(f"  Found {len(diagrams)} mermaid diagram(s)")

    if mermaid_exp.min_diagrams > 0:
        all_passed &= _check(
            f"Min diagrams ({mermaid_exp.min_diagrams})",
            len(diagrams) >= mermaid_exp.min_diagrams,
            f"Got {len(diagrams)}",
        )

    if mermaid_exp.descriptions:
        success, msg = validate_mermaid_diagrams(final_answer, mermaid_exp.descriptions)
        all_passed &= _check("Mermaid content validation", success, msg)
        if success:
            print(f"    LLM reasoning: {msg}")

    return all_passed


@pytest.mark.regression
@pytest.mark.asyncio
@pytest.mark.parametrize("case", REGRESSION_TEST_CASES, ids=lambda c: c.name)
async def test_agent_regression(case, create_live_agent, show_answer):
    """Run a single regression test case against live API."""
    async with create_live_agent(case) as agent:
        run = await run_regression_test(agent, case)

        print(f"\n{'=' * 60}")
        print(f"Test: {case.name}")
        if case.description:
            print(f"Description: {case.description}")
        print(f"{'=' * 60}")
        print(f"Steps: {run.step_count}")
        print(f"Tools used: {run.all_tools}")
        print(f"Input tokens: {run.total_input_tokens}")
        print(f"Output tokens: {run.total_output_tokens}")
        print(f"Total tokens: {run.total_tokens}")
        print(f"Success: {run.is_successful}")
        if run.error:
            print(f"Error: {run.error}")

        print("\n--- Criteria Evaluation ---")
        all_passed = _evaluate_criteria(run, case)

        if show_answer:
            final_steps = [s for s in run.steps if s.is_final]
            final_answer = final_steps[-1].final_answer if final_steps else "(no answer)"
            print("\n--- Final Answer ---")
            print(final_answer)

        print(f"{'=' * 60}")

        if not all_passed:
            pytest.fail("One or more criteria failed")
