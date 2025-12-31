"""Assertion helpers for regression testing."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

from regression_tests.framework.mermaid_analyzer import validate_mermaid_diagrams

if TYPE_CHECKING:
    from regression_tests.framework.models import (
        FileExpectation,
        RegressionRun,
        SuccessCriteria,
        TokenBudget,
        ToolExpectation,
    )


def assert_tools_match(run: RegressionRun, expectation: ToolExpectation) -> None:
    actual = run.all_tools
    expected = list(expectation.expected_tools)

    if not expected:
        return

    if expectation.mode == "exact_sequence":
        if expectation.allow_extras:
            _assert_subsequence(expected, actual)
        else:
            if actual != expected:
                raise AssertionError(f"Tool sequence mismatch: expected exactly {expected}, got {actual}")

    elif expectation.mode == "subsequence":
        _assert_subsequence(expected, actual)

    elif expectation.mode == "subset":
        missing = [name for name in expected if name not in actual]
        if missing:
            raise AssertionError(f"Tool subset mismatch: missing expected tools {missing}, got {actual}")

    else:
        raise ValueError(f"Unknown tool match mode: {expectation.mode}")


def _assert_subsequence(expected: list[str], actual: list[str]) -> None:
    it = iter(actual)
    for name in expected:
        for a in it:
            if a == name:
                break
        else:
            raise AssertionError(f"Tool subsequence mismatch: expected {expected} as subsequence, got {actual}")


def assert_tokens_within_budget(run: RegressionRun, budget: TokenBudget) -> None:
    if budget.min_total_tokens is not None:
        total = run.total_input_tokens + run.total_output_tokens
        assert total >= budget.min_total_tokens, f"Total tokens {total} < minimum {budget.min_total_tokens}"

    if budget.max_input_tokens is not None:
        assert run.total_input_tokens <= budget.max_input_tokens, (
            f"Input tokens {run.total_input_tokens} > budget {budget.max_input_tokens}"
        )

    if budget.max_output_tokens is not None:
        assert run.total_output_tokens <= budget.max_output_tokens, (
            f"Output tokens {run.total_output_tokens} > budget {budget.max_output_tokens}"
        )

    if budget.max_total_tokens is not None:
        total = run.total_input_tokens + run.total_output_tokens
        assert total <= budget.max_total_tokens, f"Total tokens {total} > budget {budget.max_total_tokens}"

    if budget.max_input_tokens_per_step is not None:
        for s in run.steps:
            if not s.is_streaming:
                assert s.input_tokens <= budget.max_input_tokens_per_step, (
                    f"Step {s.step_number} input_tokens {s.input_tokens} > per-step budget"
                )

    if budget.max_output_tokens_per_step is not None:
        for s in run.steps:
            if not s.is_streaming:
                assert s.output_tokens <= budget.max_output_tokens_per_step, (
                    f"Step {s.step_number} output_tokens {s.output_tokens} > per-step budget"
                )


def assert_success(run: RegressionRun, criteria: SuccessCriteria, output_dir: Path | None = None) -> None:
    """Assert that the agent run meets success criteria.

    Raises:
        AssertionError: If any success criterion is not met.
    """
    steps = run.steps
    assert steps, "Agent produced no steps"

    final_steps = [s for s in steps if s.is_final]
    assert final_steps, "No final step produced"
    final_step = final_steps[-1]

    if criteria.require_final_answer:
        assert final_step.final_answer, "Final step has no final_answer"

    if criteria.forbid_error:
        errors = [s.error for s in steps if s.error]
        assert not errors, f"Agent produced errors: {errors}"

    if criteria.forbid_tool_errors:
        tool_errors: list[str] = []
        for s in steps:
            for tr in s.tool_results:
                if tr.is_error:
                    tool_errors.append(f"{tr.name}: {tr.content}")
        assert not tool_errors, f"Tool errors: {tool_errors}"

    if criteria.required_keywords:
        final_answer = final_step.final_answer or ""
        answer_lower = final_answer.lower()
        missing = [kw for kw in criteria.required_keywords if kw.lower() not in answer_lower]
        assert not missing, f"Required keywords missing from final answer: {missing}"

    if criteria.max_steps is not None:
        step_count = len([s for s in steps if not s.is_streaming])
        assert step_count <= criteria.max_steps, f"Step count {step_count} exceeds max_steps {criteria.max_steps}"

    mermaid_exp = criteria.mermaid_expectation
    if mermaid_exp.descriptions or mermaid_exp.min_diagrams > 0:
        final_answer = final_step.final_answer or ""
        success, message = validate_mermaid_diagrams(final_answer, mermaid_exp.descriptions, mermaid_exp.min_diagrams)
        assert success, f"Mermaid validation failed: {message}"

    if criteria.file_expectation.expected_files:
        assert_files_created(criteria.file_expectation, output_dir)

    for check in criteria.custom_checks:
        passed, reasoning = check.check_fn(steps)
        assert passed, f"Custom check '{check.name}' failed: {reasoning}"


def _matches_pattern(filename: str, pattern: str) -> bool:
    """Check if filename matches pattern (supports wildcards like *.md)."""
    return fnmatch.fnmatch(filename, pattern)


def assert_files_created(expectation: FileExpectation, output_dir: Path | None = None) -> None:
    if output_dir is None:
        output_dir = Path("outputs")

    if not expectation.expected_files:
        return

    actual_files = list(output_dir.rglob("*")) if output_dir.exists() else []
    actual_files = [f for f in actual_files if f.is_file()]
    actual_filenames = [f.name for f in actual_files]

    if expectation.check_exists:
        unmatched_patterns = []
        for pattern in expectation.expected_files:
            matched = any(_matches_pattern(name, pattern) for name in actual_filenames)
            if not matched:
                unmatched_patterns.append(pattern)
        if unmatched_patterns:
            raise AssertionError(
                f"Expected file patterns not matched: {unmatched_patterns}. Actual files: {actual_filenames}"
            )

    if len(actual_files) != len(expectation.expected_files):
        raise AssertionError(
            f"Expected exactly {len(expectation.expected_files)} files, "
            f"found {len(actual_files)}: {[str(f) for f in actual_files]}"
        )

    if expectation.check_content:
        for filepath, expected_content in expectation.check_content.items():
            path = output_dir / filepath
            if not path.exists():
                raise AssertionError(f"File not found for content check: {path}")
            actual_content = path.read_text()
            if expected_content not in actual_content:
                raise AssertionError(
                    f"Expected content '{expected_content}' not found in {path}. "
                    f"Actual content: {actual_content[:500]}..."
                )
