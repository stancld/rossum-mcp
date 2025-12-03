# Development Guidelines

## Commands
- **Python setup**: `pip install -e .`
- **Run server**: `python server.py`
- **Lint & type check**: `pre-commit run --all-files`
- **Individual tools**: `ruff check --fix`, `ruff format`, `mypy --config-file=mypy.ini`

## Architecture
- Single-file MCP server (`server.py`) for Rossum API integration
- Main class: `RossumMCPServer` with async tool handlers
- 20 tools including `upload_document`, `get_annotation`, `list_annotations`, `create_hook`, `list_hooks`, `list_rules`, etc.
- Sync API client wrapped in async executors for MCP compatibility
- Examples in `examples/` directory

## Documentation Updates

**CRITICAL**: When adding, removing, or modifying tools (MCP or agent tools), you MUST update documentation to keep it in sync with the code.

### Files to Update When Adding/Modifying MCP Tools:

1. **`rossum_mcp/README.md`**:
   - Update the Features section to list the new tool
   - Add complete tool documentation under "Available Tools" section:
     - Tool name and description
     - Parameters (with types and descriptions)
     - Return format (with JSON examples)
     - Usage examples

2. **`docs/source/index.rst`**:
   - Update the tool count in "Features" section (e.g., "20 tools" → "21 tools")
   - Add the new tool to the appropriate category bullet list:
     - Document Processing
     - Queue & Schema Management
     - Engine Management
     - Extensions & Rules

3. **`docs/source/usage.rst`**:
   - Add full tool documentation in reStructuredText format:
     - Tool heading (using `^^^^^` underline)
     - Description paragraph
     - Parameters section with proper RST formatting
     - Returns section with `.. code-block:: json` examples
     - Optional example usage with `.. code-block:: python`

4. **`docs/source/mcp_reference.rst`** (if applicable):
   - Add SDK mapping documentation if the tool uses new SDK methods
   - Document API endpoints and query parameters
   - Include implementation notes

### Files to Update When Adding/Modifying Agent Tools:

1. **`rossum_agent/README.md`**:
   - Update the Features section to list the new tool category (if new)
   - Add complete tool documentation under the appropriate section:
     - File System Tools
     - Plotting Tools
     - Hook Analysis Tools
     - Internal Tools
   - Include parameters, return values, and usage examples

2. **`docs/source/index.rst`**:
   - Add the new tool to the "AI Agent Toolkit" feature list if it represents a new category

3. **`docs/source/usage.rst`**:
   - Add full tool documentation in the "Agent Tools" section
   - Use proper RST formatting with tool name as heading
   - Include parameters, returns, and example code blocks
   - Place under appropriate category subsection

### Documentation Checklist:
- [ ] Updated tool count/features in `docs/source/index.rst` (if applicable)
- [ ] Added tool to appropriate category in `index.rst` and corresponding README.md
- [ ] Documented parameters, return values, and examples in all relevant files
- [ ] Verified examples match actual tool signatures in code
- [ ] Built and reviewed generated documentation locally (if docs changes)

### Verification:
After updating documentation, verify consistency by checking:
```bash
# Check that tool definitions in server.py match documentation
grep -A5 "Tool(" rossum_mcp/server.py | grep "name="
grep "^\*\*" docs/source/index.rst
grep "^###" rossum_mcp/README.md | grep -i "available tools" -A50
```

## Code Style
- **Python version**: 3.12+ syntax required
- **Typing**: Use modern union syntax (`str | None`, not `Optional[str]`) and built-ins (`list[str]`, `dict[str, int]`). Avoid using `Any` type annotation as much as possible - use specific types instead
- **Imports**: Use `from pathlib import Path`, standard library first. Do NOT add try/except blocks for missing imports - assume all dependencies are installed
- **Async**: Wrap sync operations with `ThreadPoolExecutor` for MCP
- **Logging**: File-based logging to `/tmp/` since stdout is MCP protocol
- **Error handling**: Return JSON error objects, include tracebacks for debugging
- **Comments**: Brief, explain why not what
- **Quality**: Use pre-commit hooks (ruff, mypy, codespell) before committing
- **Development workflow**: After making code changes, iteratively run `pre-commit run --all-files` and fix all mypy type errors until the checks pass cleanly

## Environment
- Required: `ROSSUM_API_TOKEN`, `ROSSUM_API_BASE_URL`
- Optional Redis: `REDIS_HOST`, `REDIS_PORT` (default: 6379)
- Optional: `ROSSUM_MCP_MODE` (read-only or read-write), `ENVIRONMENT` (development/production)
- Optional: `ENABLE_USER_ISOLATION` (true/false, default: false) - Enable per-user chat isolation when deployed behind Teleport
- MCP client configuration in Claude Desktop or smolagents

### User Isolation Feature
When `ENABLE_USER_ISOLATION=true`, the agent isolates chat history per user when deployed behind Teleport:
- Detects user ID from Teleport headers (`X-Teleport-Login`, `X-Forwarded-User`)
- Falls back to Teleport session cookie if headers unavailable
- Redis keys pattern: `user:{user_id}:chat:{chat_id}` (vs shared `chat:{chat_id}`)
- Each user sees only their own chat history in the sidebar
- Disable for local development (default): all users share chat history

## Redis Logging Setup
1. **Start Redis**: `docker-compose up redis -d`
2. **Set environment variables**:
   ```bash
   export REDIS_HOST=localhost
   export REDIS_PORT=6379
   ```
3. **View logs**: Use Redis CLI to view logs:
   ```bash
   redis-cli LRANGE logs:$(date +%Y-%m-%d) 0 -1
   ```
