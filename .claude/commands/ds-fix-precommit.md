# Fix Pre-commit Issues

**Goal**: All files pass `pre-commit run -a` with no remaining issues.

## Approach

| Step | Action |
|------|--------|
| Run | `pre-commit run -a` |
| Auto-fix | `ruff check --fix` then `ruff format` on failing files |
| Iterate | Re-run pre-commit until clean |

## Output

Report summary as:

```
## Pre-commit Fixed

- <N> files reformatted by ruff format
- <N> issues auto-fixed by ruff check
- All checks passing
```

## Constraints

- No interactive commands
- Maximum 3 iterations before reporting remaining issues
