# Rossum Deployment Skill

This skill provides a safe workflow for deploying Rossum configuration changes using the deployment tools.

---

## ⚠️ MANDATORY: Create Deployment Plan FIRST

**Before performing ANY operations, you MUST create and present a deployment plan to the user.**

### Deployment Plan Template

```
## Deployment Plan

### Environment Context
- **Source environment**: [production/sandbox] (org ID: X) - PURPOSE: [read-only reference / template]
- **Target environment**: [production/sandbox] (org ID: Y) - PURPOSE: [where changes will be made]

### Reference Resources (Read-Only)
- Workspace: [name] (ID: X) from [source env]
- Queue: [name] (ID: X) from [source env]
- Schema: [name] (ID: X) from [source env]
- Hooks: [list] from [source env]

### Actions to Perform (in Target Environment)
1. [Action 1 - e.g., Copy workspace to sandbox org]
2. [Action 2 - e.g., Modify schema fields X, Y, Z]
3. [Action 3 - e.g., Add splitting extension]

### Credentials Required
- Source (read): ROSSUM_API_BASE_URL, ROSSUM_API_TOKEN
- Target (write): target_token parameter (+ target_api_base if different)
```

---

## ⚠️ MANDATORY WORKFLOW - FOLLOW THESE STEPS IN ORDER

**CRITICAL: Never modify production directly. Always use a sandbox organization for changes.**

### 🤖 Autonomous Execution Policy

**The agent MUST proceed autonomously through Steps 1-4 without asking for user input.**

Only pause and wait for user approval at Step 4 after displaying the diff. Do NOT ask for confirmation before copying, making changes, or pulling workspaces.

### Required Step Order:
1. **FIRST**: Copy workspace → sandbox using `deploy_copy_workspace` *(autonomous)*
2. **THEN**: Make changes in the **sandbox organization** via MCP tools *(autonomous)*
3. **THEN**: Use `deploy_pull` to pull sandbox and `deploy_diff` to see changes *(autonomous)*
4. **THEN**: Show diff to user and **⏸️ WAIT FOR APPROVAL** ← *Only pause here*
5. **FINALLY**: Deploy to production only after user approval with `deploy_to_org`

---

## Available Deployment Tools

The following tools are available for deployment operations:

| Tool | Description |
|------|-------------|
| `deploy_pull` | Pull configuration from an organization to local files |
| `deploy_diff` | Compare local files with remote configuration |
| `deploy_push` | Push local changes to remote |
| `deploy_copy_org` | Copy entire organization to target org |
| `deploy_copy_workspace` | Copy a workspace and all objects to target org |
| `deploy_compare_workspaces` | Compare two local workspaces to see before/after differences |
| `deploy_to_org` | Deploy local changes to target org using ID mappings |

---

## Complete Deployment Workflow

### Step 1: Copy Workspace to Sandbox

Copy a workspace and all its objects (queues, schemas, hooks, connectors, inboxes, email templates, rules) to the target organization.

```
deploy_copy_workspace(
    source_workspace_id=1787227,
    target_org_id=729505,
    target_api_base="https://api.elis.rossum.ai/v1",  # Optional if same
    target_token="<sandbox_token>"
)
```

**Output:** Creates objects in sandbox and saves ID mappings. Returns summary with created/skipped/failed counts.

### Step 2: Make Changes in Sandbox

After copying, make modifications in the sandbox organization using MCP tools.

---

#### ⚠️ CRITICAL: Use `spawn_mcp_connection` + `call_on_connection` for Sandbox Operations

**You MUST spawn a connection to the sandbox environment to make changes there.**

The default MCP tools connect to the **SOURCE** environment, not the sandbox!

```
# Step 2a: Spawn sandbox MCP connection with TARGET credentials
spawn_mcp_connection(
    connection_id="sandbox",
    api_token="<sandbox_token>",  # ← TARGET token, not source!
    api_base_url="https://api.elis.rossum.ai/v1"
)

# Step 2b: Use call_on_connection() for ALL sandbox operations
call_on_connection("sandbox", "get_schema", '{"schema_id": 123}')
call_on_connection("sandbox", "update_schema", '{"schema_id": 123, ...}')
call_on_connection("sandbox", "create_hook", '{"name": "...", ...}')
```

