# Development Guidelines

**Goal**: Maintain code quality, consistency, and documentation across rossum-mcp and rossum-agent.

## Critical Constraints

- **No auto-commits** - Only `git commit`/`git push` when explicitly instructed
- **YAGNI** - Don't add functionality until needed. Remove unused code proactively.
- **Tests required** - New features and bug fixes must include tests
- **Docs in sync** - Tool changes require documentation updates

## Commands

| Task | Command |
|------|---------|
| Setup | `pip install -e .` |
| Server | `python server.py` |
| Tests | `pytest` or `pytest path/to/test.py` |
| rossum-deploy tests | `cd rossum-deploy && pytest tests/` (required when modifying `workspace.py`) |
| Lint | `pre-commit run --all-files` |

## Architecture

- **rossum-mcp**: Single-file MCP server (`server.py`), `RossumMCPServer` class, 50 tools
- **rossum-agent**: AI agent with prompts in `rossum_agent/prompts/`, skills in `rossum_agent/skills/`
- Sync API client wrapped in async executors for MCP compatibility
- **New skills**: Add to `rossum_agent/prompts/base_prompt.py` ROSSUM_EXPERT_INTRO section

## Prompt Engineering (rossum-agent)

**rossum-agent uses Opus 4.5** - optimize prompts in `rossum_agent/prompts/` and `rossum_agent/skills/` accordingly:

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
| Comments | Explain why, not what |
| No trailing commas | `[1, 2, 3]` not `[1, 2, 3,]` |
| Noqa comments | Always explain: `# noqa: TC003 - reason` |

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

## Documentation Updates

When adding/modifying tools, update:

| Tool Type | Files to Update |
|-----------|-----------------|
| MCP tools | `rossum_mcp/README.md`, `docs/source/index.rst`, `docs/source/usage.rst` |
| Agent tools | `rossum_agent/README.md`, `docs/source/index.rst`, `docs/source/usage.rst` |

Include: tool name, description, parameters with types, return format with JSON examples.

## Testing

| Scenario | Action |
|----------|--------|
| New functions | Unit tests |
| New MCP tools | Integration tests in `rossum-mcp/tests/test_server.py` |
| New agent tools | Tests in `rossum-agent/tests/` |
| Bug fixes | Regression tests |
| Modified logic | Update + add tests |

Structure: `tests/` mirrors source, pytest fixtures in `conftest.py`, imports at file top.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `ROSSUM_API_TOKEN` | Required - API authentication |
| `ROSSUM_API_BASE_URL` | Required - API endpoint |
| `REDIS_HOST`, `REDIS_PORT` | Optional - Redis connection (default port: 6379) |
| `ROSSUM_MCP_MODE` | Optional - read-only or read-write |
| `TELEPORT_JWT_JWKS_URL` | Optional - enables user isolation via JWT |
| `PUBLIC_URL` | Optional - shareable links on remote servers |

## Planning Files

Place planning documents, task breakdowns, and scratch files in `.agents/` (gitignored).

## Code Review Checklist

- Type hints complete and accurate
- Error handling comprehensive
- Logging appropriate
- No security vulnerabilities
- Follows project conventions
- Tests exist for new functionality
