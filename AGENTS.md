# Development Guidelines

**Goal**: Maintain code quality, consistency, and documentation across rossum-agents packages (rossum-mcp, rossum-agent, rossum-deploy, rossum-agent-client).

## Critical Constraints

- **No auto-commits** - Only `git commit`/`git push` when explicitly instructed
- **Simplicity first** - Design the simplest solution that works. Fewer abstractions, fewer indirections, fewer layers. If a reader needs to jump through hoops to understand the code, it's too complex.
- **YAGNI** - Don't add functionality until needed. Remove unused code proactively.
- **Tests required** - New features and bug fixes must include tests
- **Docs in sync** - Tool changes require documentation updates

## Commands

| Task | Command |
|------|---------|
| Setup | `uv sync` or `uv pip install -e .` |
| Server | `rossum-mcp` (installed) or `python -m rossum_mcp.server` (dev) |
| Tests | `pytest` or `pytest path/to/test.py` |
| rossum-deploy tests | `cd rossum-deploy && pytest tests/` (required when modifying `workspace.py`) |
| Lint | `pre-commit run --all-files` |
| TUI lint | `cd rossum-agent-tui && npm run lint && npm run format:check && npm run typecheck` |

## Architecture

- **rossum-mcp**: FastMCP server in `rossum_mcp/server.py`; tools registered from `rossum_mcp/tools/` modules
- **rossum-agent**: AI agent with prompts in `rossum_agent/prompts/`, skills in `rossum_agent/skills/`
- **rossum-agent-tui**: Development test-bed TUI for rossum-agent. Not production code — no tests required.
- **New skills**: Add to `rossum_agent/prompts/base_prompt.py` ROSSUM_EXPERT_INTRO section

## Prompt Engineering (rossum-agent)

