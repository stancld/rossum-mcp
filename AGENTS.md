# Development Guidelines

**Goal**: Maintain code quality, consistency, and documentation across rossum-agents packages (rossum-mcp, rossum-agent, rossum-agent-client).

## Critical Constraints

- **No auto-commits** - Only `git commit`/`git push` when explicitly instructed
- **Simplicity first** - Design the simplest solution that works. Fewer abstractions, fewer indirections, fewer layers. If a reader needs to jump through hoops to understand the code, it's too complex.
- **YAGNI** - Don't add functionality until needed. Remove unused code proactively.
- **Tests required** - New features and bug fixes must include tests
- **Docs in sync** - Tool changes require documentation updates
- **Changelog PR references** - When adding changelog entries, include the PR hyperlink (e.g. `[#123](https://github.com/rossumai/rossum-agents/pull/123)`) if available

## Commands

| Task | Command |
|------|---------|
| Setup | `uv sync` or `uv pip install -e .` |
| Server | `rossum-mcp` (installed) or `python -m rossum_mcp.server` (dev) |
| Tests | `pytest` or `pytest path/to/test.py` |
| Lint | `pre-commit run --all-files` |
| TUI lint | `cd rossum-agent-tui && npm run lint && npm run format:check && npm run typecheck` |

## Architecture

- **rossum-mcp**: FastMCP server in `rossum_mcp/server.py`; tools registered from `rossum_mcp/tools/` modules
- **rossum-agent**: AI agent with system prompt in `rossum_agent/system_prompt.py`, skills in `rossum_agent/skills/`
- **rossum-agent-tui**: Development test-bed TUI for rossum-agent. Not production code — no tests required. Always use `/ink-tui-best-practices` skill when working on this package.
- **New skills**: Create `rossum_agent/skills/<slug>.md` — auto-discovered by `SkillRegistry`

## Prompt Engineering (rossum-agent)

**rossum-agent uses Opus 4.6** - optimize prompts in `rossum_agent/system_prompt.py` and `rossum_agent/skills/` accordingly:

| Principle | Implementation |
|-----------|----------------|
| Goals over procedures | "Goal: Deploy safely" not step-by-step instructions |
| Constraints over explanations | "Never mix credentials" - Opus infers consequences |
| Tables for structure | More token-efficient than prose lists |
| No redundancy | Don't explain what Opus can infer |
| Facts not warnings | State rules directly, skip "IMPORTANT" preambles |

## Code Style

| Rule | Example |
|------|---------|
| Python 3.12+ | Modern syntax required |
| Type hints | `str \| None` not `Optional[str]`, `list[str]` not `List[str]` |
| No `Any` | Use specific types |
| Imports | Standard library first, `from pathlib import Path` |
| No lazy imports | All imports at module level. No `import` inside functions/methods. |
| Comments | Explain why, not what |
| No trailing commas | Follow ruff-format output |
| Logging | f-strings in `logger.*()` calls are fine — prefer `logger.info(f"...")` over `%s` style |
| Noqa comments | Always explain: `# noqa: TC003 - reason` |
| No hardcoded `/tmp` | Use `tempfile` module or `/mock/...` paths in tests — CodeFactor runs Bandit (B108) |

## FastMCP Tools (rossum-mcp)

**Constraint**: Don't duplicate info between `description` and docstring.

```python
@mcp.tool(description="List users. Filter by username/email. Returns URLs usable as token_owner.")
async def list_users(
    username: str | None = None,
    email: str | None = None,
) -> list[User]:
    # No docstring - description + type hints sufficient
    ...
```

Add docstring only when: non-obvious formats, complex filtering, unclear defaults.

Import return types at module level (not TYPE_CHECKING) for FastMCP serialization.

### Adding New MCP Tools

| Step | Action |
|------|--------|
| Install latest SDK | Run `uv add rossum-api@latest` to get the newest `rossum-api` package |
| Leverage SDK | Check if `rossum-api` already provides models, dataclasses, type literals, or helper methods for the feature before writing custom code |
| Private SDK access | Usage of private/internal APIs in `rossum-api` is allowed — we control both packages |
| Use typed constructs | Prefer dataclasses, `Literal` types, enums, and typed models from `rossum-api` over plain strings or untyped dicts |
| API docs fallback | If the SDK doesn't cover the needed functionality, consult https://rossum.app/api/docs for the raw API spec |

### Adding New Rossum Capabilities (formula fields, reasoning fields, etc.)

