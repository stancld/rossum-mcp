---
name: Hooks
description: hook templates, token_owner, testing, debugging
---

# Hooks Skill

**Goal**: Create, configure, and test hooks — prefer Rossum Store templates over custom code.

## Constraints

| Constraint | Detail |
|------------|--------|
| Templates first | `search(query={"entity": "hook_template"})` before writing custom code — most use cases are covered |
| Custom code last resort | Only write custom serverless functions when no template covers the requirement |

## Hook Types

| Type | Purpose | Key config |
|------|---------|------------|
| `function` | Serverless Python executed by Rossum | `config.code`, `config.runtime`, `config.timeout_s` |
| `webhook` | External HTTP endpoint | `settings` for auth/headers |
| `job` | Scheduled/invocation-based | Used with `invocation.*` events |

## Events

Events use strict `event.action` format — passing just `"annotation_content"` is invalid.

| Event | Actions |
|-------|---------|
| `annotation_content` | `initialize`, `started`, `user_update` (deprecated — use `updated`), `updated`, `confirm`, `export` |
| `annotation_status` | `changed` |
| `invocation` | `manual`, `scheduled`, `interface` |
| `upload` | `created` |
| `email` | `received` |

## Creating from Templates

```
search(query={"entity": "hook_template"})
create_hook_from_template(name="My Hook", hook_template_id=123, queues=["https://..."], token_owner="https://.../users/456")
```

Before calling `create_hook_from_template`:

| Check | Why |
|-------|-----|
| `use_token_owner` | If `true`, `token_owner` is required |
| `events` | Template defaults; can override but not all overrides are compatible |
| `secrets_schema` | Template may need secrets (API keys) configured after creation |

## Creating Custom Hooks

```
create_hook(name="My Hook", type="function", queues=["https://..."], events=["annotation_content.export"], config={"source": "<code>"}, token_owner="https://.../users/456", run_after=["https://.../hooks/99"], sideload=["schemas"])
```

### Function hook config

| Field | Detail |
|-------|--------|
| `config.source` | Auto-renamed to `config.code` before API call |
| `config.runtime` | Defaults to `python3.12` if omitted |
| `config.timeout_s` | Silently capped at 60 seconds |

### Webhook hook config

| Field | Detail |
|-------|--------|
| `settings` | Webhook-specific configuration (headers, auth, etc.) |

## token_owner

| Rule | Detail |
|------|--------|
| Format | User URL: `https://<base>/users/<id>` |
| Required when | Template has `use_token_owner=true`, or hook needs API access (annotation actions, connector calls) |
| Forbidden role | `organization_group_admin` users cannot be token owners |
| Finding a valid user | `search(query={"entity": "user", "is_organization_group_admin": false})` -> use `url` field of an active user |

## Secrets

`secrets` is a `dict[str, str]` of key-value env vars for serverless functions (API keys, credentials).

| Behavior | Detail |
|----------|--------|
| Write-only | Values are never returned by the API — `get(entity="hook")` always shows `secrets: {}` even when secrets are set |
| Set via | `create_hook(secrets={"KEY": "val"})` or `update_hook(secrets={"KEY": "val"})` |
| Check configured keys | `get(entity="hook_secrets_keys", entity_id=<hook_id>)` — returns list of key names (not values) |
| Schema | `secrets_schema` on the hook defines which keys are expected |

## Sideloads

`sideload` controls which related objects are included in hook request payloads when the hook fires. Annotation content is always auto-included for `annotation_content` events — no sideload needed.

| Allowed values |
|----------------|
| `queues`, `modifiers`, `schemas`, `emails`, `related_emails`, `relations`, `child_relation`, `notes`, `suggested_edits`, `assignees`, `pages`, `labels`, `automation_blockers` |

## run_after

`run_after` takes a list of **hook URLs** (not IDs) that must execute before this hook.

```
run_after=["https://.../hooks/99", "https://.../hooks/100"]
```

Circular dependencies will be rejected by the API.

## TxScript Boilerplate

Custom function hooks use TxScript — a Python 3.12 DSL for field manipulation:

```python
from txscript import TxScript, is_set, is_empty, default_to

def rossum_hook_request_handler(payload):
    t = TxScript.from_payload(payload)

    # Read: t.field.<schema_id>
    # Write: t.field.<schema_id> = new_value
    # Check: is_set(t.field.x), is_empty(t.field.x)

    return t.hook_response()
```

| Rule | Detail |
|------|--------|
| Never use `is None` | Use `is_empty()` / `is_set()` — fields are `None`-like but not `None` |
| Always return `t.hook_response()` | Omitting causes silent failures |

Load `txscript` skill for advanced patterns (line items, table columns, messaging, annotation actions).

## Testing

```
test_hook(hook_id, event, action)
```

`event` and `action` are separate params (not dot-joined) — e.g., `event="annotation_content", action="export"`.

| Rule | Detail |
|------|--------|
| Annotation required | `annotation_content` and `annotation_status` events need an annotation — `test_hook` auto-resolves from hook's queues |
| Before calling `test_hook` | `search(query={"entity": "annotation", "queue_id": <queue_id>})` to verify annotations exist |
| No annotations found | Ask user to upload a document first — never upload documents yourself for testing |
| `status`/`previous_status` | Auto-default to `to_review`/`importing` if not provided |

## Updating Hooks

`update_hook` is a partial update — only provided fields change. Existing `name`, `queues`, `events`, `config` are preserved as baseline.

To update function code: pass the full new `config` dict (including `code`/`source`, `runtime`, `timeout_s`).

## Debugging

`search(query={"entity": "hook_log", "hook_id": 123})` — 7-day retention, max 100 per call. Filter by `log_level`, `status`, `annotation_id`, time range.

## Common Pitfalls

| Pitfall | Detail |
|---------|--------|
| Wrong event format | Must be `"event.action"` (e.g., `"annotation_content.export"`), not just `"annotation_content"` |
| `secrets` looks empty | `secrets` is write-only — API always returns `{}` even when set; use `get(entity="hook_secrets_keys")` to check configured keys |
| Timeout silently capped | `timeout_s > 60` is silently reduced to 60 — no error raised |
| Token owner role | `organization_group_admin` users silently fail as token owners — always verify role first |
| Test without annotations | Testing annotation events fails if no annotations exist on the hook's queues |
| `run_after` format | Takes hook **URLs**, not hook IDs |
| `queues` format | Takes queue **URLs**, not queue IDs |

## Cross-Reference

- Formula fields (no hook needed): load `formula-fields` skill