| ❌ WRONG (uses source env) | ✅ CORRECT (uses sandbox env) |
|---------------------------|-------------------------------|
| `get_schema(schema_id=123)` | `call_on_connection("sandbox", "get_schema", '{"schema_id": 123}')` |
| `update_schema(schema_id=123, ...)` | `call_on_connection("sandbox", "update_schema", '{"schema_id": 123, ...}')` |

**⚠️ IMPORTANT: Spawned connections do NOT persist across conversation turns.**

If you started a sandbox connection in a previous message and the user sends a new message, you MUST call `spawn_mcp_connection()` again before using `call_on_connection()`. Check if you have an active connection by looking for a successful `spawn_mcp_connection` call **in your current turn**, not in previous messages.

---

### Step 3: Pull and Compare

After making changes, pull both configurations and compare them:

**Option A: Compare workspaces (recommended for before/after diff)**

Use `deploy_compare_workspaces` to see field-level diffs between sandbox state BEFORE and AFTER your changes:

```python
# Pull sandbox workspace BEFORE making changes (right after deploy_copy_workspace)
deploy_pull(
    workspace_id=<target_workspace_id>,  # Use ID from deploy_copy_workspace output
    workspace_path="./before-changes",
    api_base_url="https://api.elis.rossum.ai/v1",
    token="<sandbox_token>"
)

# ... make changes in sandbox via call_on_connection() ...

# Pull sandbox workspace AFTER making changes
deploy_pull(
    workspace_id=<target_workspace_id>,  # Same workspace ID
    workspace_path="./after-changes",
    api_base_url="https://api.elis.rossum.ai/v1",
    token="<sandbox_token>"
)

# Compare the two states to see what changed
deploy_compare_workspaces(
    source_workspace_path="./before-changes",
    target_workspace_path="./after-changes"
)
```

**Option B: Local vs remote diff**

Use `deploy_diff` to compare local files with remote configuration:

```
# Pull sandbox configuration
deploy_pull(
    org_id=729505,
    api_base_url="https://api.elis.rossum.ai/v1",
    token="<sandbox_token>"
)

# Check what changed vs remote
deploy_diff()
```

### Step 4: Show Diff to User and Wait for Approval

Present the diff to the user. **Always call `.summary()` on the comparison result** to get a concise, readable output:

```python
# Get the comparison result
result = deploy_diff()

# Display the summary to the user (NOT the raw result)
print(result.summary())
```

Example output format:
```
=== Deployment Diff ===
[Show result.summary() output here]

Do you want to deploy these changes to production?
```

**⚠️ NEVER proceed without explicit user approval.**

## ⚠️ Output Rules

- **DO NOT create markdown files** for summaries, diffs, or reports unless explicitly asked to by a user

### Step 5: Deploy to Production (After Approval)

Only after user explicitly approves:

```
# Dry run first to preview
deploy_to_org(
    target_org_id=123456,  # Production org
    target_api_base="https://api.elis.rossum.ai/v1",
    target_token="<production_token>",
    dry_run=True
)

# Execute deployment (only after user approval)
deploy_to_org(
    target_org_id=123456,
    target_api_base="https://api.elis.rossum.ai/v1",
    target_token="<production_token>",
    dry_run=False
)
```

---

## Tool Reference

### deploy_pull

Pull Rossum configuration objects to local files. **Use `workspace_id` (not `org_id`) for before/after comparisons.**

**Parameters:**
- `workspace_id` (recommended): The workspace ID to pull - use this for comparing workspaces
- `org_id` (alternative): The organization ID to pull from - pulls ALL workspaces (overkill for comparisons)
- `workspace_path` (optional): Path to workspace directory
- `api_base_url` (optional): API base URL for target environment
- `token` (optional): API token for target environment

### deploy_diff

Compare local workspace files with remote Rossum configuration.

