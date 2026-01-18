# Review Code Changes

**Goal**: Review uncommitted changes for quality issues, ensure tests pass, and produce MR-ready summary.

## Scope

| Context | What to Review |
|---------|----------------|
| No argument | Uncommitted changes; if none, review last commit |
| Commit provided | The specified commit(s) |

## Review Checklist

| Category | Check For |
|----------|-----------|
| Unused code | Dead imports, variables, unreachable branches |
| Duplication | Repeated logic that should use shared components |
| AI slop | Excessive try/catch, defensive checks in trusted paths, `Any` casts, style drift |
| Documentation | Changes reflected in README.md and CLAUDE.md |

## Approach

| Step | Action |
|------|--------|
| Analyze | Review diff for issues in checklist |
| Critical issues | Use `AskUserQuestion` for each - fix or skip |
| Tests | If test files changed, ask whether to run `pytest` |
| Summary | Generate short MR description of what was done |

## Constraints

- Ask before running tests (use `AskUserQuestion`)
- No automatic commits
- Report only critical issues, not style nitpicks
