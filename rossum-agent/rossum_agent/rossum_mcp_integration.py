"""MCP Tools Integration Module.

Provides functionality to connect to the rossum-mcp server and convert MCP tools
to Anthropic tool format for use with the Claude API.

MCPConnection supports optional change tracking: when write_tools is provided,
the connection intercepts write operations, caches read results, and tracks
entity changes for version control.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, cast

from anthropic.types import ToolParam
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from rossum_agent.change_tracking.commit_service import CommitService
from rossum_agent.change_tracking.models import EntityChange

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import redis
    from mcp.types import Tool as MCPTool

    from rossum_agent.api.models.schemas import MCPMode
    from rossum_agent.change_tracking.store import CommitStore, SnapshotStore

logger = logging.getLogger(__name__)

Operation: TypeAlias = Literal["create", "update", "delete"]  # noqa: UP040 - `type` keyword causes cyclic definition with `from __future__ import annotations`

_TRACKED_RESOURCES_KEY = "_tracked_resources"
_WRITE_PREFIXES = ("create_", "update_", "delete_", "patch_")
_READ_PREFIXES = ("get_", "list_")

_OPERATION_MAP: dict[str, Operation] = {
    "create_": "create",
    "update_": "update",
    "patch_": "update",
    "delete_": "delete",
}

# Tools that don't follow the standard prefix convention
_TOOL_OVERRIDES: dict[str, tuple[str, Operation]] = {
    "prune_schema_fields": ("schema", "update"),
    "create_queue_from_template": ("queue", "create"),
    "create_hook_from_template": ("hook", "create"),
}


def extract_entity_type(tool_name: str) -> str | None:
    """Extract entity type from tool name (e.g., 'update_queue' -> 'queue')."""
    if tool_name in _TOOL_OVERRIDES:
        return _TOOL_OVERRIDES[tool_name][0]
    for prefix in (*_WRITE_PREFIXES, *_READ_PREFIXES):
        if tool_name.startswith(prefix):
            return tool_name[len(prefix) :]
    return None


def extract_entity_id(entity_type: str, arguments: dict[str, Any]) -> str | None:
    """Extract entity ID from tool arguments (e.g., queue_id from update_queue args)."""
    id_key = f"{entity_type}_id"
    entity_id = arguments.get(id_key)
    if entity_id is not None:
        return str(entity_id)
    if "id" in arguments:
        return str(arguments["id"])
    return None


def to_dict(obj: Any) -> dict | None:
    """Convert MCP result to a plain dict. Handles Pydantic models, dataclasses, and dicts."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    return None


def unwrap(data: dict) -> dict:
    """Unwrap FastMCP's {"result": ...} wrapper if present."""
    inner = data.get("result")
    return inner if isinstance(inner, dict) else data


def extract_entity_name(data: dict | None) -> str:
    """Extract a human-readable name from entity data, unwrapping FastMCP wrapper."""
    if data is None:
        return ""
    source = unwrap(data)
    for key in ("name", "label", "title", "subject"):
        if source.get(key):
            return str(source[key])
    return ""


def classify_operation(tool_name: str) -> Operation:
    """Classify the operation type from tool name."""
    if tool_name in _TOOL_OVERRIDES:
        return _TOOL_OVERRIDES[tool_name][1]
    for prefix, operation in _OPERATION_MAP.items():
        if tool_name.startswith(prefix):
            return operation
    return "update"


def _pop_tracked_resources(result: Any) -> list[dict[str, Any]]:
    """Extract and remove _tracked_resources from a dict result.

    Returns the list of tracked resource entries, or an empty list if the
    result is not a dict or has no tracked resources.
    """
    if isinstance(result, dict):
        return result.pop(_TRACKED_RESOURCES_KEY, [])
    return []


