"""Regression test case definitions.

Add new test cases to REGRESSION_TEST_CASES list.
Each case defines:
- api_base_url: Rossum API base URL
- api_token: Rossum API token
- prompt: What to ask the agent
- tool_expectation: Which tools should be used
- token_budget: Maximum token usage allowed
- success_criteria: What constitutes success
"""

from __future__ import annotations

from regression_tests.framework.models import (
    FileExpectation,
    MermaidExpectation,
    RegressionTestCase,
    SuccessCriteria,
    TokenBudget,
    ToolExpectation,
)

REGRESSION_TEST_CASES: list[RegressionTestCase] = [
    RegressionTestCase(
        name="explain_aurora_sas_workflow",
        description="Explain a document workflow on a queue",
        api_base_url="https://api.elis.develop.r8.lol/v1",
        rossum_url="https://elis.develop.r8.lol/documents?filtering=%7B%22items%22%3A%5B%7B%22field%22%3A%22queue%22%2C%22value%22%3A%5B%223960192%22%5D%2C%22operator%22%3A%22isAnyOf%22%7D%5D%2C%22logicOperator%22%3A%22and%22%7D&level=queue&page=1&page_size=100",
        prompt="Explain a document workflow and learning workflow on this queue.",
        tool_expectation=ToolExpectation(
            expected_tools=["get_queue", "list_hooks", "get_queue_schema", "get_queue_engine"], mode="subset"
        ),
        token_budget=TokenBudget(min_total_tokens=40000, max_total_tokens=75000),
        success_criteria=SuccessCriteria(
            require_final_answer=True,
            forbid_error=True,
            forbid_tool_errors=True,
            required_keywords=["document_type", "classification", "training", "workflow"],
            max_steps=4,
            mermaid_expectation=MermaidExpectation(
                descriptions=[
                    "Document workflow showing upload, classification, review, and routing to specialized queues",
                    "Learning workflow showing how the classification engine learns from training queues",
                ],
                min_diagrams=2,
            ),
            file_expectation=FileExpectation(),  # no files are expected to be generated
        ),
    ),
    RegressionTestCase(
        name="analyze_broken_document_splitting",
        description="Analyze broken document splitting extension based on invoice ID field",
        api_base_url="https://api.elis.develop.r8.lol/v1",
        rossum_url=None,
        prompt=(
            "Please, investigate the errors with document splitting extension based on extracted invoice ID field on the queue 4014559.\n\n"
            "Give me one-paragraph executive summary for roasting the account manager - store it in `roast.md`."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "get_queue",
                "list_hooks",
                "get_queue_schema",
                "list_hook_logs",
                "list_annotations",
                "get_hook",
                "search_knowledge_base",
                "write_file",
            ],
            mode="subset",
        ),
        token_budget=TokenBudget(min_total_tokens=120000, max_total_tokens=200000),
        success_criteria=SuccessCriteria(
            require_final_answer=True,
            forbid_error=True,
            forbid_tool_errors=True,
            required_keywords=["splitting", "invoice"],
            max_steps=6,
            file_expectation=FileExpectation(expected_files=["roast.md"]),
        ),
    ),
]
