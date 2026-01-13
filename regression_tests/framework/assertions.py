"""Assertion helpers for regression testing."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from regression_tests.framework.models import (
        FileExpectation,
        RegressionRun,
        TokenBudget,
        ToolExpectation,
    )


def _tool_matches(expected_tool: str | tuple[str, ...], actual_tools: list[str]) -> bool:
    """Check if expected tool (or any alternative) is in actual tools.

    Args:
        expected_tool: Either a single tool name or a tuple of alternatives (OR condition)
        actual_tools: List of actual tool names used

    Returns:
        True if the expected tool (or any alternative) was used
    """
    if isinstance(expected_tool, tuple):
        # OR condition: any of the alternatives is valid
        return any(alt in actual_tools for alt in expected_tool)
    return expected_tool in actual_tools


def assert_tools_match(run: RegressionRun, expectation: ToolExpectation) -> None:
    actual = run.all_tools
    expected = list(expectation.expected_tools)

    if not expected:
        return

    if expectation.mode == "exact_sequence":
        # For exact sequence, flatten tuples to first option for comparison
        flat_expected = [e[0] if isinstance(e, tuple) else e for e in expected]
        if actual != flat_expected:
            raise AssertionError(f"Tool sequence mismatch: expected exactly {flat_expected}, got {actual}")

    elif expectation.mode == "subset":
        missing = [e for e in expected if not _tool_matches(e, actual)]
        if missing:
            raise AssertionError(f"Tool subset mismatch: missing expected tools {missing}, got {actual}")

    else:
        raise ValueError(f"Unknown tool match mode: {expectation.mode}")


def assert_tokens_within_budget(run: RegressionRun, budget: TokenBudget) -> None:
    total = run.total_input_tokens + run.total_output_tokens

    if budget.min_total_tokens is not None:
        assert total >= budget.min_total_tokens, f"Total tokens {total} < minimum {budget.min_total_tokens}"

    if budget.max_total_tokens is not None:
        assert total <= budget.max_total_tokens, f"Total tokens {total} > budget {budget.max_total_tokens}"


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
