# Security

## Authentication Model

rossum-mcp authenticates to the Rossum API using a **user-scoped API token** (`ROSSUM_API_TOKEN`). The token is required at startup and attached to every API request via the `rossum-api` SDK.

### User-Scoped Access

The Rossum API enforces strict organization-level isolation on the backend:

1. Every API token is bound to a **specific user and organization**.
2. All API responses are filtered server-side — a token can only access resources belonging to its organization.
3. Additional scoping layers (workspace, queue, annotation) further restrict visibility based on the user's role and permissions.

**rossum-mcp does not implement its own authorization.** It delegates all access control to the Rossum API, which is the authoritative source of truth for what a given token can see and do.

### What This Means in Practice

- A user running rossum-mcp sees **only their organization's resources** (workspaces, queues, schemas, annotations, hooks, etc.).
- Read/write boundaries are enforced by both the Rossum API (role-based permissions) and rossum-mcp's `ROSSUM_MCP_MODE` setting.
- There is no way to escalate access beyond what the underlying token grants.

## Application-Level Controls

| Control | Description |
|---------|-------------|
| `ROSSUM_MCP_MODE=read-only` | Disables all write operations at the MCP layer, regardless of the token's API permissions |
| Schema content validation | Schema content is validated and sanitized before API submission (strips invalid values, coerces types) |
| No token logging | The API token is never logged or exposed in tool outputs |
| Immutable config | Server configuration (including the token) is stored in a frozen dataclass and cannot be changed at runtime |

## Best Practices

- **Rotate tokens regularly.** Token rotation requires a server restart with the new value.
- **Use read-only mode** when the MCP server is used for exploration or monitoring only.
- **Never commit tokens.** Use environment variables or a `.env` file (gitignored).
- **Scope to least privilege.** Use a token from a user account with only the permissions needed for the intended workflow.

## Reporting Vulnerabilities

If you discover a security issue, please use [GitHub's private vulnerability reporting](https://github.com/stancld/rossum-agents/security/advisories/new) to submit a description, reproduction steps, and affected package(s). Do not open a public issue.