@dataclass
class MCPConnection:
    """MCP client connection with optional change tracking.

    When write_tools is provided, the connection intercepts write operations,
    caches read results, and tracks entity changes for version control.
    """

    client: Client
    write_tools: set[str] = field(default_factory=set)
    chat_id: str | None = None
    redis_client: redis.Redis | None = None
    cache_ttl_seconds: int = 30 * 24 * 3600
    _tools: list[MCPTool] | None = field(default=None, init=False, repr=False)
    _read_cache: dict[tuple[str, str], dict] = field(default_factory=dict, init=False, repr=False)
    _changes: list[EntityChange] = field(default_factory=list, init=False, repr=False)
    _commit_store: CommitStore | None = field(default=None, init=False, repr=False)
    _snapshot_store: SnapshotStore | None = field(default=None, init=False, repr=False)
    _environment: str | None = field(default=None, init=False, repr=False)

    async def get_tools(self) -> list[MCPTool]:
        """Get the list of available MCP tools (cached)."""
        if self._tools is None:
            self._tools = await self.client.list_tools()
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call an MCP tool by name with the given arguments."""
        arguments = arguments or {}

        if name in self.write_tools:
            return await self._handle_write(name, arguments)

        result = await self._call_mcp(name, arguments)
        self._try_cache_read(name, arguments, result)
        return result

    async def _call_mcp(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute the raw MCP tool call and extract the result."""
        logger.info(f"Calling MCP tool {name}")

        result = await self.client.call_tool(name, arguments)
        # Prefer structured_content (raw dict) over data (parsed pydantic model)
        # because FastMCP's json_schema_to_type has a bug where nested dict fields
        # like config: dict[str, Any] become empty dataclasses, losing all data.
        if result.structured_content is not None:
            raw = result.structured_content
            # FastMCP sometimes wraps return values in {"result": ...}
            if isinstance(raw, dict):
                return unwrap(raw)
            return raw
        if result.data is not None:
            return result.data
        if result.content:
            text_parts = [str(block.text) for block in result.content if hasattr(block, "text") and block.text]
            if len(text_parts) == 1:
                return text_parts[0]
            return "\n".join(text_parts) if text_parts else None
        return None

    def _cache_get(self, entity_type: str, entity_id: str) -> dict | None:
        if self.redis_client and self.chat_id:
            raw = self.redis_client.get(f"read_cache:{self.chat_id}:{entity_type}:{entity_id}")
            if raw is not None:
                return json.loads(cast("bytes", raw))
            return None
        return self._read_cache.get((entity_type, entity_id))

    def _cache_set(self, entity_type: str, entity_id: str, data: dict) -> None:
        if self.redis_client and self.chat_id:
            key = f"read_cache:{self.chat_id}:{entity_type}:{entity_id}"
            self.redis_client.setex(key, self.cache_ttl_seconds, json.dumps(data, default=str))
        else:
            self._read_cache[(entity_type, entity_id)] = data

    async def _handle_write(self, name: str, arguments: dict[str, Any]) -> Any:
        # Handle unified delete tool: delete(entity="queue", entity_id=123)
        if name == "delete" and "entity" in arguments and "entity_id" in arguments:
            entity_type = arguments["entity"]
            entity_id = str(arguments["entity_id"])
            operation: Operation = "delete"
        else:
            entity_type = extract_entity_type(name)
            entity_id = extract_entity_id(entity_type or "", arguments) if entity_type else None
            operation = classify_operation(name)

        self._auto_commit_if_needed(entity_type, entity_id, operation)

        before = await self._get_before_snapshot(entity_type, entity_id, operation)
        result = await self._call_mcp(name, arguments)

        tracked = _pop_tracked_resources(result)

        after, entity_id = await self._get_after_snapshot(operation, entity_type, entity_id, result)

        if after is not None and entity_type and entity_id:
            self._cache_set(entity_type, entity_id, after)

        self._record_change(name, arguments, entity_type, entity_id, operation, before, after)
        self._record_tracked_resources(tracked, operation)
        return result

    def _record_tracked_resources(
        self,
        tracked: list[dict[str, Any]],
        operation: Operation,
    ) -> None:
        """Create EntityChange entries for side-effect resources reported by MCP tools."""
        for entry in tracked:
            et = entry.get("entity_type", "")
            eid = entry.get("entity_id", "")
            data = entry.get("data")
            if not (et and eid and isinstance(data, dict)):
                continue
            self._cache_set(et, eid, data)
            self._changes.append(
                EntityChange(
                    entity_type=et,
                    entity_id=eid,
                    entity_name=extract_entity_name(data),
                    operation=operation,
                    before=None,
                    after=data,
                )
            )
            logger.info(f"Tracked side-effect {operation} on {et}:{eid}")

    def _auto_commit_if_needed(
        self,
        entity_type: str | None,
        entity_id: str | None,
        operation: Operation,
    ) -> None:
        # Auto-commit when the same entity already has pending changes with a
        # *different* operation type (e.g. create→delete, create→update).
        # Same-type sequences (update→update like prune+patch) stay in one commit.
        if not (entity_type and entity_id and self._changes and self._commit_store):
            return
        if any(
            c.entity_type == entity_type and c.entity_id == entity_id and c.operation != operation
            for c in self._changes
        ):
            self.flush_and_commit("auto-flush before new request")

    async def _get_before_snapshot(
        self,
        entity_type: str | None,
        entity_id: str | None,
        operation: Operation,
    ) -> dict | None:
        if not (entity_type and entity_id):
            return None
        before = self._cache_get(entity_type, entity_id)
        if before is None and operation != "create":
            before = await self.fetch_snapshot(entity_type, entity_id)
            if before is not None:
                self._cache_set(entity_type, entity_id, before)
        return before

    async def _get_after_snapshot(
        self,
        operation: Operation,
        entity_type: str | None,
        entity_id: str | None,
        result: Any,
    ) -> tuple[dict | None, str | None]:
        if operation == "create":
            after = to_dict(result)
            if after is not None and entity_id is None and entity_type:
                source = unwrap(after)
                entity_id = str(source.get("id", source.get(f"{entity_type}_id", "")))
            return after, entity_id
        if operation == "delete":
            return None, entity_id
        if entity_type and entity_id:
            return await self.fetch_snapshot(entity_type, entity_id), entity_id
        return None, entity_id

    def _record_change(
        self,
        name: str,
        arguments: dict[str, Any],
        entity_type: str | None,
        entity_id: str | None,
        operation: Operation,
        before: dict | None,
        after: dict | None,
    ) -> None:
        if entity_type and entity_id:
            self._changes.append(
                EntityChange(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_name=extract_entity_name(before) or extract_entity_name(after),
                    operation=operation,
                    before=before,
                    after=after,
                )
            )
            logger.info(f"Tracked {operation} on {entity_type}:{entity_id}")
        else:
            logger.warning(f"Could not extract entity identity from {name}({arguments})")

    async def fetch_snapshot(self, entity_type: str, entity_id: str) -> dict | None:
        """Fetch current entity state via the unified get tool."""
        try:
            try:
                typed_id: int | str = int(entity_id)
            except ValueError:
                typed_id = entity_id
            result = await self._call_mcp("get", {"entity": entity_type, "entity_id": typed_id})
            as_dict = to_dict(result)
            if as_dict is not None:
                # Unwrap unified get response: {"entity": ..., "id": ..., "data": {...}}
                if "data" in as_dict:
                    data = as_dict["data"]
                    if isinstance(data, dict):
                        return data
                return as_dict
            logger.warning(
                "fetch_snapshot get(%s, %s): result is %s, not convertible to dict",
                entity_type,
                entity_id,
                type(result).__name__,
            )
        except Exception:
            logger.warning("fetch_snapshot get(%s, %s) failed", entity_type, entity_id, exc_info=True)
        return None

    def _try_cache_read(self, name: str, arguments: dict[str, Any], result: Any) -> None:
        """Cache a read result if it looks like a single-entity get."""
        as_dict = to_dict(result)
        if as_dict is None:
            return

        # Handle unified get tool: get(entity="queue", entity_id=123) → {"entity": "queue", "id": 123, "data": {...}}
        if name == "get" and "entity" in arguments and "entity_id" in arguments:
            entity_type = arguments["entity"]
            entity_id = str(arguments["entity_id"])
            data = as_dict.get("data", as_dict)
            if isinstance(data, dict):
                self._cache_set(entity_type, entity_id, data)
            return

        entity_type = extract_entity_type(name)
        if entity_type is None:
            return
        entity_id = extract_entity_id(entity_type, arguments)
        if entity_id is None and name.startswith("get_"):
            entity_id = str(as_dict.get("id", ""))
        if not entity_id:
            return
        self._cache_set(entity_type, entity_id, as_dict)

    def setup_change_tracking(
        self,
        write_tools: set[str],
        chat_id: str,
        environment: str,
        commit_store: CommitStore,
        snapshot_store: SnapshotStore,
    ) -> None:
        """Configure change tracking on this connection."""
        self.write_tools = write_tools
        self.chat_id = chat_id
        self.redis_client = commit_store.client
        self._commit_store = commit_store
        self._snapshot_store = snapshot_store
        self._environment = environment

    def flush_and_commit(self, user_request: str) -> None:
        """Commit pending changes to the store."""
        if not (self._commit_store and self._snapshot_store and self._environment and self._changes):
            return
        CommitService(self._commit_store, self._snapshot_store).create_commit(
            self, self.chat_id or "unknown", user_request, self._environment
        )

    def get_changes(self) -> list[EntityChange]:
        """Get the list of tracked changes."""
        return list(self._changes)

    def has_changes(self) -> bool:
        """Check if any writes were intercepted."""
        return bool(self._changes)

    def clear_changes(self) -> None:
        """Clear tracked changes (after committing)."""
        self._changes.clear()


