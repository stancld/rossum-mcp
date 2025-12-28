# Hook Debugging Skill

This skill provides a workflow for debugging Rossum hook code using the Opus sub-agent.

## When to Use This Skill

Activate this skill when:
- User reports a hook is not working correctly
- User asks to debug, fix, or troubleshoot a function hook
- Hook execution produces errors or unexpected behavior
- User wants to understand why a hook is failing

## Debugging Workflow

### Step 1: Knowledge Base Research (MANDATORY)

**Before any debugging, you MUST use `search_knowledge_base` first:**
- Search with queries like "[extension name] configuration" or "[error message]"
- Use ALL configuration-related information in your reasoning
- Search for the specific extension name, error message, or behavior you're investigating
- The Knowledge Base contains official documentation on extension configuration, common issues, and best practices
- This step is REQUIRED before attempting to debug code or configuration

### Step 2: Investigation Priority Order

1. **Search Rossum Knowledge Base** - for official documentation and known issues
2. **Configuration issues** (hooks, schemas, rules) - most common
3. **Field ID mismatches** - check schema_id vs annotation content
4. **Trigger event misconfiguration** - verify correct events
5. **Automation thresholds** - check queue and field-level settings
6. **External service failures** - webhooks, integrations

### Step 3: Debugging Checklist

Before diving into code:
- Check knowledge base if more information about the hook is available
- Verify hook is active and attached to correct queue
- Check trigger events match the workflow stage
- Validate field IDs exist in schema
- Review hook code for syntax/logic errors
- Check automation_level and score_threshold settings
- **Parent-child relations can be chained** - when debugging, check children of children (nested relationships) as issues may propagate through the chain
- **Schema compatibility for extensions** - search the knowledge base for extension schema requirements, then verify the schema matches (correct **data types**, **singlevalue vs multivalue datapoint**, required fields exist)

### Step 4: Hook Code Debugging with Opus

**MANDATORY**: When debugging Python hook code (function hooks), you MUST use the `debug_hook` tool. Do NOT attempt to debug hook code yourself - always delegate to the Opus sub-agent.

**CRITICAL: Investigate ALL Issues**
- DO NOT stop at the first issue found - there are often multiple problems
- The Opus sub-agent will exhaustively analyze the code for ALL potential issues
- Continue investigating even after fixing one error - look for edge cases, missing error handling, and other problems
- The goal is robust, production-ready code that handles all scenarios

The `debug_hook` tool:
1. Spawns an Opus-based debugging sub-agent with deep reasoning capabilities
2. Opus fetches the hook code and annotation data automatically
3. Opus exhaustively analyzes the code for ALL issues (not just the first one)
4. Opus iteratively tests fixes until the code works correctly for all cases
5. Returns detailed analysis with verified, working code that addresses ALL issues found

**Simple usage**: Just pass the IDs - the sub-agent fetches everything itself:
```
debug_hook(hook_id="12345", annotation_id="67890")
```

You do NOT need to call `get_hook` or `get_annotation` first - the Opus sub-agent will do that.

### Step 5: Trust and Apply Opus Results

**CRITICAL:**
- When Opus returns analysis and fixed code, you MUST trust its findings and apply them
- DO NOT second-guess or re-analyze what Opus has already thoroughly investigated
- DO NOT simplify or modify the fixed code Opus provides - use it exactly as returned
- Opus has deep reasoning capabilities and has already verified the solution works
- Your job after receiving Opus results is to present them clearly to the user and help apply the fix, NOT to re-do the analysis

## Understanding Relations vs Document Relations

When debugging issues related to document relationships:

- **Relations** (`get_relation`, `list_relations`): Links between annotations created by Rossum workflow actions
  - `edit`: Created after rotating or splitting documents in UI
  - `attachment`: One or more documents attached to another document
  - `duplicate`: Same document imported multiple times
  - Use cases: Track document edits, find duplicates, manage attachments

- **Document Relations** (`get_document_relation`, `list_document_relations`): Additional links between annotations and documents
  - `export`: Documents generated from exporting an annotation (e.g., PDF exports)
  - `einvoice`: Electronic invoice documents associated with an annotation
  - Use cases: Track exported files, manage e-invoice documents, find generated outputs

## Example Agent Conversation

**User**: My validation hook isn't working - it's supposed to reject invoices without a PO number but it's letting them through

**Agent**:
1. Searches knowledge base for "validation hook" and "annotation validation"
2. Gets the hook details with `get_hook(hook_id=...)`
3. Verifies hook is enabled and attached to the correct queue
4. Checks trigger events are correct (e.g., `annotation_content.user_update`)
5. Uses `debug_hook(hook_id="...", annotation_id="...")` to have Opus analyze the code
6. Presents Opus findings and the fixed code to the user
7. Offers to update the hook with the corrected code
