# Rossum Deployment Skill

This skill provides a safe workflow for deploying Rossum configuration changes using the `Workspace` class from `rossum_deploy`.

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
- Target (write): TARGET_ROSSUM_API_TOKEN (+ target_api_base if different)
```

---

## ⚠️ MANDATORY WORKFLOW - FOLLOW THESE STEPS IN ORDER

**CRITICAL: Never modify production directly. Always use a sandbox organization for changes.**

### 🤖 Autonomous Execution Policy

**The agent MUST proceed autonomously through Steps 1-5 without asking for user input.**

Only pause and wait for user approval at Step 5 after displaying the diff. Do NOT ask for confirmation before copying, making changes, or pulling workspaces.

### Required Step Order:
1. **FIRST**: Copy workspace → sandbox using `ws.copy_workspace()` *(autonomous)*
1b. **IMMEDIATELY AFTER COPY**: Pull sandbox to capture baseline with `before_ws.pull_workspace()` *(autonomous)*
2. **THEN**: Make changes in the **sandbox organization** *(autonomous)*
3. **THEN**: Pull sandbox again to capture changes with `after_ws.pull_workspace()` *(autonomous)*
4. **THEN**: Compare before vs after with `after_ws.compare_workspaces(source_workspace=before_ws)` *(autonomous)*
5. **THEN**: Show diff to user and **⏸️ WAIT FOR APPROVAL** ← *Only pause here*
6. **FINALLY**: Deploy to production only after user approval with `ws.deploy()`

---

## When to Use This Skill

Load this skill when the user asks to:
- Create or update queues, schemas, hooks, or extensions
- Set up document splitting, sorting, or automation
- Deploy configuration changes
- Copy configurations between organizations

---

## Using the Workspace Class

The `Workspace` class from `rossum_deploy` provides all deployment operations.

### Initialization

```python
from rossum_deploy import Workspace

# Environment variables (or user-provided)
ROSSUM_API_BASE_URL = "https://api.elis.rossum.ai/v1"
ROSSUM_API_TOKEN = "<source_token>"
TARGET_ROSSUM_API_TOKEN = "<target_token>"

# Create workspace instance
ws = Workspace(
    "./my-project",  # Local directory for config files
    api_base=ROSSUM_API_BASE_URL,
    token=ROSSUM_API_TOKEN
)
```

---

## Complete Deployment Workflow

### Step 1: Copy Workspace to Sandbox

Copy a workspace and all its objects (queues, schemas, hooks, connectors, inboxes, email templates, rules) to the target organization.

```python
copy_result = ws.copy_workspace(
    source_workspace_id=1787227,
    target_org_id=729505,
    target_api_base=ROSSUM_API_BASE_URL,  # Same or different API base
    target_token=TARGET_ROSSUM_API_TOKEN,
)

# copy_result contains:
# - copy_result.created: List of (ObjectType, source_id, target_id, name)
# - copy_result.failed: List of (ObjectType, source_id, name, error)
# - copy_result.skipped: List of (ObjectType, source_id, name, reason)
# - copy_result.id_mapping: IdMapping object with source→target ID mappings
```

**Output:** Creates objects in sandbox and saves ID mappings to `.id_mapping_<source>_to_<target>.json`.

### Step 1b: Pull Sandbox Immediately After Copy (Baseline)

**Right after copying, pull the sandbox to capture the "before" state:**

```python
# Pull sandbox immediately after copy to capture baseline state
before_ws = Workspace("./before-config", api_base=ROSSUM_API_BASE_URL, token=TARGET_ROSSUM_API_TOKEN)
target_workspace_id = copy_result.id_mapping.get(ObjectType.WORKSPACE, SOURCE_WORKSPACE_ID)
before_ws.pull_workspace(workspace_id=target_workspace_id)
```

This creates a snapshot of the sandbox state BEFORE any changes are made.

### Step 2: Make Changes in Sandbox

After copying, make modifications in the sandbox organization.

---

#### ⚠️ CRITICAL: You MUST Use Target IDs from `id_mapping`

**After `copy_workspace()`, target objects have DIFFERENT IDs than source objects.**

The `copy_result.id_mapping` maps source IDs → target IDs. You MUST extract target IDs before making any calls:

```python
from rossum_deploy import ObjectType

# Get target IDs from the copy result
target_workspace_id = copy_result.id_mapping.get(ObjectType.WORKSPACE, source_workspace_id)
target_queue_id = copy_result.id_mapping.get(ObjectType.QUEUE, source_queue_id)
target_schema_id = copy_result.id_mapping.get(ObjectType.SCHEMA, source_schema_id)
target_hook_id = copy_result.id_mapping.get(ObjectType.HOOK, source_hook_id)

