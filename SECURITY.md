# Security Policy

## Supported Versions

Only the latest released version of each package receives security updates.

## Reporting a Vulnerability

Please **do not** open a public issue. Instead, use [GitHub's private vulnerability reporting](https://github.com/rossumai/rossum-agents/security/advisories/new) to submit a description, reproduction steps, and affected package(s). You can expect a response within 72 hours.

## What's in Place

- **CodeQL** and **Snyk** scan every push and PR for vulnerabilities
- **Rate limiting** on the agent API via `slowapi`
- **Read-only mode** (`ROSSUM_MCP_MODE=read-only`) to disable all write operations
- **Schema content validation** before API submission (strips invalid values, coerces types)
- **CORS** restricted to allowed origins

For package-specific security details, see [rossum-mcp/SECURITY.md](rossum-mcp/SECURITY.md).

## Credentials

Never commit tokens or secrets. Use environment variables or a `.env` file (gitignored).

```bash
export ROSSUM_API_TOKEN="your-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
```
