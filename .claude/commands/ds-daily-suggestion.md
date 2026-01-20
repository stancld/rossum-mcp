# Daily Suggestion

**Goal**: Generate 1-5 small, related improvements (3-5 min total human review) and open MR.

## Improvement Categories

| Priority | Category | Examples |
|----------|----------|----------|
| 1 | Self-improvement | Analyze recent commits → improve `.claude/commands/` |
| 2 | Documentation | Stale docs, missing examples, outdated instructions |
| 3 | Code quality | Dead code, unused imports, type hint gaps |
| 4 | Developer experience | Workflow improvements, better error messages |

## Scope Constraints

| Constraint | Rationale |
|------------|-----------|
| 1-5 related changes | Justify reviewer's context-switch; single trivial changes waste time |
| No feature additions | Features need planning |
| No breaking changes | Safe to merge quickly |
| Self-contained | No follow-up work required |

## Approach

| Step | Action |
|------|--------|
| Sync | `git checkout master && git pull` |
| Branch | `git checkout -b cc-daily-suggestion-YYYY-MM-DD` |
| Analyze | Check recent commits (last 2 weeks) for patterns worth capturing in commands |
| Find | Identify 1-5 related improvements from categories above |
| Implement | Make the change |
| Verify | Run `pre-commit run --all-files` on changed files |
| Commit | Commit with descriptive message |
| Push | `git push -u origin HEAD` |
| MR | Open MR via `gh pr create` |

## Commit Message Format

```
<area>: <short description>

<optional 1-2 sentence context>
```

Areas: `docs`, `claude-commands`, `chore`, `style`

## MR Template

```markdown
## Summary
- <1 bullet describing the change>

## Review Notes
- Coffee-time review (~3-5 min)
- No behavioral changes / Safe refactor / Docs only

🤖 Generated with [Claude Code](https://claude.ai/code) daily suggestion
```

## Output

Return MR URL when complete.

## Constraints

- 1-5 improvements per run
- Skip if no meaningful improvements found (report "Nothing today")
- Prefer self-improvement of `.claude/commands/` when patterns emerge from recent commits

## Feedback Integration

When user runs `/ds-daily-suggestion-feedback`, outcomes are logged to `.agents/daily-suggestion-log.md`. Before suggesting, review this log for rejection patterns to avoid.