# Print the mapping for reference
print(f"Source queue {source_queue_id} → Target queue {target_queue_id}")
print(f"Source schema {source_schema_id} → Target schema {target_schema_id}")
```

**Available ObjectType values:** `WORKSPACE`, `QUEUE`, `SCHEMA`, `HOOK`, `INBOX`, `CONNECTOR`, `ENGINE`, `EMAIL_TEMPLATE`, `RULE`

---

#### Via MCP tools with sandbox credentials

```python
# Step 2a: Spawn sandbox MCP connection with TARGET credentials
spawn_mcp_connection(
    connection_id="sandbox",
    api_token=TARGET_ROSSUM_API_TOKEN,  # ← TARGET token, not source!
    api_base_url=ROSSUM_API_BASE_URL
)

# Step 2b: Get TARGET IDs from the id_mapping
target_schema_id = copy_result.id_mapping.get(ObjectType.SCHEMA, source_schema_id)
target_queue_id = copy_result.id_mapping.get(ObjectType.QUEUE, source_queue_id)

# Step 2c: Use call_on_connection() with TARGET IDs for ALL sandbox operations
call_on_connection("sandbox", "get_schema", f'{{"schema_id": {target_schema_id}}}')
call_on_connection("sandbox", "update_schema", f'{{"schema_id": {target_schema_id}, ...}}')
call_on_connection("sandbox", "get_queue", f'{{"queue_id": {target_queue_id}}}')
```

---

#### ⚠️ CRITICAL: Use `call_on_connection()` for ALL Sandbox Operations

**You MUST use `call_on_connection("sandbox", ...)` to interact with the sandbox environment.**

The default MCP tools (e.g., `get_schema`, `update_schema`, `get_queue`) connect to the **SOURCE** environment, not the sandbox!

| ❌ WRONG (uses source env) | ✅ CORRECT (uses sandbox env) |
|---------------------------|-------------------------------|
| `get_schema(schema_id=123)` | `call_on_connection("sandbox", "get_schema", '{"schema_id": 123}')` |
| `update_schema(schema_id=123, ...)` | `call_on_connection("sandbox", "update_schema", '{"schema_id": 123, ...}')` |
| `get_queue(queue_id=456)` | `call_on_connection("sandbox", "get_queue", '{"queue_id": 456}')` |

**Common mistakes:**
1. Using `source_schema_id` instead of `target_schema_id` → results in 404 errors
2. Calling `get_schema(...)` directly instead of `call_on_connection("sandbox", "get_schema", ...)` → operates on wrong environment

### Step 3: Pull Sandbox Again (After Changes)

After making changes in sandbox, pull again to capture the "after" state:

```python
# Pull sandbox after changes to capture final state
after_ws = Workspace("./after-config", api_base=ROSSUM_API_BASE_URL, token=TARGET_ROSSUM_API_TOKEN)
after_ws.pull_workspace(workspace_id=target_workspace_id)
```

### Step 4: Compare Before vs After (Diff)

Compare the sandbox **before** and **after** your changes to show exactly what was modified:

```python
# Compare before vs after to see what the agent changed
# before_ws (caller) = source, after_ws = target
compare_result = before_ws.compare_workspaces(
    target_workspace=after_ws,
    id_mapping=None,  # No mapping needed - same workspace at different times
)

# Display the diff
print(compare_result.summary())

# Access detailed differences:
# - compare_result.objects: List of ObjectCompare with field-level diffs
# - compare_result.source_only: Objects deleted (were in before, not in after)
# - compare_result.target_only: Objects created (not in before, now in after)
# - compare_result.total_identical: Count of unchanged objects
# - compare_result.total_different: Count of changed objects
```

**This shows the user exactly what changes the agent made**, not the differences between prod and sandbox.

### Step 5: Show Diff to User and Wait for Approval

Present the diff to the user:

```python
print("=== Deployment Diff ===")
print(compare_result.summary())
print("\nDo you want to deploy these changes to production?")
```

**⚠️ NEVER proceed without explicit user approval.**

### Step 6: Deploy to Production (After Approval)

Only after user explicitly approves:

```python
# Dry run first to preview
deploy_result = after_ws.deploy(
    target_org_id=<production_org_id>,
    target_api_base=ROSSUM_API_BASE_URL,
    target_token=ROSSUM_API_TOKEN,  # Production token
    id_mapping=copy_result.id_mapping,
    dry_run=True,
)
print("Dry run:", deploy_result.summary())

# Execute deployment (only after user approval)
deploy_result = after_ws.deploy(
    target_org_id=<production_org_id>,
    target_api_base=ROSSUM_API_BASE_URL,
    target_token=ROSSUM_API_TOKEN,
    id_mapping=copy_result.id_mapping,
    dry_run=False,
)
print("Deployed:", deploy_result.summary())
```

---

## Example: Complete Workflow Script

```python
from rossum_deploy import Workspace, ObjectType