def create_mcp_transport(
    rossum_api_token: str, rossum_api_base_url: str, mcp_mode: MCPMode = "read-only"
) -> StdioTransport:
    """Create a StdioTransport for the rossum-mcp server."""
    return StdioTransport(
        command="rossum-mcp",
        args=[],
        env={
            **os.environ,
            "ROSSUM_API_BASE_URL": rossum_api_base_url.rstrip("/"),
            "ROSSUM_API_TOKEN": rossum_api_token,
            "ROSSUM_MCP_MODE": mcp_mode,
        },
    )


@asynccontextmanager
async def connect_mcp_server(
    rossum_api_token: str, rossum_api_base_url: str, mcp_mode: MCPMode = "read-only"
) -> AsyncIterator[MCPConnection]:
    """Connect to the rossum-mcp server and yield an MCPConnection.

    This context manager handles the lifecycle of the MCP client connection.
    Tools are cached after the first retrieval for efficiency.
    """
    transport = create_mcp_transport(
        rossum_api_token=rossum_api_token, rossum_api_base_url=rossum_api_base_url, mcp_mode=mcp_mode
    )
    async with (client := Client(transport)):
        yield MCPConnection(client=client)


def mcp_tools_to_anthropic_format(mcp_tools: list[MCPTool]) -> list[ToolParam]:
    """Convert MCP tools to Anthropic tool format."""
    return [
        ToolParam(name=mcp_tool.name, description=mcp_tool.description or "", input_schema=mcp_tool.inputSchema)
        for mcp_tool in mcp_tools
    ]
