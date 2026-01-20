# Clean AI Slop & Simplify Code

**Goal**: Remove AI-generated patterns and simplify code while preserving exact functionality.

## Scope

Only refine code modified in the current branch (diff against `master`), unless instructed otherwise.

## What to Remove

| Category | Pattern | Example |
|----------|---------|---------|
| AI Slop | Redundant comments | Comments explaining what, not why |
| AI Slop | Excessive defensiveness | Try/catch or null checks in trusted internal paths |
| AI Slop | Type bypasses | `# type: ignore`, `Any`, `Optional[str]` instead of `str \| None` |
| AI Slop | Style drift | `List[str]` instead of `list[str]`, trailing commas |
| Simplify | Dead code | Unused variables, imports, unreachable branches |
| Simplify | Over-abstraction | Helpers/utilities used only once |
| Simplify | Premature generalization | Config options or parameters never used |
| Simplify | Unnecessary nesting | Deep conditionals that can be flattened |

## Project Standards (from CLAUDE.md)

| Rule | Correct | Avoid |
|------|---------|-------|
| Type hints | `str \| None` | `Optional[str]` |
| Collections | `list[str]`, `dict[str, int]` | `List[str]`, `Dict[str, int]` |
| No Any | Specific types always | `Any` to silence errors |
| Comments | Explain why | Explain what |
| Noqa | `# noqa: E501 - reason` | `# noqa: E501` |
| Trailing commas | `[1, 2, 3]` | `[1, 2, 3,]` |

## Balance

| Do | Don't |
|----|-------|
| Prefer clarity over brevity | Create dense one-liners |
| Keep helpful abstractions | Remove structure that aids understanding |
| Use explicit patterns | Write clever code that's hard to debug |
| Follow existing file style | Introduce new conventions |

## Approach

| Step | Action |
|------|--------|
| Diff | `git diff master...HEAD` to identify changed files |
| Scan | Find AI patterns and simplification opportunities |
| Clean | Apply changes preserving all functionality |
| Verify | Run `pytest` to confirm behavior unchanged |

## Output

Report 1-3 sentence summary of changes made.

## Constraints

- No automatic commits
- Preserve all existing functionality
- Run tests before and after to verify no regressions
