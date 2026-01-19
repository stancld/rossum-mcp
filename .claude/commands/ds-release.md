# Release Package

**Goal**: Verify $ARGUMENTS is release-ready with correct version, changelog, and passing checks.

## Valid Packages

| Package | Path | Module |
|---------|------|--------|
| rossum-mcp | `rossum-mcp/` | `rossum_mcp` |
| rossum-agent | `rossum-agent/` | `rossum_agent` |
| rossum-deploy | `rossum-deploy/` | `rossum_deploy` |
| rossum-agent-client | `rossum-agent-client/` | `rossum_agent_client` |

## Checklist

| Item | Verification |
|------|--------------|
| Version (pyproject.toml) | `pyproject.toml` version matches release (not `dev` suffix) |
| Version (__init__.py) | `<module>/__init__.py` `__version__` matches pyproject.toml |
| Changelog | `[Unreleased]` section converted to `[X.Y.Z] - YYYY-MM-DD` |
| Changelog content | Entries exist for this release |
| New Unreleased | Empty `[Unreleased]` section added above |
| Pre-commit | `pre-commit run -a` passes |
| Tests | `pytest` passes for the package |

## Approach

| Step | Action |
|------|--------|
| Validate | Confirm package name is valid |
| Check versions | Read `pyproject.toml` and `<module>/__init__.py`, verify no `dev` suffix and versions match |
| Check changelog | Read `CHANGELOG.md`, verify release section exists with today's date |
| Run checks | Execute pre-commit and pytest |
| Report | List any issues found |
| Output | Provide commit message and tag command |

## Output Format

After all checks pass, provide:

```
## Ready to Release

Suggested commit message:
chore(<package>): release vX.Y.Z

Git tag command:
git tag <package>-vX.Y.Z
```

## Constraints

- No automatic commits
- Report all issues before suggesting fixes
- Use `AskUserQuestion` if version/date ambiguous
