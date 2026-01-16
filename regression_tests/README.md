# Regression Tests

Local regression testing framework for rossum-agent.

## Overview

This framework tests that the agent:
1. Uses expected tools for a given task
2. Stays within token budgets
3. Completes tasks successfully
4. Produces answers with required content
5. Generates valid mermaid diagrams (LLM-evaluated)

## Running Tests

```bash
# Run with API token from environment variable
export ROSSUM_API_TOKEN="your_token_here"
pytest regression_tests/ -v -s

# Or pass token via command line
pytest regression_tests/ -v -s --api-token="your_token_here"

# Show the full final answer in output
pytest regression_tests/ -v -s --show-answer

# Run a specific test by name
pytest regression_tests/ -v -k "test_name"
```

**Token priority**: `--api-token` flag > `.env` `TEST_NAME_API_TOKEN` > `.env` `DEFAULT_API_TOKEN` > test case `api_token`

## .env File Setup

Create `regression_tests/.env` with tokens for each test:

```bash
# Token for specific test (TEST_NAME in uppercase, hyphens become underscores)
MY_TEST_API_TOKEN=token_for_my_test
ANOTHER_TEST_API_TOKEN=token_for_another_test

# Fallback token if no specific token found
DEFAULT_API_TOKEN=fallback_token
```

## Adding Test Cases

Edit `test_cases.py` and add a new `RegressionTestCase`:

```python
RegressionTestCase(
    name="my_test",
    description="What this test verifies",
    api_base_url="https://elis.rossum.ai/api/v1",
    prompt="The prompt to send to the agent",
    # api_token is optional - provide via env var or --api-token flag
    tool_expectation=ToolExpectation(
        expected_tools=["list_queues", "get_annotation"],
        mode=ToolMatchMode.SUBSET,
    ),
    token_budget=TokenBudget(
        min_total_tokens=40000,  # Ensure meaningful work
        max_total_tokens=75000,
    ),
    success_criteria=SuccessCriteria(
        required_keywords=["invoice", "workflow"],
        max_steps=5,
        mermaid_expectation=MermaidExpectation(
            descriptions=["Diagram showing document flow"],
            min_diagrams=1,
        ),
    ),
),
```

## Tool Matching Modes

Use `ToolMatchMode` enum:

- **SUBSET**: All expected tools must appear (order doesn't matter, extras allowed)
- **EXACT_SEQUENCE**: Tools must match exactly in order

## Token Budget Options

- `min_total_tokens`: Minimum combined tokens (ensure meaningful work)
- `max_input_tokens`: Total input tokens across all steps
- `max_output_tokens`: Total output tokens across all steps
- `max_total_tokens`: Combined input + output tokens
- `max_input_tokens_per_step`: Per-step input limit
- `max_output_tokens_per_step`: Per-step output limit

## Success Criteria

All tests automatically require: final answer present, no agent errors, no tool errors.

Configurable options:
- `required_keywords`: Keywords that must appear in the final answer (case-insensitive)
- `max_steps`: Maximum number of agent steps allowed
- `require_subagent`: Require that an Opus sub-agent was used (default: False)
- `mermaid_expectation`: Validate mermaid diagrams with LLM (see below)
- `file_expectation`: Expected output files (see below)
- `custom_checks`: List of custom validation functions

## Mermaid Diagram Validation

Validate that the agent produces mermaid diagrams matching expected descriptions. Uses Claude Haiku to evaluate if diagrams match:

```python
from regression_tests.framework.models import MermaidExpectation

RegressionTestCase(
    # ...
    success_criteria=SuccessCriteria(
        mermaid_expectation=MermaidExpectation(
            descriptions=[
                "Document workflow showing upload, classification, and routing",
                "Learning workflow showing how the engine learns from training data",
            ],
            min_diagrams=2,
        ),
    ),
)
```

## File Expectations

Check if the agent creates expected files:

```python
from regression_tests.framework.models import FileExpectation

RegressionTestCase(
    # ...
    success_criteria=SuccessCriteria(
        file_expectation=FileExpectation(
            expected_files=["output/report.json", "output/summary.txt"],
            check_exists=True,
            check_content={"output/report.json": '"status": "success"'},
        ),
    ),
)
```

## Custom Validation

```python
def check_mentions_invoice(steps):
    final = [s for s in steps if s.is_final][-1]
    assert "invoice" in final.final_answer.lower(), "Expected mention of invoice"

RegressionTestCase(
    name="invoice_check",
    # ...
    success_criteria=SuccessCriteria(
        custom_check=check_mentions_invoice,
    ),
)
```

## Requirements

- AWS credentials configured for Bedrock access
- Valid Rossum API token for the target environment
