# Daily Suggestion Feedback

**Goal**: Log suggestion outcome to improve future suggestions.

## Input

`$ARGUMENTS` = `accepted` | `rejected [reason]`

## Action

Append entry to `.claude/daily-suggestion-log.md`:

```markdown
## YYYY-MM-DD
- **Outcome**: accepted/rejected
- **Reason**: <reason if rejected>
- **MR**: <link if available from git>
```

Create file if missing. If rejected, briefly note what to avoid in future.

## Output

Confirm logging:

```
Logged <outcome> to .claude/daily-suggestion-log.md
```

## Constraints

- Append only, never modify existing entries
- Use ISO date format (YYYY-MM-DD)
