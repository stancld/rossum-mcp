---
description: Delegate Rossum platform tasks to the Rossum Agent via the fabry CLI. Use for querying, configuring, and managing the Rossum platform.
---

# Fabry

**Goal**: Delegate Rossum platform tasks to the Rossum Agent via the `fabry` CLI.

**CLI**: `fabry` — a Node.js binary bundled with this package. Do NOT use `rossum-agent-client`, `pip install`, or any Python tool. The only command is `fabry`.

## Quick Reference

```bash
# Read-only query (default)
fabry -x "List all queues with their IDs and names"

# Write operation
fabry --mcp-mode read-write -x "Add a required string field 'tax_id' to queue 12345"

# Complex prompt from file
fabry -r /tmp/rossum-task.md

# Cautious mode — agent confirms before changes
fabry --mcp-mode read-write --persona cautious -x "Delete the 'obsolete_field' from queue 12345 schema"
```

| Flag | Purpose | Default |
|------|---------|---------|
| `-x PROMPT` | Execute prompt directly | — |
| `-r FILE` | Read prompt from file | — |
| `--mcp-mode` | `read-only` or `read-write` | `read-only` |
| `--persona` | `default` or `cautious` | `default` |
| `--show-thinking` | Show reasoning + tool calls on stderr | off |

## Output

| Stream | Content |
|--------|---------|
| **stdout** | Final answer text only — pipe-friendly |
| **stderr** | Progress, tool calls, token usage |

## Full Reference

For capabilities, constraints, and troubleshooting, read `fabry-skill/prompt.md`.
