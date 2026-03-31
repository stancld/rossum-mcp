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
| `task_step` | `task` (user message — see note below), `preload_info` |
| `memory_step` | `step_number`, `text`, `tool_calls[{name, arguments}]`, `tool_results[{name, content, is_error}]`, `thinking_blocks`, `input_tokens`, `output_tokens` |

**`task` field**: Can be a `str` or a `list` of content blocks (e.g., `[{"type": "text", "text": "..."}, {"type": "image", ...}]`). Extract text by joining all `text`-type items. Always normalize to string before classification.

## Analysis Pipeline

Write a single Python script via `cat << 'PYEOF' > $TMPDIR/analyze_chats.py ... PYEOF` (avoids Write tool guard issues), then run it. All phases in one script, output results to stdout.

### Parsing Requirements

The export is PostgreSQL `COPY` format with JSONB fields. Parsing is non-trivial:

| Requirement | Implementation |
|-------------|----------------|
| Field size | `csv.field_size_limit(sys.maxsize)` — JSONB fields exceed default 131072 limit |
| CSV dialect | `csv.reader(f)` — fields are comma-separated, quoted with `""` escaping |
| Backslash unescaping | Iteratively replace `\\\\` → `\\` until stable before `json.loads()` |
| Quote unescaping | Replace `""` → `"` within quoted fields (handled by `csv.reader`) |

```python
import csv, json, sys

csv.field_size_limit(sys.maxsize)

def unescape_jsonb(raw: str) -> any:
    """Unescape PostgreSQL JSONB and parse."""
    s = raw.strip()
    # Iterative backslash unescaping
    while '\\\\' in s:
        s = s.replace('\\\\', '\\')
    return json.loads(s)

def extract_task_text(task) -> str:
    """Normalize task field to string."""
    if isinstance(task, str):
        return task
    if isinstance(task, list):
        return " ".join(b.get("text", "") for b in task if isinstance(b, dict) and b.get("type") == "text")
    return str(task)
```

### Phase 1: Overview Statistics

| Metric | How to compute |
|--------|----------------|
| Total chats | Count lines |
| Abandoned chats (filtered out) | Has no `task_step` in messages (empty `[]`) — skip these entirely, they are false positives |
| Active chats analyzed | Total minus abandoned |
| Persona distribution | Count `persona` values in metadata |
| MCP mode distribution | Count `mcp_mode` values in metadata |
| Config commits | Chats with non-empty `config_commits` |
| Token usage | Sum per-step `input_tokens`/`output_tokens` from `memory_step` entries (primary source). Fall back to `total_input_tokens`/`total_output_tokens` from metadata. Note: metadata totals are often zero for older chats. |

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
| Single Python script via Bash | Write script with `cat << 'PYEOF' > $TMPDIR/analyze.py` then `python $TMPDIR/analyze.py <csv_path>`. All phases in one script. |
| Use parsing recipe above | Includes `csv.field_size_limit`, iterative backslash unescaping, task text normalization |
| Handle large files | Process line-by-line; don't load entire file into memory for JSON parsing |

### Cross-referencing (Phase 6 only)

When identifying improvement opportunities, validate gaps against these specific locations — do NOT spawn an open-ended codebase exploration agent:

| What to check | Where |
|----------------|-------|
| MCP tool existence | `rossum-mcp/rossum_mcp/tools/` — grep for tool function names |
| Agent tools | `rossum-agent/rossum_agent/tools/` |
| Skills | `rossum-agent/rossum_agent/skills/` — check `__init__.py` for registry |
| Dynamic tool loading | `rossum-agent/rossum_agent/tools/dynamic_tools.py` |
| Prompts | `rossum-agent/rossum_agent/prompts/base_prompt.py` |

Use targeted Grep/Glob calls, not a general-purpose Agent subagent.
