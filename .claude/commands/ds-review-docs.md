# Review Documentation Sync

**Goal**: Ensure documentation stays synchronized with code changes.

## Scope

| Context | What to Review |
|---------|----------------|
| No argument | Changes on current branch vs `master` |
| Path provided | Documentation for specified module/tool |

## Documentation Inventory

| Component | Documentation Files |
|-----------|---------------------|
| rossum-mcp | `rossum-mcp/README.md`, `rossum-mcp/CHANGELOG.md` |
| rossum-agent | `rossum-agent/README.md`, `rossum-agent/CHANGELOG.md` |
| rossum-deploy | `rossum-deploy/README.md`, `rossum-deploy/CHANGELOG.md` |
| rossum-agent-client | `rossum-agent-client/README.md`, `rossum-agent-client/CHANGELOG.md` |
| rossum-agent-client-ts | `rossum-agent-client-ts/README.md` |
| OpenAPI spec | `rossum-agent/rossum_agent/api/openapi.json` |
| Shared docs | `docs/source/*.rst`, `README.md`, `CHANGELOG.md` |
| Landing page | `docs/landing/index.html`, `docs/landing/blog/` |
| Dev guidelines | `CLAUDE.md`, `AGENTS.md` |

## Review Checklist

| Category | Check For |
|----------|-----------|
| MCP tools | New tools in `rossum-mcp/rossum_mcp/tools/` documented in README and `docs/source/mcp_reference.rst` |
| Agent skills | New skills in `rossum-agent/rossum_agent/skills/` documented in README and `docs/source/skills_and_subagents.rst` |
| Changelogs | New features/fixes added to appropriate CHANGELOG.md |
| API changes | Parameter changes, return type changes reflected in docs |
| Examples | Code examples still valid after changes |
| Env vars | New environment variables documented |
| OpenAPI spec | Endpoints, request/response schemas, and SSE events in `rossum-agent/rossum_agent/api/openapi.json` match source code |

## Approach

| Step | Action |
|------|--------|
| Diff | `git diff master...HEAD --name-only` to identify changed files |
| Categorize | Group changes by component (mcp, agent, deploy) |
| Cross-reference | For each code change, verify matching doc update exists |
| Report | List missing/outdated documentation with specific file paths |

## MCP Tool Documentation Standard

Each MCP tool requires:
- Tool name and description in README.md
- Parameters table with types and descriptions
- Return format with JSON example
- Entry in `docs/source/mcp_reference.rst`

## OpenAPI Spec Review

The OpenAPI spec (`rossum-agent/rossum_agent/api/openapi.json`) is the contract for the `rossum-agent-client` package. It must stay in sync with the actual `rossum-agent` API.

**Source of truth**: FastAPI routes in `rossum-agent/rossum_agent/api/routes/` and Pydantic models in `rossum-agent/rossum_agent/api/models/schemas.py`.

**Regeneration**: `cd rossum-agent && python scripts/generate_openapi.py`

| Check | What to verify |
|-------|----------------|
| Endpoints | All FastAPI routes in `api/routes/*.py` present in spec paths |
| Request/response schemas | Pydantic models in `api/models/schemas.py` match spec component schemas |
| SSE events | All SSE event models (StepEvent, SubAgentProgressEvent, etc.) present in spec schemas |
| SSE event mapping | `x-sse-events` extension on messages endpoint lists all event types |
| Parameters | Required/optional headers, query params, path params match route signatures |
| Error responses | ErrorResponse and HTTPValidationError on relevant endpoints |
| Spec freshness | Run `generate_openapi.py` and diff — no unexpected changes |

**When to flag**: Any change to `rossum-agent/rossum_agent/api/` (routes, models, dependencies) without a corresponding `openapi.json` update.

## Output Format

Report findings as:

```
## Documentation Gaps

### Missing
- [ ] `tool_name` - not in rossum-mcp/README.md
- [ ] `skill_name` - not in docs/source/skills_and_subagents.rst

### Outdated
- [ ] `file.md:line` - parameter X removed but still documented

### OpenAPI Spec Drift
- [ ] `POST /api/v1/endpoint` - in routes but missing from spec
- [ ] `SchemaModel` - in schemas.py but missing from spec components
- [ ] Spec stale - `generate_openapi.py` output differs from committed spec

### Changelog Entries Needed
- [ ] rossum-mcp/CHANGELOG.md - added tool_name
```

## Constraints

- No automatic file modifications
- Report gaps only, let user decide priority
- Focus on user-facing documentation, not internal comments
