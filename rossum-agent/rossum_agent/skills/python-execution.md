# Python Execution Skill

**Goal**: Use `execute_python` efficiently for data shaping, MCP result transformation, and Rossum copilot helpers.

## Tool

```python
execute_python(code="result = 1 + 2", operation_name="quick check")
```

Use short snippets only. Stdlib imports allowed: collections, csv, datetime, fpdf, functools, io, itertools, json, math, operator, pathlib, re, statistics, string, textwrap, time. Return the final value via `result` or the last expression.

## Built-In Helpers

These helpers are available inside `execute_python` snippets:

| Helper | Purpose |
|--------|---------|
| `mcp(tool_name, **kwargs)` | Call MCP tools from Python without large tool arguments |
| `api_get(entity, entity_id)` | Compatibility shortcut for `mcp("get", entity=..., entity_id=...)` |
| `schema_content(value)` | Normalize schema payloads to the bare content array |
| `write_file(filename, content)` | Save strings, dicts, or lists to the output directory |
| `json` | Encode or inspect JSON structures |
| `copilot` | Namespace exposing Rossum copilot helpers |

Copilot helpers (e.g. `suggest_formula_field`, `suggest_rule`) are also available as top-level functions — load the relevant domain skill for usage details.

## Constraints

| Rule | Detail |
|------|--------|
| Imports | Stdlib imports allowed (collections, csv, datetime, fpdf, functools, io, itertools, json, math, operator, pathlib, re, statistics, string, textwrap, time); all other imports are blocked |
| No dunder access | Names or attributes starting with `__` are blocked |
| Short snippets only | Max length is 12000 characters |
| Large outputs go to files | If the useful result is a large dict/list/string, call `write_file(...)` and return the write result instead of inlining the payload |
| Save normalized schemas | When writing schema JSON, write the content array itself |
