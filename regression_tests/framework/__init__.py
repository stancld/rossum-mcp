"""Regression testing framework for rossum-agent."""

from __future__ import annotations

from regression_tests.framework.assertions import (
    assert_files_created,
    assert_tokens_within_budget,
    assert_tools_match,
)
from regression_tests.framework.models import (
    FileExpectation,
    RegressionRun,
    RegressionTestCase,
    SuccessCriteria,
    TokenBudget,
    ToolExpectation,
    ToolMatchMode,
)
from regression_tests.framework.runner import run_regression_test

__all__ = [
    "FileExpectation",
    "RegressionRun",
    "RegressionTestCase",
    "SuccessCriteria",
    "TokenBudget",
    "ToolExpectation",
    "ToolMatchMode",
    "assert_files_created",
    "assert_tokens_within_budget",
    "assert_tools_match",
    "run_regression_test",
]
