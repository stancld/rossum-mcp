# Analyze Chat Data

**Goal**: Analyze rossum-agent chat data from a CSV export to identify improvement opportunities for rossum-agent and rossum-mcp.

## Input

`$ARGUMENTS` = path to a CSV file containing PostgreSQL-exported chat rows.

If no argument provided, prompt the user for the file path.

## Data Format

Each line is a PostgreSQL tuple: `(db_id, chat_id, messages_jsonb, output_dir, metadata_jsonb, created_at, expires_at)`

| Field | Format | Key contents |
|-------|--------|--------------|
| `messages` | JSONB array | Steps: `task_step` (user turns), `memory_step` (agent reasoning + tool calls) |
| `metadata_` | JSONB object | `persona`, `summary`, `mcp_mode`, `total_steps`, `total_tool_calls`, `total_input_tokens`, `total_output_tokens`, `config_commits` |

### Step types inside messages

| Type | Contains |
|------|----------|
| `task_step` | `task` (user message text), `preload_info` |
| `memory_step` | `step_number`, `text`, `tool_calls[{name, arguments}]`, `tool_results[{name, content, is_error}]`, `thinking_blocks`, `input_tokens`, `output_tokens` |

## Analysis Pipeline

Run the analysis using Python scripts via Bash. Parse the PostgreSQL tuple format (not standard CSV). Use `""` → `"` unescaping for embedded JSON.

### Phase 1: Overview Statistics

| Metric | How to compute |
|--------|----------------|
| Total chats | Count lines |
| Active vs abandoned | Has `task_step` in messages vs empty `[]` |
| Abandonment rate | `empty / total * 100` |
| Persona distribution | Count `persona` values in metadata |
| MCP mode distribution | Count `mcp_mode` values in metadata |
| Config commits | Chats with non-empty `config_commits` |
| Token usage | Sum `total_input_tokens`, `total_output_tokens` from metadata; fall back to summing per-step `input_tokens`/`output_tokens` from `memory_step` if metadata totals are zero |

### Phase 2: Tool Usage Analysis

| Metric | How to compute |
|--------|----------------|
| Tool call frequency | Count all `"name": "<tool>"` in `tool_calls` across all `memory_step` entries |
| Top tools | Sort by frequency descending |
| Error rate | Count `"is_error": true` in `tool_results`; extract surrounding context for each |
| Tool-not-found errors | Search for `"Unknown tool"` in tool result content |
| Tools per chat | Average and max tool calls per active chat |

### Phase 3: User Intent Categorization

Classify each chat by the **first** `task_step` content:

| Category | Signal words in task |
|----------|----------------------|
| Investigate/debug | why, error, issue, debug, stuck, not working, wrong, investigate |
| Configure/modify | add, replace, modify, configure, set up, implement, change, update |
| Explain/how-to | how, explain, what is, what does, what rules, what happens |
| Customer email draft | email, draft, write.*customer, write.*user |
| Data lookup | search, find, look, check, which, query |
| Create new | create, generate, new document |

Report distribution and list chat IDs per category.

### Phase 4: Failure Pattern Detection

| Pattern | Detection method |
|---------|------------------|
| "I don't have access" | Summary contains "don't have access" or "cannot" |
| Tool errors | `is_error: true` in tool_results |
| URL not resolved | User task contains `http` but summary indicates access failure |
| Mode mismatch | Write-intent words in task + `mcp_mode: read-only` |
| User frustration / repeated asks | `task_step` count >= 3 per chat (multi-turn = possible struggle) |
| "I can't see" UX issues | Task text contains "can't see" |
| Hallucinated tools | Tool results containing "Unknown tool" |

### Phase 5: Workflow Patterns

| Pattern | Detection method |
|---------|------------------|
| Multi-turn investigations | Chats with >= 5 `task_step` entries — list with summaries |
| Email drafting | Chats using `write_file` with `email` in filename |
| Schema modifications | Chats using `patch_schema_with_subagent` or `patch_schema` |
| Knowledge base lookups | Chats using `search_knowledge_base` or `search_elis_docs` |
| Skill loading | Extract skill names from `load_skill` arguments |
| Read-write outcomes | Chats in `read-write` mode — did they produce `config_commits`? |

### Phase 6: Improvement Opportunities

Synthesize findings into a ranked list of improvement opportunities:

| Column | Description |
|--------|-------------|
| Priority | 1 (highest) to N |
| Opportunity | Short title |
| Package | `rossum-agent`, `rossum-mcp`, or `both` |
| Evidence | Specific chats/counts from the analysis |
| Effort | Low / Medium / High |
| Impact | Low / Medium / High |

**Prioritization criteria** (in order):
1. Complete task failures (user got zero value)
2. High-frequency inefficiencies (affects many chats)
3. Recurring multi-turn struggles (same type of question takes too long)
4. Missing capabilities (users ask for things we can't do)
5. UX/rendering issues

## Output Format

Present results as structured markdown with tables. End with the ranked improvement opportunities table and 2-3 sentence summary of the highest-impact findings.

## Constraints

| Constraint | Rationale |
|------------|-----------|
| No modifications to any source files | Analysis only |
| Use Python via Bash for parsing | PostgreSQL tuple format needs custom parsing |
| Handle large files | Process line-by-line; don't load entire file into memory for JSON parsing |
| Escape-aware parsing | Handle `""` escaping in PostgreSQL JSONB text |
| Cross-reference with codebase | When identifying improvement opportunities, check current tools/skills/prompts to confirm gaps are real |