When implementing support for Rossum-specific features, research them first:

| Source | URL | Purpose |
|--------|-----|---------|
| Knowledge Base | https://knowledge-base.rossum.ai/ | Feature concepts, configuration, and usage guides |
| API Docs | https://rossum.app/api/docs | API endpoints, request/response schemas |

## Documentation Updates

When adding/modifying tools, update:

| Tool Type | Files to Update |
|-----------|-----------------|
| MCP tools | `rossum-mcp/README.md`, `docs/source/rossum-mcp/tools.rst`, `docs/source/rossum-mcp/configuration.rst` |
| Agent tools | `rossum-agent/README.md`, `docs/source/rossum-agent/tools.rst`, `docs/source/rossum-agent/skills.rst`, `docs/source/rossum-agent/subagents.rst` |
| Agent API | Regenerate OpenAPI spec and TUI types (see [OpenAPI Spec](#openapi-spec-rossum-agent-client) section) |

Include: tool name, description, parameters with types, return format with JSON examples.

### OpenAPI Spec (rossum-agent-client)

The OpenAPI spec is the contract for `rossum-agent-client` and `rossum-agent-tui`. Keep it in sync when changing `rossum-agent/rossum_agent/api/` (routes, models, dependencies).

| Trigger | Action |
|---------|--------|
| New/changed endpoint | Regenerate spec |
| New/changed Pydantic model | Regenerate spec |
| New wire event type | Add model to `_SSE_EVENT_MODELS` list in `scripts/generate_openapi.py`, regenerate spec |
| Changed wire event fields | Regenerate spec |

Regeneration pipeline:

```bash
# 1. Regenerate OpenAPI spec from Python models
cd rossum-agent && python scripts/generate_openapi.py

# 2. Regenerate TypeScript types from the spec (single source in rossum-agent-client-ts)
cd rossum-agent-client-ts && npm run generate
```

The API reference page at `/api-reference/` has a version selector dropdown. CI collects versioned specs from GitHub Release assets (uploaded by the release workflow).

Note: `rossum-agent-tui` imports OpenAPI types from `rossum-agent-client` (no duplicate `generated.ts`).

### rossum-agent-tui Type Generation

TUI imports OpenAPI types from `rossum-agent-client` — there is no separate `generated.ts` in the TUI package. The single source of truth is `rossum-agent-client-ts/src/generated.ts`.

| Rule | Detail |
|------|--------|
| Source of truth | `rossum-agent-client-ts/src/generated.ts` (generated from `rossum-agent/rossum_agent/api/openapi.json`) |
| Generate command | `cd rossum-agent-client-ts && npm run generate` |
| TUI convenience | `cd rossum-agent-tui && npm run generate` (delegates to client-ts) |
| Import types | TUI imports `components` from `rossum-agent-client` |
| After API changes | Regenerate OpenAPI spec, then run generate in client-ts |

## Testing

| Scenario | Action |
|----------|--------|
| New functions | Unit tests |
| New MCP tools | Integration tests in `rossum-mcp/tests/tools/` and catalog tests in `rossum-mcp/tests/test_catalog.py` |
| New agent tools | Tests in `rossum-agent/tests/` |
| Bug fixes | Regression tests |
| Modified logic | Update + add tests |

Structure: `tests/` mirrors source, pytest fixtures in `conftest.py`, imports at file top. Use `pytest.mark.parametrize` to eliminate repetitive test functions that differ only in inputs/expected outputs.

**Exception**: `rossum-agent-tui` — dev-only test-bed, tests not required.

## Streaming Contract (rossum-agent → rossum-agent-tui)

AI SDK UI Message Stream v1 compatible. Wire protocol: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol

Response header: `x-vercel-ai-ui-message-stream: v1`. Each line is `data: <json>\n\n` where the JSON `type` field discriminates the event. Stream ends with `data: [DONE]\n\n`.

### Wire Event Types

Adapter in `rossum_agent/api/routes/stream_adapter.py` converts internal `AgentStep`/`StreamEvent` → wire event dicts.

| Wire `type` | When emitted |
|-------------|--------------|
| `start` | Stream begins (emitted by route handler) |
| `finish` | Stream ends (before `[DONE]` sentinel) |
| `reasoning-start` | Reasoning block opens (`id`) |
| `reasoning-delta` | Incremental reasoning content (`id`, `delta`) |
| `reasoning-end` | Reasoning block closes (`id`) |
| `text-start` | New text block opens |
| `text-delta` | Incremental text content |
| `text-end` | Text block closes |
| `tool-input-start` | Tool call begins (`toolCallId`, `toolName`) |
| `tool-input-available` | Tool call args ready (`toolCallId`, `toolName`, `input`) |
| `tool-output-available` | Tool result ready (`toolCallId`, `output`) |
| `error` | Error event |
| `data-agent-question` | Structured question from agent (payload in `data` field) |
| `data-task-snapshot` | Full task list snapshot (payload in `data` field) |
| `data-file-created` | File created during agent run (payload in `data` field) |
| `data-final-answer` | Final answer from agent (payload in `data` field, ignored by elis-frontend) |

### Stream Lifecycle

| Phase | Detail |
|-------|--------|
| Start | `start` event emitted first |
| Reasoning | Reasoning blocks open/close with start/delta/end triplets |
| Content | Text blocks open/close with start/delta/end triplets |
| Tool use | Tool input start/available, then output available per tool call |
| Finish | Open reasoning/text blocks closed, then `finish`, then `data: [DONE]\n\n` |

### Internal Adapter

The adapter layer (`stream_adapter.py`) converts internal events to wire format:

| Internal event | Wire event(s) |
|---------------|---------------|
| `ReasoningStep` | `reasoning-start` + `reasoning-delta` (+ `reasoning-end` when finalized) |
| `TextDeltaStep` (intermediate) | `reasoning-start` + `reasoning-delta` (+ `reasoning-end` when finalized) |
| `TextDeltaStep` (final answer) | `text-start` + `text-delta` (+ `text-end` when finalized) |
| `FinalAnswerStep` | `data-final-answer` (+ `reasoning-end` if reasoning block was open) |
| `ErrorStep` | `error` |
| `ToolStartStep` | `tool-input-start` + `tool-input-available` (per new tool call, deduplicated) |
| `ToolResultStep` | `tool-output-available` (per result) |
| `AgentQuestionPart` | `data-agent-question` |
| `TaskSnapshotPart` | `data-task-snapshot` |
| `FileCreatedPart` | `data-file-created` |
| `SubAgentProgressPart` | Dropped |
| `StreamDoneEvent` | Captured for metadata; not emitted directly |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `ROSSUM_API_TOKEN` | Required - API authentication |
| `ROSSUM_API_BASE_URL` | Required - API endpoint |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Optional - PostgreSQL connection (default: localhost:5432) |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Optional - PostgreSQL credentials (default: rossum_agent/rossum/rossum) |
| `VALKEY_HOST`, `VALKEY_PORT` | Optional - Valkey connection for change tracking (default: localhost:6379) |
| `VALKEY_PASSWORD` | Optional - Valkey authentication password |
| `ROSSUM_MCP_MODE` | Optional - read-only or read-write |
| `ROSSUM_MCP_LOG_LEVEL` | Optional - MCP server log level (default: INFO) |
| `ROSSUM_MCP_LOG_FORMAT` | Optional - MCP server log format: json or console (default: console) |
| `ROSSUM_AGENT_LOG_LEVEL` | Optional - Agent API log level (default: INFO) |
| `ROSSUM_AGENT_LOG_FORMAT` | Optional - Agent API log format: json or console (default: console) |
| `AWS_REGION` | Optional - AWS region for Bedrock (default: us-east-1) |
| `AWS_BEDROCK_MODEL_ARN` | Optional - Custom ARN for Opus model |
| `AWS_BEDROCK_MODEL_ARN_SMALL` | Optional - Custom ARN for Haiku model |
| `ADDITIONAL_ALLOWED_ROSSUM_HOSTS` | Optional - Comma-separated regex for extra allowed API hosts |
| `SLACK_BOT_TOKEN` | Optional - Slack bot token for reports |
| `SLACK_CHANNEL` | Optional - Slack channel for reports |
| `ROSSUM_AGENT_API_URL` | Optional - Agent API URL (rossum-agent-client) |
| `ROSSUM_AGENT_PERSONA` | Optional - Agent persona: default or cautious |
| `ROSSUM_FRONTEND_REPO` | Optional - Absolute path to the Rossum WebUI repo for UI cross-referencing |

## Planning Files

Place planning documents, task breakdowns, and scratch files in `.agents/` (gitignored).

## Code Review Checklist

- Type hints complete and accurate
- Error handling comprehensive
- Logging appropriate
- No security vulnerabilities
- Follows project conventions
- Tests exist for new functionality