**rossum-agent uses Opus 4.6** - optimize prompts in `rossum_agent/prompts/` and `rossum_agent/skills/` accordingly:

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
| MCP tools | `rossum-mcp/README.md`, `docs/source/index.rst`, `docs/source/usage.rst`, `docs/source/mcp_reference.rst` |
| Agent tools | `rossum-agent/README.md`, `docs/source/index.rst`, `docs/source/usage.rst`, `docs/source/skills_and_subagents.rst` |
| Agent API | Regenerate OpenAPI spec and TUI types (see [OpenAPI Spec](#openapi-spec-rossum-agent-client) section) |

Include: tool name, description, parameters with types, return format with JSON examples.

### OpenAPI Spec (rossum-agent-client)

The OpenAPI spec is the contract for `rossum-agent-client` and `rossum-agent-tui`. Keep it in sync when changing `rossum-agent/rossum_agent/api/` (routes, models, dependencies).

| Trigger | Action |
|---------|--------|
| New/changed endpoint | Regenerate spec |
| New/changed Pydantic model | Regenerate spec |
| New SSE event type | Add model to `_SSE_EVENT_MODELS` list in `api/main.py`, regenerate spec |
| Changed SSE event fields | Regenerate spec |

Regeneration pipeline:

```bash
# 1. Regenerate OpenAPI spec from Python models
cd rossum-agent && python scripts/generate_openapi.py

# 2. Regenerate TypeScript types from the spec (single source in rossum-agent-client-ts)
cd rossum-agent-client-ts && npm run generate
```

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

Structure: `tests/` mirrors source, pytest fixtures in `conftest.py`, imports at file top.

**Exception**: `rossum-agent-tui` — dev-only test-bed, tests not required.

## SSE Streaming Contract (rossum-agent → rossum-agent-tui)

### SSE Event Types

Backend (`messages.py`) emits these SSE event names with corresponding payloads:

| SSE `event:` | Payload model (Python) | TS type (TUI) | Notes |
|--------------|------------------------|---------------|-------|
| `step` | `StepEvent` | `StepEvent` | Main event for all agent steps |
| `sub_agent_progress` | `SubAgentProgressEvent` | `SubAgentProgressEvent` | Sub-agent iteration updates |
| `sub_agent_text` | `SubAgentTextEvent` | `SubAgentTextEvent` | Sub-agent text streaming |
| `task_snapshot` | `TaskSnapshotEvent` | `TaskSnapshotEvent` | Task tracker state |
| `agent_question` | `AgentQuestionEvent` | `AgentQuestionEvent` | Structured question from agent to user |
| `file_created` | `FileCreatedEvent` | `FileCreatedEvent` | Output file notification |
| `done` | `StreamDoneEvent` | `StreamDoneEvent` | Final event with token usage |

### StepEvent.type Values

`StepEvent.type` is a `Literal` union shared across both sides:

| Type | When emitted | `is_streaming` | Key fields |
|------|-------------|----------------|------------|
| `thinking` | Model's chain-of-thought reasoning | `true` while streaming, `false` when finalized | `content` |
| `intermediate` | Model's response text before tool calls | `true` while streaming | `content` |
| `tool_start` | Tool execution begins | implicitly streaming (not explicitly marked) | `tool_name`, `tool_arguments`, `tool_progress` |
| `tool_result` | Tool execution completes | always `false` | `tool_name`, `result`, `is_error` |
| `final_answer` | Model's final response | `true` while streaming, `is_final=true` when done | `content` |
| `error` | Agent execution error | N/A, `is_final=true` | `content` |

### Streaming Lifecycle

| Behavior | Detail |
|----------|--------|
| `is_streaming: true` | Step is still in progress; may be replaced by updated events with the same `step_number`/`type` |
| `is_streaming: false` | Step is finalized; safe to commit to history |
| Finalization guarantee | Every `is_streaming: true` step is eventually followed by an `is_streaming: false` event for the same `step_number`. The finalized event carries the authoritative type (e.g. text streamed as `final_answer` may be finalized as `intermediate` once tool_use blocks arrive). |
| TUI implication | When a finalized event arrives for the same `step_number` as the current streaming step, replace (don't commit) the stale streaming version. When `step_number` differs, commit the previous streaming step before replacing. |

### Tool Use Event Flow

The agent signals tool usage through two paired `StepEvent` types sharing the same `step_number`:

| Event type | Source | Key fields | When emitted |
|------------|--------|------------|--------------|
| `tool_start` | `agent_service._create_tool_start_event` | `tool_name`, `tool_arguments`, `tool_progress` | When the agent begins executing a tool |
| `tool_result` | `agent_service._create_tool_result_event` | `tool_name`, `result`, `is_error` | After tool execution completes (only emitted when `is_streaming=false`) |

**Pairing logic** (TUI `buildChatItems.ts`): `tool_result` steps are indexed by `stepNumber` into a map; each `tool_start` is paired with its matching `tool_result` to produce a single `ChatItem` of `kind: "tool_call"`.

**Rendering** (`ToolCall.tsx`): Tool calls are expandable. Collapsed shows tool name, args summary, status icon (✓/✗), and result preview. Expanded shows full arguments and full result.

**During streaming**: While a tool is executing, the TUI shows a `StreamingIndicator` with a spinner and tool name/progress. Sub-agent progress (for compound tools like `patch_schema_with_subagent`) is shown inline.

### Field Serialization

- Backend uses Pydantic `model_dump_json()` → snake_case keys (`step_number`, `tool_name`, `is_streaming`)
- TUI `StepEvent` interface mirrors snake_case field names directly
- TUI converts to camelCase `CompletedStep` via `stepToCompleted()` in `useChat.ts` for internal state
- `tool_progress`: Python `tuple[int, int]` serializes as JSON `[int, int]`; TS declares `number[] | null` (works but could be tightened to `[number, number] | null`)

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `ROSSUM_API_TOKEN` | Required - API authentication |
| `ROSSUM_API_BASE_URL` | Required - API endpoint |
| `CHAT_STORAGE_BACKEND` | Optional - `postgres` (default) or `redis` for chat persistence |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Optional - PostgreSQL connection (default: localhost:5432) |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Optional - PostgreSQL credentials (default: rossum_agent/rossum/rossum) |
| `REDIS_HOST`, `REDIS_PORT` | Optional - Redis connection for change tracking (default: localhost:6379) |
| `ROSSUM_MCP_MODE` | Optional - read-only or read-write |
| `ROSSUM_MCP_LOG_LEVEL` | Optional - MCP server log level (default: INFO) |
| `AWS_REGION` | Optional - AWS region for Bedrock (default: us-east-1) |
| `AWS_BEDROCK_MODEL_ARN` | Optional - Custom ARN for Opus model |
| `AWS_BEDROCK_MODEL_ARN_SMALL` | Optional - Custom ARN for Haiku model |
| `ROSSUM_KB_DATA_PATH` | Optional - Path to local knowledge base JSON |
| `ADDITIONAL_ALLOWED_ROSSUM_HOSTS` | Optional - Comma-separated regex for extra allowed API hosts |
| `SLACK_BOT_TOKEN` | Optional - Slack bot token for reports |
| `SLACK_CHANNEL` | Optional - Slack channel for reports |
| `ROSSUM_AGENT_API_URL` | Optional - Agent API URL (rossum-agent-client) |
| `ROSSUM_AGENT_PERSONA` | Optional - Agent persona: default or cautious |

## Planning Files

Place planning documents, task breakdowns, and scratch files in `.agents/` (gitignored).

## Code Review Checklist

- Type hints complete and accurate
- Error handling comprehensive
- Logging appropriate
- No security vulnerabilities
- Follows project conventions
- Tests exist for new functionality
