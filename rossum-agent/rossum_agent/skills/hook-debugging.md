# Hook Debugging Skill

**Goal**: Identify and fix hook issues.

## Tools

| Tool | Purpose |
|------|---------|
| `search_knowledge_base` | **USE FIRST** - Rossum docs contain extension configs, known issues, required schema fields |
| `debug_hook(hook_id, annotation_id)` | Spawns Opus sub-agent for code analysis - returns verified fix |

## Constraints

- **ALWAYS search knowledge base first** - it contains solutions, required configurations, and known issues that save debugging time
- **Use `debug_hook` for Python code** - do not analyze hook code yourself
- **Trust `debug_hook` results** - do not re-analyze or modify the returned fix

## `debug_hook` Usage

```python
debug_hook(hook_id="12345", annotation_id="67890")
```

The sub-agent fetches hook code and annotation data automatically. No need to call `get_hook` or `get_annotation` first.

## Relations Reference

| Type | Tools | Use Case |
|------|-------|----------|
| Relations | `get_relation`, `list_relations` | Track edits, duplicates, attachments |
| Document Relations | `get_document_relation`, `list_document_relations` | Track exports, e-invoice docs |
