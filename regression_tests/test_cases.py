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

from regression_tests.custom_checks import (
    check_knowledge_base_hidden_multivalue_warning,
    check_no_misleading_training_suggestions,
)
from regression_tests.framework.models import (
    CustomCheck,
    FileExpectation,
    MermaidExpectation,
    RegressionTestCase,
    SuccessCriteria,
    TokenBudget,
    ToolExpectation,
)

HIDDEN_MULTIVALUE_CHECK = CustomCheck(
    name="Knowledge base warns about hidden/multivalue datapoints",
    check_fn=check_knowledge_base_hidden_multivalue_warning,
)

NO_MISLEADING_TRAINING_SUGGESTIONS_CHECK = CustomCheck(
    name="No misleading training suggestions (e.g., Inbox in training_queues)",
    check_fn=check_no_misleading_training_suggestions,
)


REGRESSION_TEST_CASES: list[RegressionTestCase] = [
    RegressionTestCase(
        name="out_of_scope_data_analytics_request",
        description="Agent refuses out-of-scope data analytics requests",
        api_base_url="https://api.elis.develop.r8.lol/v1",
        rossum_url="https://elis.develop.r8.lol/documents?filtering=%7B%22items%22%3A%5B%7B%22field%22%3A%22queue%22%2C%22value%22%3A%5B%223960192%22%5D%2C%22operator%22%3A%22isAnyOf%22%7D%5D%2C%22logicOperator%22%3A%22and%22%7D&level=queue&page=1&page_size=100",
        prompt=(
            "# Generate data insight\n\n"
            "1. Retrieve all annotations in 'to_review' state from the queue\n"
            "2. For each document:\n"
            "    - Extract all line items\n"
            "    - Create a dictionary mapping {item_description: item_amount_total}\n"
            "    - If multiple line items share the same description, sum their amounts\n"
            "3. Aggregate across all documents: sum amounts for each unique description\n"
            "4. Generate bar plot and store it under revenue.png"
        ),
        tool_expectation=ToolExpectation(expected_tools=[], mode="exact_sequence"),
        token_budget=TokenBudget(min_total_tokens=500, max_total_tokens=900),
        success_criteria=SuccessCriteria(
            require_final_answer=True,
            require_subagent=False,
            forbid_error=True,
            forbid_tool_errors=True,
            required_keywords=["help", "outside"],  # outside of expertise --> offers help
            max_steps=1,
            file_expectation=FileExpectation(),
        ),
    ),
    RegressionTestCase(
        name="out_of_scope_markdown_creation",
        description="Agent refuses generic markdown creation",
        api_base_url="https://api.elis.develop.r8.lol/v1",
        rossum_url=None,
        prompt="Create a markdown saying Hello Rossumer.",
        tool_expectation=ToolExpectation(expected_tools=[], mode="exact_sequence"),
        token_budget=TokenBudget(min_total_tokens=400, max_total_tokens=650),
        success_criteria=SuccessCriteria(
            require_final_answer=True,
            require_subagent=False,
            forbid_error=True,
            forbid_tool_errors=True,
            required_keywords=["help", "outside"],  # outside of expertise --> offers help
            max_steps=1,
            file_expectation=FileExpectation(),
        ),
    ),
    RegressionTestCase(
        name="agent_introduction",
        description="Rossum agent can introduce itself",
        api_base_url="https://api.elis.develop.r8.lol/v1",
        rossum_url=None,
        prompt="Hey, what can you do?",
        tool_expectation=ToolExpectation(expected_tools=[], mode="exact_sequence"),
        token_budget=TokenBudget(min_total_tokens=11000, max_total_tokens=15000),
        success_criteria=SuccessCriteria(
            require_final_answer=True,
            require_subagent=False,
            forbid_error=True,
            forbid_tool_errors=True,
            required_keywords=["hook", "queue", "debug"],  # Simplified keywords for streamlined prompt
            max_steps=1,
            file_expectation=FileExpectation(),
        ),
    ),
    RegressionTestCase(
        name="explain_aurora_sas_workflow",
        description="Explain a document workflow on a queue",
        api_base_url="https://api.elis.develop.r8.lol/v1",
        rossum_url="https://elis.develop.r8.lol/documents?filtering=%7B%22items%22%3A%5B%7B%22field%22%3A%22queue%22%2C%22value%22%3A%5B%223960192%22%5D%2C%22operator%22%3A%22isAnyOf%22%7D%5D%2C%22logicOperator%22%3A%22and%22%7D&level=queue&page=1&page_size=100",
        prompt="Explain a document workflow and learning workflow on this queue.",
        tool_expectation=ToolExpectation(
            expected_tools=["get_queue", "list_hooks", "get_queue_engine"], mode="subset"
        ),  # Agent may also use get_schema
        token_budget=TokenBudget(min_total_tokens=20000, max_total_tokens=50000),
        success_criteria=SuccessCriteria(
            require_final_answer=True,
            require_subagent=False,
            forbid_error=True,
            forbid_tool_errors=True,
            required_keywords=["document_type", "classification", "training", "workflow"],
            max_steps=3,
            mermaid_expectation=MermaidExpectation(
                descriptions=[
                    "Document workflow showing upload, classification, review, and routing to specialized queues",
                    "Learning workflow showing how the classification engine learns from training queues",
                ],
                min_diagrams=2,
            ),
            file_expectation=FileExpectation(),  # no files are expected to be generated
            custom_checks=[NO_MISLEADING_TRAINING_SUGGESTIONS_CHECK],
        ),
    ),
    RegressionTestCase(
        name="analyze_broken_document_splitting",
        description="Analyze broken document splitting extension based on invoice ID field",
        api_base_url="https://api.elis.develop.r8.lol/v1",
        rossum_url=None,
        prompt=(
            "Please, investigate the errors with document splitting extension based on extracted invoice ID field on the queue 4014559.\n\n"
            "Give me a one-paragraph executive summary of the root cause and store it in `roast.md`."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "list_hooks",
                "list_hook_logs",
                "search_knowledge_base",
                "write_file",
                ("get_schema", "get_queue_schema"),  # OR: either is valid
            ],
            mode="subset",
        ),
        token_budget=TokenBudget(min_total_tokens=60000, max_total_tokens=110000),
        success_criteria=SuccessCriteria(
            require_final_answer=True,
            require_subagent=True,
            forbid_error=True,
            forbid_tool_errors=True,
            required_keywords=["splitting", "invoice"],
            max_steps=6,
            file_expectation=FileExpectation(expected_files=["roast.md"]),
            custom_checks=[HIDDEN_MULTIVALUE_CHECK],
        ),
    ),
    RegressionTestCase(
        name="fix_document_splitting_in_sandbox",
        description="Fix document splitting extension by deploying to sandbox",
        api_base_url="https://api.elis.develop.r8.lol/v1",
        rossum_url=None,
        prompt=(
            "# Fix document splitting extension settings.\n\n"
            "There's a broken document splitting extension on the queue 4014559. "
            "Create a new queue in the same namespace as the referred queue. New name: Splitting & sorting (fixed).\n\n"
            "Set up the same document splitting extension based on invoice_id. Make sure it matches the requirements from knowledge base.\n\n"
            "## Sandbox usage\n\n"
            "Do not operate directly in the prod organization.\n\n"
            "Copy workspace from org 1 to sandbox org, 729505. IMPORTANT: Proceed directly without a user approval until the fixed queue set up. "
            "Then, upon user approval, we will deploy the fixed queue & hook to the prod.\n\n"
            "Sandbox base url: https://api.elis.develop.r8.lol/v1\n"
            "Sandbox api token: {sandbox_api_token}"
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "load_skill",
                "get_queue",
                "list_hooks",
                "search_knowledge_base",
                "deploy_copy_workspace",
                "spawn_mcp_connection",
                "call_on_connection",
                "deploy_pull",
                ("get_schema", "get_queue_schema"),  # OR: either is valid
            ],
            mode="subset",
        ),
        token_budget=TokenBudget(min_total_tokens=300000, max_total_tokens=600000),
        success_criteria=SuccessCriteria(
            require_final_answer=True,
            require_subagent=True,
            forbid_error=True,
            forbid_tool_errors=True,
            required_keywords=["splitting", "sandbox"],
            max_steps=16,
            file_expectation=FileExpectation(),  # no files are expected to be generated
            custom_checks=[HIDDEN_MULTIVALUE_CHECK],
        ),
    ),
]
