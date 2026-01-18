# Fix Pre-commit Issues

**Goal**: All files pass `pre-commit run -a` with no remaining issues.

## Approach

| Step | Action |
|------|--------|
| Run | `pre-commit run -a` |
| Auto-fix | `ruff check --fix` then `ruff format` on failing files |
| Iterate | Re-run pre-commit until clean |

## Constraints

- No interactive commands
- Report summary of fixes applied
