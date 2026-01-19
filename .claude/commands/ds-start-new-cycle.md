# Start New Development Cycle

**Goal**: Prepare $ARGUMENTS for next development cycle after release.

## Valid Packages

| Package | Path |
|---------|------|
| rossum-mcp | `rossum-mcp/` |
| rossum-agent | `rossum-agent/` |
| rossum-deploy | `rossum-deploy/` |
| rossum-agent-client | `rossum-agent-client/` |

## Changes

| File | Change |
|------|--------|
| `pyproject.toml` | Bump version, add `dev` suffix (e.g., `0.4.0` → `0.5.0dev`) |
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
| Read current | Get version from `pyproject.toml` |
| Bump | Apply version bump with `dev` suffix |
| Changelog | Verify/add empty Unreleased section |
| Verify | Run pre-commit on modified files |

## Constraints

- No automatic commits
- Use `AskUserQuestion` if major vs minor bump unclear
