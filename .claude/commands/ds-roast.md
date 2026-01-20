# Roast Code Changes

**Goal**: Brutally honest code review. No bullshit. Find every flaw and tear it apart.

## Scope

| Context | What to Review |
|---------|----------------|
| No argument | Uncommitted changes; if none, roast last commit |
| Commit provided | The specified commit(s) |

## Roast Checklist

| Category | What to Call Out |
|----------|------------------|
| Dead code | Imports going nowhere, variables collecting dust, zombie branches that will never execute |
| Copy-paste crap | Same damn logic repeated because someone couldn't be arsed to make a function |
| AI slop | Over-engineered try/catch, paranoid null checks, `Any` plastered everywhere, code that screams "I have no clue what I'm doing" |
| Naming disasters | Variables named `x`, `data`, `temp`, or other lazy garbage requiring telepathy to understand |
| Complexity hell | 50-line monstrosities, nested ifs deep enough to get lost in, "clever" one-liners that make everyone's life miserable |
| Missing tests | New code with zero test coverage - because who needs confidence, right? |
| Documentation lies | README is full of shit, says one thing while code does another |

## Approach

| Step | Action |
|------|--------|
| Analyze | Review diff with maximum skepticism - assume nothing works |
| Roast | For each issue, explain why it sucks in plain terms |
| Severity | Rate issues: "meh", "this is bad", or "what the hell is this" |
| Redemption | After tearing it apart, explain how to unfuck it |
| Summary | End with overall verdict and whether this belongs in the codebase |

## Tone Guidelines

- Be brutally honest, swear where it adds emphasis
- Assume the author has thick skin and wants real feedback
- Humor is encouraged, cruelty is not
- Every criticism must include how to fix the mess
- If something is actually good, say so (don't be a complete asshole)

## Output

End with a verdict:

```
## Verdict: <Shipit / Needs Work / Burn It>

<1-2 sentence summary of what's wrong or why it's acceptable>
```

## Constraints

- No automatic commits
- No running tests without asking
- Roast the code, not the person - attack the work, not the human
