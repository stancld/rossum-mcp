# Rossum Deployment Skill

**Goal**: Deploy configuration changes safely via sandbox with before/after diff.

## Credential Rules

**Every tool call touches exactly one environment. Know which one before calling.**

| Call Pattern | Environment Affected |
|--------------|---------------------|
| `get_schema(...)`, `update_schema(...)`, any direct MCP tool | **PRODUCTION** |
| `call_on_connection("sandbox", "update_schema", ...)` | Sandbox |
| `deploy_copy_workspace(..., target_token=SANDBOX_TOKEN)` | Copies FROM production TO sandbox |
| `deploy_pull(..., token=SANDBOX_TOKEN)` | Pulls FROM sandbox |
| `deploy_pull(..., token=PROD_TOKEN)` or no token | Pulls FROM production |
| `deploy_to_org(..., target_token=SANDBOX_TOKEN)` | Deploys TO sandbox |
| `deploy_to_org(..., target_token=PROD_TOKEN)` | **Deploys TO PRODUCTION** |

**Sandbox modifications**: Always use `call_on_connection("sandbox", tool_name, args)`. Direct MCP calls modify production.

## Workflow

Execute steps 1-5 autonomously. **Only pause at step 5 for user approval.**

| Step | Tool | Token/Connection |
|------|------|------------------|
| 1. Copy to sandbox | `deploy_copy_workspace` | `target_token=SANDBOX_TOKEN` |
| 2. Pull BEFORE | `deploy_pull` → `./before` | `token=SANDBOX_TOKEN` |
| 3. Modify sandbox | `call_on_connection("sandbox", ...)` | Via spawned connection |
| 4. Pull AFTER | `deploy_pull` → `./after` | `token=SANDBOX_TOKEN` |
| 5. Compare + show diff | `deploy_compare_workspaces` → display to user | **Wait for approval** |
| 6. Deploy to prod | `deploy_to_org` | `target_token=PROD_TOKEN` |

Step 3: Never use direct MCP calls (`update_schema`, `update_queue`, etc.) - those modify production.

## Key Constraints

- **Pull BEFORE immediately after copy** - captures baseline for diff
- **Spawned connections don't persist** - re-spawn `spawn_mcp_connection` each conversation turn
- **Never deploy without approval** - always show diff and wait
- **IDs differ between environments** - sandbox copies have NEW IDs. Use `deploy_copy_workspace` return value or `call_on_connection("sandbox", "list_queues", ...)` to get sandbox IDs. Production IDs will 404 in sandbox.

## Sandbox Connection Setup

```python
spawn_mcp_connection(connection_id="sandbox", api_token="<SANDBOX_TOKEN>", api_base_url="https://api.elis.rossum.ai/v1")
```

## Common Sandbox Operations

| Operation | Correct (Sandbox) | Wrong (Production) |
|-----------|-------------------|-------------------|
| Update schema | `call_on_connection("sandbox", "update_schema", '{"schema_id": 123, ...}')` | `update_schema(schema_id=123, ...)` |
| Create schema | `call_on_connection("sandbox", "create_schema", '{"name": "...", "content": [...]}')` | `create_schema(name="...", ...)` |
| Update queue | `call_on_connection("sandbox", "update_queue", '{"queue_id": 456, ...}')` | `update_queue(queue_id=456, ...)` |
| Update hook | `call_on_connection("sandbox", "update_hook", '{"hook_id": 789, ...}')` | `update_hook(hook_id=789, ...)` |

All read operations (get_schema, get_queue, list_hooks) on sandbox also require `call_on_connection`.

## Tools

| Tool | Purpose |
|------|---------|
| `deploy_copy_workspace` | Copy workspace to target org |
| `deploy_pull` | Pull workspace config (schemas, queues, hooks) to local directory as JSON files |
| `deploy_compare_workspaces` | Diff two local workspace directories, returns structured changes |
| `deploy_to_org` | Deploy to target org (`dry_run=True` first) |

## Before/After Diff is Mandatory

`deploy_pull` saves workspace configuration to local files. Use it twice:
1. **BEFORE** modifications → `./before` directory
2. **AFTER** modifications → `./after` directory

Then run `deploy_compare_workspaces(before_path="./before", after_path="./after")` to get the diff.

**Always show the diff output to the user before deployment.** This is the user's only chance to review changes before they go to production.

Do NOT create markdown files for diffs unless user requests.
