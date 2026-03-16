# Daily Suggestion Feedback

**Goal**: Log suggestion outcome to improve future suggestions.

## Input

`$ARGUMENTS` = `accepted` | `rejected [reason]`

## Action

Append entry to `.claude/daily-suggestion-log.md`:

```markdown
## YYYY-MM-DD (attempt N)
- **Outcome**: accepted/rejected
- **Reason**: <reason if rejected>
- **Note**: <optional context for future improvement>
- **MR**: <link if available from git>
```

| Field | Required | Notes |
|-------|----------|-------|
| Date heading | Yes | ISO format; add `(attempt N)` suffix when multiple runs on same day |
| Outcome | Yes | `accepted` or `rejected` |
| Reason | If rejected | What to avoid in future |
| Note | Optional | Positive feedback, patterns to repeat, scope guidance |
| MR | If available | Link from `gh pr list` or git log |

Create file if missing. If rejected, briefly note what to avoid in future.

## Output

Confirm logging:

```
Logged <outcome> to .claude/daily-suggestion-log.md
```

## Constraints

- Append only, never modify existing entries
- Use ISO date format (YYYY-MM-DD)
