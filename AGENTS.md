# Development Guidelines

## Git Workflow
- **NEVER commit or push automatically** - Only run `git commit` or `git push` when explicitly instructed by the user
- Suggest commit messages when asked, but wait for user approval before committing

## Commands
- **Python setup**: `pip install -e .`
- **Run server**: `python server.py`
- **Run tests**: `pytest` (run all tests), `pytest path/to/test_file.py` (run specific test)
- **Lint & type check**: `pre-commit run --all-files`
- **Individual tools**: `ruff check --fix`, `ruff format`, `mypy --config-file=mypy.ini`

## Architecture
- Single-file MCP server (`server.py`) for Rossum API integration
- Main class: `RossumMCPServer` with async tool handlers
- 21 tools including `upload_document`, `get_annotation`, `list_annotations`, `get_hook`, `create_hook`, `list_hooks`, `list_rules`, etc.
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

## Testing Requirements

**CRITICAL**: When adding new features or modifying existing code, you MUST write tests.

### When to Write Tests:
- **New functions/methods**: Write unit tests for all new functions and methods
- **New MCP tools**: Add integration tests in `rossum-mcp/tests/test_server.py`
- **New agent tools**: Add unit tests in `rossum-agent/tests/`
- **Bug fixes**: Add regression tests to prevent the bug from reoccurring
- **Modified logic**: Update existing tests and add new ones for changed behavior
- **New modules**: Create corresponding test file (e.g., `foo.py` → `test_foo.py`)

### Test Structure:
- Place tests in `tests/` directory mirroring the source structure
- Use pytest fixtures for common setup (see `conftest.py`)
- Test file naming: `test_<module_name>.py`
- Test function naming: `test_<functionality>_<scenario>`

### Test Coverage Guidelines:
- **Unit tests**: Test individual functions/methods in isolation
- **Integration tests**: Test MCP tool handlers end-to-end
- **Mock external dependencies**: Use `unittest.mock` for API calls, file I/O, etc.
- **Edge cases**: Test error conditions, empty inputs, boundary values
- **Async code**: Use `pytest-asyncio` for async function tests

### Development Workflow:
1. Write/modify code
2. Write/update tests for your changes
3. Run tests: `pytest path/to/test_file.py`
4. Verify all tests pass: `pytest`
5. Run pre-commit hooks: `pre-commit run --all-files`
6. Fix any issues and repeat until all checks pass

## Code Style
- **YAGNI**: Don't add functionality until it's actually needed. Remove unused code, endpoints, and features proactively.
- **Python version**: 3.12+ syntax required
- **Typing**: Use modern union syntax (`str | None`, not `Optional[str]`) and built-ins (`list[str]`, `dict[str, int]`). Avoid using `Any` type annotation as much as possible - use specific types instead
- **Imports**: Use `from pathlib import Path`, standard library first. Do NOT add try/except blocks for missing imports - assume all dependencies are installed
- **Async**: Wrap sync operations with `ThreadPoolExecutor` for MCP
- **Logging**: File-based logging to `/tmp/` since stdout is MCP protocol
- **Error handling**: Return JSON error objects, include tracebacks for debugging
- **Comments**: Brief, explain why not what
- **Noqa/type-ignore comments**: Always add an explanatory comment when using `# noqa` or `# type: ignore`. Explain why the suppression is necessary (e.g., `# noqa: TC003 - Callable used in type annotation at runtime for FastAPI`)
- **Quality**: Use pre-commit hooks (ruff, mypy, codespell) before committing
- **Development workflow**: After making code changes, iteratively run `pre-commit run --all-files` and fix all mypy type errors until the checks pass cleanly

## Environment
- Required: `ROSSUM_API_TOKEN`, `ROSSUM_API_BASE_URL`
- Optional Redis: `REDIS_HOST`, `REDIS_PORT` (default: 6379)
- Optional: `ROSSUM_MCP_MODE` (read-only or read-write), `ENVIRONMENT` (development/production)
- Optional: `TELEPORT_JWT_JWKS_URL` for JWT verification and user isolation
- Optional: `PUBLIC_URL` for shareable links on remote servers (e.g., `https://your-domain.com`)
- MCP client configuration in Claude Desktop

### User Isolation Feature
User isolation is automatically enabled when `TELEPORT_JWT_JWKS_URL` is configured:
- Extracts username from `Teleport-Jwt-Assertion` header (JWT token)
- JWT token is the only supported authentication method
- Redis keys pattern: `user:{user_id}:chat:{chat_id}` (vs shared `chat:{chat_id}`)
- Each user sees only their own chat history in the sidebar
- Local development (no JWT config): all users share chat history

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

## Code Review Guidelines

When performing code reviews, evaluate the following aspects:

### Architecture & Design
- Single Responsibility: Each class/function should have one clear purpose
- Separation of concerns: Business logic, I/O, and presentation should be separate
- Dependency injection: Prefer injected dependencies over hard-coded ones
- Error boundaries: Errors should be handled at appropriate levels

### Code Quality
- **Type safety**: All functions should have type hints; avoid `Any` where possible
- **Error handling**: Exceptions should be caught, logged, and handled gracefully
- **Logging**: Sufficient logging for debugging without exposing sensitive data
- **Naming**: Clear, descriptive names for variables, functions, and classes
- **DRY**: Avoid code duplication; extract common patterns

### Security
- No hardcoded secrets or credentials
- Input validation on all external inputs
- Proper sanitization of data before logging

### Performance
- Avoid unnecessary I/O or API calls
- Use caching where appropriate
- Consider async/await for I/O-bound operations

### Testing
- Is the code testable? (Can dependencies be mocked?)
- Are edge cases considered?
- Is error handling tested?

### Review Checklist
- [ ] Type hints are complete and accurate
- [ ] Error handling is comprehensive
- [ ] Logging is appropriate (not too verbose, not too sparse)
- [ ] No security vulnerabilities (secrets, injection, etc.)
- [ ] Code follows project conventions (see Code Style section)
- [ ] Tests exist or are planned for new functionality
