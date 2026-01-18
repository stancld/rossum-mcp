# Rossum Deployment Skill

**Goal**: Deploy configuration changes safely via sandbox with before/after diff.

## Credential Identification

**Identify tokens BEFORE any deployment operation.** User may provide tokens with unclear naming.

| Identification Method | How to Apply |
|-----------------------|--------------|
| Check organization ID | Use `get_organization(org_id)` with each token to see org name - sandbox orgs typically contain "sandbox", "test", or "dev" |
| Check org URL pattern | Sandbox orgs often use different base URLs or have distinct naming conventions |
| Ask user explicitly | If tokens are ambiguous, ask: "Which token is for production and which for sandbox?" |
| Default env token = production | Token in `ROSSUM_API_TOKEN` env var is production (your main connection) |

**Constraint**: Never assume which token is prod/sandbox. Verify or ask.

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

| Constraint | Rule |
|------------|------|
| Pull before compare | **Never call `deploy_compare_workspaces` without first pulling both directories via `deploy_pull`**. Comparison requires local JSON files - there is nothing to compare without pulling first. |
| Pull BEFORE immediately | After `deploy_copy_workspace`, immediately run `deploy_pull` to `./before`. This captures the baseline. |
| Pull AFTER last | After all sandbox modifications, run `deploy_pull` to `./after`. Then compare. |
| Spawned connections don't persist | Re-spawn `spawn_mcp_connection` each conversation turn. |
| Never deploy without approval | Always show diff and wait for explicit user approval. |
| IDs differ between environments | Sandbox copies have NEW IDs. Use `deploy_copy_workspace` return value or `call_on_connection("sandbox", "list_queues", ...)` to get sandbox IDs. Production IDs will 404 in sandbox. |
| Identify credentials first | Before deployment, verify which token is production vs sandbox (see Credential Identification). |

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

**`deploy_compare_workspaces` compares local JSON files, not remote APIs.** Without pulling, there are no files to compare.

| Step | Command | Output Directory |
|------|---------|------------------|
| 1. Pull baseline | `deploy_pull(org_id=..., workspace_path="./before", token=SANDBOX_TOKEN)` | `./before/` |
| 2. Make modifications | `call_on_connection("sandbox", ...)` | - |
| 3. Pull modified state | `deploy_pull(org_id=..., workspace_path="./after", token=SANDBOX_TOKEN)` | `./after/` |
| 4. Compare | `deploy_compare_workspaces(source_workspace_path="./before", target_workspace_path="./after")` | Diff output |

**Constraint**: Steps 1 and 3 are prerequisites for step 4. Skipping pull = empty comparison = deployment failure.

**Always show the diff output to the user before deployment.** This is the user's only chance to review changes before they go to production.

Do NOT create markdown files for diffs unless user requests.
