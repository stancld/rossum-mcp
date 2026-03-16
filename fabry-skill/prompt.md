# Fabry

**Goal**: Delegate Rossum platform tasks to the Rossum Agent — an Opus 4.6-powered expert for configuring, debugging, documenting, and managing the Rossum platform.

## Prerequisites

Required environment variables (must be set by the calling agent before invoking this skill):

| Variable | Purpose |
|----------|---------|
| `ROSSUM_AGENT_API_URL` | Agent API endpoint |
| `ROSSUM_API_BASE_URL` | Rossum API URL |
| `ROSSUM_API_TOKEN` | Authentication token |

If any are missing, stop and report the error — do not prompt the user for values.

Install the CLI if not available: `uv pip install rossum-agent-client`

## Usage

Send natural-language prompts to the Rossum Agent via `rossum-agent-client`.

```bash
# Read-only query (default)
rossum-agent-client -x "List all queues with their IDs and names"

# Write operation — requires --mcp-mode read-write
rossum-agent-client --mcp-mode read-write -x "Add a required string field 'tax_id' to the schema on queue 12345"

# Complex prompt from file
rossum-agent-client -r /tmp/rossum-task.md

# Cautious mode — agent confirms before making changes
rossum-agent-client --mcp-mode read-write --persona cautious -x "Delete the 'obsolete_field' from queue 12345 schema"
```

### CLI Flags

| Flag | Purpose | Default |
|------|---------|---------|
| `-x PROMPT` | Execute prompt directly | — |
| `-r FILE` | Read prompt from file | — |
| `--mcp-mode` | `read-only` or `read-write` | `read-only` |
| `--persona` | `default` or `cautious` | `default` |
| `--show-thinking` | Show reasoning + tool calls on stderr | off |

### Output

| Stream | Content |
|--------|---------|
| **stdout** | Final answer text only — pipe-friendly, capturable |
| **stderr** | Progress indicators, tool calls, token usage |
| **Files** | Agent-created files (CSVs, PDFs, JSON) saved to current directory |

## Capabilities

| Category | What It Handles | Example Prompt |
|----------|----------------|----------------|
| Queues & Workspaces | Create, list, inspect, configure, delete queues and workspaces | "List all queues", "Create a queue from the Invoice template" |
| Schemas | Read/modify fields, prune unused fields, all types (sections, multivalue, enums) | "Add a required 'vendor_vat' string field to the header section on queue 12345" |
| Formula Fields | Deterministic computed fields via TxScript — math, strings, dates, aggregations | "Add a formula that calculates total_with_tax as amount * (1 + tax_rate/100)" |
| AI Reasoning Fields | AI-powered fields for ambiguous formats, contextual interpretation, classification | "Add a reasoning field that determines payment terms from the invoice text" |
| Lookup Fields | Fields fetching values from Master Data Hub — vendor matching, catalog lookups | "Add a lookup field that matches vendor_name against the vendor master data" |
| Hooks & Extensions | Create, configure, test serverless functions; Rossum Store templates or custom Python 3.12 | "Create a hook from the 'Copy value to another field' template on queue 12345" |
| Validation Rules | TxScript trigger conditions with error/warning/info/automate actions | "Add a rule that shows an error when amount_total > 1000000" |
| Annotations & Documents | Query, inspect, update annotations; upload documents; copy between queues | "Show extracted data from annotation 99999", "Upload invoice.pdf to queue 12345" |
| UI Settings | Queue UI layout — annotation list columns, sidebar ordering, field visibility | "Add 'vendor_name' and 'amount_total' columns to the annotation list table" |
| Document Testing | Generate mock PDFs, upload, verify extraction, trigger hooks — end-to-end | "Generate a test PDF matching queue 12345's schema, upload it, verify extraction" |
| Users & Permissions | Create/update users, manage roles and group assignments | "Create a user with email john@example.com as annotator on queue 12345" |
| Email Templates | Automated notification templates with configurable recipients | "Create an auto-send email template for confirmed invoices on queue 12345" |
| Change History | Audit trail, inspect diffs, revert commits, restore entity versions | "Show recent changes", "Revert the last commit" |
| Knowledge Base | Search Rossum platform docs and API reference | "How do formula fields work in Rossum?" |

## Prompt Tips

Include entity IDs when known. State goals, not steps. Request structured output ("as JSON", "as markdown table") when parsing the result.

## Choosing MCP Mode

| Mode | Use When |
|------|---------|
| `read-only` | Querying, listing, inspecting, explaining — no side effects |
| `read-write` | Creating, modifying, or deleting any Rossum resource |

## Choosing Persona

| Persona | Use When |
|---------|---------|
| `default` | Standard tasks — agent acts autonomously |
| `cautious` | Destructive or production changes — agent confirms before acting |

## Constraints

| Constraint | Value |
|-----------|-------|
| Chat creates | 30/min |
| Messages | 10/min |
| Message length | 50,000 chars max |
| Images per message | 5 (max 5 MB each; jpeg/png/gif/webp) |
| PDFs per message | 5 (max 20 MB each) |
| Timeout | 300s default |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Missing required configuration" | Set the three env vars above |
| 401 error | Token expired — get a fresh `ROSSUM_API_TOKEN` |
| 429 error | Rate limit hit — wait and retry |
| Timeout | Break the task into smaller, more focused prompts |
| "read-only mode" rejection | Add `--mcp-mode read-write` |
