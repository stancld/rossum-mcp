# Start New Development Cycle

**Goal**: Prepare $ARGUMENTS for next development cycle after release.

## Valid Packages

| Package | Path | Module |
|---------|------|--------|
| rossum-mcp | `rossum-mcp/` | `rossum_mcp` |
| rossum-agent | `rossum-agent/` | `rossum_agent` |
| rossum-deploy | `rossum-deploy/` | `rossum_deploy` |
| rossum-agent-client | `rossum-agent-client/` | `rossum_agent_client` |

## Changes

| File | Change |
|------|--------|
| `pyproject.toml` | Bump version, add `dev` suffix (e.g., `0.4.0` → `0.5.0dev`) |
| `<module>/__init__.py` | Bump `__version__` to match pyproject.toml |
| `CHANGELOG.md` | Ensure empty `[Unreleased] - YYYY-MM-DD` section at top |

## Version Bump Rules

| Current | Next |
|---------|------|
| `X.Y.Z` | `X.Y+1.0dev` (minor bump) |
| `X.Y.Zdev` | Already dev, verify changelog only |

## Approach

| Step | Action |
|------|--------|
| Validate | Confirm package name is valid |
| Read current | Get version from `pyproject.toml` and `<module>/__init__.py` |
| Bump | Apply version bump with `dev` suffix to both files |
| Changelog | Verify/add empty Unreleased section |
| Verify | Run pre-commit on modified files |
| Output | Provide commit message |

## Output Format

After all changes made, provide:

```
## Ready to Commit

Suggested commit message:
<package>: Start X.Y.Z
```

## Constraints

- No automatic commits
- Use `AskUserQuestion` if major vs minor bump unclear
