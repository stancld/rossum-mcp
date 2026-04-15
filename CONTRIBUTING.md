# Contributing to Rossum Agents

Thanks for your interest in contributing. This repo is **coding-agent-first** — the `AGENTS.md` file gives AI agents everything they need to set up, build, test, and lint, so you can contribute quickly whether you're writing code yourself or pairing with an agent.

---

## What lives where

**Core packages — where most contributions happen:**

- **`rossum-mcp/`** — FastMCP server that wraps the [Rossum API](https://rossum.app/api/docs/) into MCP tools. If you need the agent to *do* something new with the API, start here.
- **`rossum-agent/`** — The AI agent itself (powered by Claude Opus 4.6). It's built around **[skills](rossum-agent/rossum_agent/skills/)** — markdown files that teach the agent how to handle specific domains like formula fields, schema patching, or deployment.

**Auxiliary packages — lower priority for now:**

- `rossum-agent-client/` — Typed Python client for the agent API
- `rossum-agent-tui/` — Terminal UI for development and testing (Node.js)

---

## How to add a new capability

The agent is **skill-first**. Adding a new capability (e.g., formula fields, reasoning fields, business rules) follows this pattern:

1. **Write a skill file** — Create `rossum-agent/rossum_agent/skills/<your-skill>.md`. Look at existing skills in that directory for the format — they define the goal, workflow, and when to use the skill.

2. **Register the skill** — Skills are auto-discovered by `SkillRegistry` from the `skills/` directory. No manual registration needed.

3. **Add MCP tools if needed** — If the Rossum API interaction isn't already covered by an existing tool, add one in `rossum-mcp/rossum_mcp/tools/`. See [Adding an MCP tool](#adding-an-mcp-tool) below.

4. **Add a regression test** — Add a test case in `regression_tests/test_cases.py` that validates the agent handles the new capability correctly. This is how we catch regressions.

---

## Adding an MCP tool

```bash
uv add rossum-api@latest  # always start with the latest SDK
```

1. Check if [`rossum-api`](https://github.com/rossumai/rossum-sdk) already provides models or helpers for what you need.
2. Add the tool function in the appropriate module under `rossum-mcp/rossum_mcp/tools/`.
3. Write tests in `rossum-mcp/tests/tools/`.
4. Update docs: `rossum-mcp/README.md`, `rossum-mcp/TOOLS.md`, `docs/source/index.rst`, `docs/source/usage.rst`, and `docs/source/mcp_reference.rst`.

---

## Adding a regression test

Regression tests validate end-to-end agent behavior — they run real prompts against the agent and check tool usage, token budgets, and output quality.

Add a `RegressionTestCase` to `regression_tests/test_cases.py`:

```python
RegressionTestCase(
    name="my_test",
    description="What this test verifies",
    api_base_url="https://elis.rossum.ai/api/v1",
    prompt="The prompt to send to the agent",
    tool_expectation=ToolExpectation(
        expected_tools=["tool_a", "tool_b"],
        mode=ToolMatchMode.SUBSET,
    ),
    token_budget=TokenBudget(min_total_tokens=20000, max_total_tokens=60000),
    success_criteria=SuccessCriteria(
        required_keywords=["expected", "output"],
        max_steps=5,
    ),
)
```

For domain-specific validation (e.g., checking that a hook was configured correctly), add custom check functions in `regression_tests/custom_checks/`.

See `regression_tests/README.md` for details on running tests and all available options.

---

## Development setup

```bash
git clone https://github.com/rossumai/rossum-agents.git
cd rossum-agents
uv sync --all-extras          # install all packages with dev dependencies
pytest                         # run tests
pre-commit run --all-files     # lint and format (ruff, codespell, etc.)
```

## Code style

- Python 3.12+ with modern syntax
- Type hints everywhere — `str | None` not `Optional[str]`, `list[str]` not `List[str]`
- No `Any` types
- Comments explain *why*, not *what*
- Follow `ruff-format` output

---

## Example prompts for Amp Code / Claude Code

This repo has an `AGENTS.md` that gives agents all the context they need. Keep your prompts short — the agent knows where things live.

🔧 > Add a new MCP tool `list_inbox_emails` that lists emails received by a queue's inbox.

🧠 > Create a new agent skill for managing email templates.

🧪 > Add a regression test that verifies the agent can list queues and describe their schema.

🐛 > The `update_queue` tool doesn't handle queues with no schema. Fix it.

🗺️ > Walk me through how skills get loaded and used by the agent.

✨ > Add a `hook_type` filter parameter to the `list_hooks` tool.

---

## Submitting your changes

Open a PR to `master` and ping **@stancld** for review.
