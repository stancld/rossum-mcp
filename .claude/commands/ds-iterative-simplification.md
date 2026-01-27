# Iterative Code Simplification

**Goal**: Simplify code through iterative cycles of refinement and critical review until no significant issues remain.

## Scope

| Context | What to Simplify |
|---------|------------------|
| No argument | Recently modified or uncommitted code |
| File/path provided | The specified file(s) or directory |

## Process

| Phase | Action |
|-------|--------|
| 1. Simplify | Apply `/code-simplifier` to target code |
| 2. Review | Run `/ds-review` or `/ds-roast` (based on user preference) on changes |
| 3. Iterate | If review finds issues, return to phase 1 with feedback |
| 4. Complete | When review passes with no critical issues, output final summary |

## Before Starting

Ask the user (use `AskUserQuestion`):

| Question | Options |
|----------|---------|
| Review style | `/ds-review` (constructive) or `/ds-roast` (brutal) |
| Max iterations | 2-5 cycles (default: 3) |

## Iteration Rules

| Rule | Description |
|------|-------------|
| Track changes | Keep list of what was simplified each round |
| Accumulate feedback | Each review informs next simplification pass |
| Exit early | Stop if no changes made or review passes |
| Prevent loops | Don't undo previous simplifications unless review demands it |

## Convergence Criteria

Stop iterating when ANY of these are true:

| Condition | Meaning |
|-----------|---------|
| Clean review | Review finds no critical issues |
| No changes | Simplifier made no modifications |
| Max iterations | Reached user-specified limit |
| Diminishing returns | Changes are cosmetic only |

## Output

After final iteration:

```
## Simplification Summary

### Changes Made (by iteration)
- **Round 1**: <changes>
- **Round 2**: <changes>
...

### Final Review
<review summary or verdict>

### Ready for Commit
<yes/no + suggested commit message if yes>
```

## Constraints

- No automatic commits
- Ask before running tests
- Each iteration should make meaningful progress
- If stuck in a loop (same issue reappearing), stop and report to user
