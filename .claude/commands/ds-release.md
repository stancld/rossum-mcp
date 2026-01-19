# Release Package

**Goal**: Verify $ARGUMENTS is release-ready with correct version, changelog, and passing checks.

## Valid Packages

| Package | Path |
|---------|------|
| rossum-mcp | `rossum-mcp/` |
| rossum-agent | `rossum-agent/` |
| rossum-deploy | `rossum-deploy/` |
| rossum-agent-client | `rossum-agent-client/` |

## Checklist

| Item | Verification |
|------|--------------|
| Version | `pyproject.toml` version matches release (not `dev` suffix) |
| Changelog | `[Unreleased]` section converted to `[X.Y.Z] - YYYY-MM-DD` |
| Changelog content | Entries exist for this release |
| New Unreleased | Empty `[Unreleased] - YYYY-MM-DD` section added above |
| Pre-commit | `pre-commit run -a` passes |
| Tests | `pytest` passes for the package |

## Approach

| Step | Action |
|------|--------|
| Validate | Confirm package name is valid |
| Check version | Read `pyproject.toml`, verify no `dev` suffix |
| Check changelog | Read `CHANGELOG.md`, verify release section exists with today's date |
| Run checks | Execute pre-commit and pytest |
| Report | List any issues found |

## Constraints

- No automatic commits
- Report all issues before suggesting fixes
- Use `AskUserQuestion` if version/date ambiguous
