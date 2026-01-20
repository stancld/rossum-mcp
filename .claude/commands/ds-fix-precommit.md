# Fix Pre-commit Issues

**Goal**: All files pass `pre-commit run --all-files` with no remaining issues.

## Approach

| Step | Action |
|------|--------|
| Run | `pre-commit run --all-files` |
| Auto-fix | `ruff check --fix` then `ruff format` on failing files |
| Iterate | Re-run pre-commit until clean |

## Constraints

- No interactive commands
- Report summary of fixes applied