# Configuration
ROSSUM_API_BASE_URL = "https://api.elis.develop.r8.lol/v1"
ROSSUM_API_TOKEN = "<production_token>"
TARGET_ROSSUM_API_TOKEN = "<sandbox_token>"

SOURCE_WORKSPACE_ID = 1787227
TARGET_ORG_ID = 729505
PRODUCTION_ORG_ID = 123456  # Your production org ID

# Step 1: Copy workspace to sandbox
ws = Workspace("./my-project", api_base=ROSSUM_API_BASE_URL, token=ROSSUM_API_TOKEN)

copy_result = ws.copy_workspace(
    source_workspace_id=SOURCE_WORKSPACE_ID,
    target_org_id=TARGET_ORG_ID,
    target_api_base=ROSSUM_API_BASE_URL,
    target_token=TARGET_ROSSUM_API_TOKEN,
)
print("Copied:", copy_result.summary())

# Step 1b: Pull sandbox immediately to capture baseline state
target_workspace_id = copy_result.id_mapping.get(ObjectType.WORKSPACE, SOURCE_WORKSPACE_ID)
before_ws = Workspace("./before-config", api_base=ROSSUM_API_BASE_URL, token=TARGET_ROSSUM_API_TOKEN)
before_ws.pull_workspace(workspace_id=target_workspace_id)
print("Captured baseline state")

# Step 2: Agent makes changes in sandbox (via MCP with sandbox credentials)
# ... changes happen here via spawn_mcp_connection + call_on_connection ...

# Step 3: Pull sandbox again to capture changes
after_ws = Workspace("./after-config", api_base=ROSSUM_API_BASE_URL, token=TARGET_ROSSUM_API_TOKEN)
after_ws.pull_workspace(workspace_id=target_workspace_id)
print("Captured final state")

# Step 4: Compare before vs after to see what agent changed
# before_ws (caller) = source, after_ws = target
compare_result = before_ws.compare_workspaces(
    target_workspace=after_ws,
    id_mapping=None,  # No mapping needed - same workspace at different times
)

# Step 5: Show diff and get approval
print("=== Changes Made by Agent ===")
print(compare_result.summary())
approval = input("Deploy to production? (yes/no): ")

# Step 6: Deploy if approved
if approval.lower() == "yes":
    deploy_result = after_ws.deploy(
        target_org_id=PRODUCTION_ORG_ID,
        target_api_base=ROSSUM_API_BASE_URL,
        target_token=ROSSUM_API_TOKEN,  # Production token
        id_mapping=copy_result.id_mapping,
        dry_run=False,
    )
    print("Deployed:", deploy_result.summary())
```

---

## File Structure

After operations:
```
my-project/
├── .rossum-deploy.yaml                    # Config file
├── .id_mapping_<source>_to_<target>.json  # ID mappings from copy_workspace
├── workspaces/
├── queues/
├── schemas/
├── hooks/
├── inboxes/
├── connectors/
├── engines/
├── email_templates/
└── rules/
```

---

## Available Workspace Methods

| Method | Description |
|--------|-------------|
| `copy_workspace()` | Copy a workspace and all objects to target org |
| `copy_org()` | Copy entire organization to target org |
| `pull()` | Pull all objects from an organization |
| `pull_workspace()` | Pull a specific workspace and related objects |
| `compare_workspaces()` | Compare two workspaces with ID mapping |
| `diff()` | Compare local files vs remote |
| `push()` | Push local changes to remote |
| `deploy()` | Deploy to target org using ID mappings |

---

## Safety Notes

- **Never modify production directly** - always use sandbox
- **Always copy first** - sandbox starts empty until you copy
- **Always show diff** before deploying
- **Never deploy without user approval**
- Use `dry_run=True` first to preview operations
- Use `dry_run=False` to execute the actual deployment (only after user approval)
- ID mappings are saved automatically by copy operations

---

## ⚠️ Common Mistakes to Avoid

1. **Skipping the copy step** - The sandbox organization has NO objects until you copy from production.

2. **Using wrong credentials** - Source operations use `ROSSUM_API_TOKEN`, target operations need `TARGET_ROSSUM_API_TOKEN`.

3. **Using source IDs in target (CAUSES 404 ERRORS!)** - After copy, target objects have DIFFERENT IDs.
   - **Symptom:** `HTTP 404 - {"detail":"Not found."}` when calling MCP tools on sandbox
   - **Cause:** Using source IDs like `4068086` instead of target IDs from `id_mapping`
   - **Fix:** Always use `copy_result.id_mapping.get(ObjectType.SCHEMA, source_id)` to get target IDs

4. **Deploying without diff review** - Always run `compare_workspaces()` and show the user before deploying.

5. **Deploying without confirmation** - Always require explicit user approval before calling `deploy(confirm=True)`.
