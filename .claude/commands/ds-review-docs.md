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
| Shared docs | `docs/source/*.rst`, `README.md`, `CHANGELOG.md` |
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

## Output Format

Report findings as:

```
## Documentation Gaps

### Missing
- [ ] `tool_name` - not in rossum-mcp/README.md
- [ ] `skill_name` - not in docs/source/skills_and_subagents.rst

### Outdated
- [ ] `file.md:line` - parameter X removed but still documented

### Changelog Entries Needed
- [ ] rossum-mcp/CHANGELOG.md - added tool_name
```

## Constraints

- No automatic file modifications
- Report gaps only, let user decide priority
- Focus on user-facing documentation, not internal comments