**Parameters:**
- `workspace_path` (optional): Path to workspace directory

### deploy_push

Push local changes to Rossum.

**Parameters:**
- `dry_run` (optional): If True, only show what would be pushed
- `force` (optional): If True, push even if there are conflicts
- `workspace_path` (optional): Path to workspace directory

### deploy_copy_org

Copy all objects from source organization to target organization.

**Parameters:**
- `source_org_id` (required): Source organization ID
- `target_org_id` (required): Target organization ID
- `target_api_base` (optional): Target API base URL
- `target_token` (optional): Target API token
- `workspace_path` (optional): Path to workspace directory

### deploy_copy_workspace

Copy a single workspace and all its objects to target organization.

**Parameters:**
- `source_workspace_id` (required): Source workspace ID
- `target_org_id` (required): Target organization ID
- `target_api_base` (optional): Target API base URL
- `target_token` (optional): Target API token
- `workspace_path` (optional): Path to workspace directory

### deploy_compare_workspaces

Compare two local workspaces to see differences between source and target. Use this to see exactly what changed after making modifications in the sandbox.

**When to use:**
- After copying a workspace to sandbox and making changes, to see a detailed before/after diff
- When you need field-level comparison between source (production) and target (sandbox) configurations

**Parameters:**
- `source_workspace_path` (required): Path to the source (original/production) workspace directory
- `target_workspace_path` (required): Path to the target (modified/sandbox) workspace directory
- `id_mapping_path` (optional): Path to ID mapping JSON file from `deploy_copy_workspace`. If None, objects are matched by their original IDs.

**Example workflow:**
```python
# 1. Copy workspace to sandbox
deploy_copy_workspace(source_workspace_id=1787227, target_org_id=729505, ...)

# 2. Pull sandbox workspace BEFORE making changes
deploy_pull(workspace_id=<target_workspace_id>, workspace_path="./before-changes", token="<sandbox_token>")

# 3. Make changes in sandbox via call_on_connection()...

# 4. Pull sandbox workspace AFTER changes
deploy_pull(workspace_id=<target_workspace_id>, workspace_path="./after-changes", token="<sandbox_token>")

# 5. Compare before vs after states
deploy_compare_workspaces(
    source_workspace_path="./before-changes",
    target_workspace_path="./after-changes"
)
```

### deploy_to_org

Deploy local configuration changes to a target organization.

**Parameters:**
- `target_org_id` (required): Target organization ID
- `target_api_base` (optional): Target API base URL
- `target_token` (optional): Target API token
- `dry_run` (optional): If True, only show what would be deployed
- `workspace_path` (optional): Path to workspace directory

---

## Safety Notes

- **Never modify production directly** - always use sandbox
- **Always copy first** - sandbox starts empty until you copy
- **Always show diff** before deploying
- **Never deploy without user approval**
- Use `dry_run=True` first to preview operations
- ID mappings are saved automatically by copy operations

---

## ⚠️ Common Mistakes to Avoid

1. **Skipping the copy step** - The sandbox organization has NO objects until you copy from production.

2. **Using wrong credentials** - Source operations use default env vars, target operations need explicit `token` parameter.

3. **Calling MCP tools directly instead of call_on_connection** - Default MCP tools operate on source environment.
   - **Symptom:** Changes appear in production instead of sandbox
   - **Fix:** Always use `spawn_mcp_connection` + `call_on_connection` for sandbox operations

4. **Deploying without diff review** - Always run `deploy_diff()` and show the user before deploying.

5. **Deploying without confirmation** - Always require explicit user approval before calling `deploy_to_org`.

6. **Forgetting to remap token owners** - Hooks with `token_owner` reference users that don't exist in the target organization. When deploying hooks to a different org, **ask the user which user in the target org should be the token owner**. Use `list_users` on the target org to find available users.

7. **Assuming spawned connections persist across turns** - Spawned MCP connections are cleared when a new conversation turn starts. If you used `spawn_mcp_connection` in a previous message, you must call it again in your current turn before using `call_on_connection`.
