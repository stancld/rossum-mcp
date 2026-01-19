# Match API Client to OpenAPI Spec

**Goal**: Verify API client coverage matches OpenAPI specification - no missing endpoints, no unnecessary implementations.

## Scope

| Input | Files to Analyze |
|-------|------------------|
| OpenAPI spec | `openapi.json` |
| Client impl | `rossum_agent_client/client.py` |
| Models | `rossum_agent_client/models/` |

## What to Check

| Category | Criteria |
|----------|----------|
| Missing endpoints | API paths in spec without client methods |
| Orphan methods | Client methods not backed by spec endpoints |
| Parameter mismatch | Client params don't match spec (required/optional, types) |
| Response models | Client response types align with spec schemas |
| HTTP methods | Client uses correct method (GET/POST/DELETE) per spec |

## Approach

| Step | Action |
|------|--------|
| Parse spec | Extract all paths, methods, parameters, schemas from `openapi.json` |
| Scan client | Identify all API methods, their HTTP calls, and parameters |
| Map | Create endpoint-to-method mapping |
| Diff | Identify gaps in both directions |
| Report | Output findings per category |

## Output Format

```
## API Client Coverage Report

### Missing Endpoints (in spec, not in client)
- [ ] `POST /api/endpoint` - description from spec

### Orphan Methods (in client, not in spec)
- [ ] `client.method_name()` - calls `POST /unknown`

### Parameter Mismatches
- [ ] `client.method()` - missing required param `x` from spec
- [ ] `client.method()` - extra param `y` not in spec

### Type Mismatches
- [ ] `client.method()` returns `X`, spec defines `Y`
```

## Constraints

- No automatic modifications
- Report discrepancies only
- Consider both sync and async client implementations
