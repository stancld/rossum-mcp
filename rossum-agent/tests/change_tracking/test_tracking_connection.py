from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.change_tracking.commit_service import CommitService
from rossum_agent.change_tracking.models import EntityChange
from rossum_agent.rossum_mcp_integration import (
    MCPConnection,
    classify_operation,
    extract_entity_id,
    extract_entity_name,
    extract_entity_type,
    to_dict,
    unwrap,
)
from rossum_agent.tools.change_history import revert_commit
from rossum_agent.tools.core import AgentContext, set_context


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def write_tools():
    return {"create_queue", "update_queue", "delete_queue", "patch_queue"}


@pytest.fixture
def conn(mock_client, write_tools):
    c = MCPConnection(client=mock_client, write_tools=write_tools)
    c._call_mcp = AsyncMock()
    return c


class TestExtractEntityType:
    def test_write_prefixes(self):
        assert extract_entity_type("create_queue") == "queue"
        assert extract_entity_type("update_schema") == "schema"
        assert extract_entity_type("delete_hook") == "hook"
        assert extract_entity_type("patch_inbox") == "inbox"

    def test_read_prefixes(self):
        assert extract_entity_type("get_queue") == "queue"
        assert extract_entity_type("list_queues") == "queues"

    def test_overrides(self):
        assert extract_entity_type("prune_schema_fields") == "schema"
        assert extract_entity_type("create_queue_from_template") == "queue"
        assert extract_entity_type("create_hook_from_template") == "hook"

    def test_unknown_prefix(self):
        assert extract_entity_type("run_export") is None
        assert extract_entity_type("some_random_tool") is None


class TestExtractEntityId:
    def test_entity_type_id_key(self):
        assert extract_entity_id("queue", {"queue_id": 123}) == "123"

    def test_generic_id_key(self):
        assert extract_entity_id("queue", {"id": 456}) == "456"

    def test_prefers_entity_type_key(self):
        assert extract_entity_id("queue", {"queue_id": 123, "id": 456}) == "123"

    def test_no_id(self):
        assert extract_entity_id("queue", {"name": "test"}) is None


class TestToDict:
    def test_dict_passthrough(self):
        d = {"id": 1, "name": "test"}
        assert to_dict(d) is d

    def test_pydantic_model(self):
        from pydantic import BaseModel

        class FakeSchema(BaseModel):
            id: int
            name: str

        model = FakeSchema(id=1, name="test")
        result = to_dict(model)
        assert result == {"id": 1, "name": "test"}

    def test_dataclass(self):
        @dataclass
        class FakeEntity:
            id: int
            name: str

        obj = FakeEntity(id=1, name="test")
        result = to_dict(obj)
        assert result == {"id": 1, "name": "test"}

    def test_string_returns_none(self):
        assert to_dict("some string") is None

    def test_none_returns_none(self):
        assert to_dict(None) is None

    def test_list_returns_none(self):
        assert to_dict([1, 2, 3]) is None


class TestUnwrap:
    def test_unwraps_result_key(self):
        data = {"result": {"id": 1, "name": "Schema"}}
        assert unwrap(data) == {"id": 1, "name": "Schema"}

    def test_no_result_key(self):
        data = {"id": 1, "name": "Queue"}
        assert unwrap(data) == {"id": 1, "name": "Queue"}

    def test_result_key_non_dict(self):
        data = {"result": [1, 2, 3]}
        assert unwrap(data) == {"result": [1, 2, 3]}


class TestExtractEntityName:
    def test_name_field(self):
        assert extract_entity_name({"name": "My Queue"}) == "My Queue"

    def test_label_field(self):
        assert extract_entity_name({"label": "My Label"}) == "My Label"

    def test_title_field(self):
        assert extract_entity_name({"title": "My Title"}) == "My Title"

    def test_subject_field(self):
        assert extract_entity_name({"subject": "My Subject"}) == "My Subject"

    def test_none_data(self):
        assert extract_entity_name(None) == ""

    def test_no_name_fields(self):
        assert extract_entity_name({"id": 1, "url": "http://..."}) == ""

    def test_unwraps_fastmcp_result_wrapper(self):
        assert extract_entity_name({"result": {"id": 1, "name": "Wrapped Name"}}) == "Wrapped Name"

    def test_unwraps_with_label(self):
        assert extract_entity_name({"result": {"id": 1, "label": "Wrapped Label"}}) == "Wrapped Label"


class TestClassifyOperation:
    def test_create(self):
        assert classify_operation("create_queue") == "create"

    def test_update(self):
        assert classify_operation("update_queue") == "update"

    def test_patch(self):
        assert classify_operation("patch_queue") == "update"

    def test_delete(self):
        assert classify_operation("delete_queue") == "delete"

    def test_overrides(self):
        assert classify_operation("prune_schema_fields") == "update"
        assert classify_operation("create_queue_from_template") == "create"
        assert classify_operation("create_hook_from_template") == "create"

    def test_unknown(self):
        assert classify_operation("unknown_tool") == "update"


class TestGetTools:
    @pytest.mark.anyio
    async def test_delegates_to_client(self, mock_client, write_tools):
        mock_client.list_tools = AsyncMock(return_value=[])
        conn = MCPConnection(client=mock_client, write_tools=write_tools)
        result = await conn.get_tools()
        assert result == []
        mock_client.list_tools.assert_awaited_once()


class TestReadCaching:
    @pytest.mark.anyio
    async def test_caches_get_result(self, conn):
        conn._call_mcp = AsyncMock(return_value={"id": 1, "name": "Test Queue"})

        await conn.call_tool("get_queue", {"queue_id": "1"})

        assert ("queue", "1") in conn._read_cache
        assert conn._read_cache[("queue", "1")] == {"id": 1, "name": "Test Queue"}

    @pytest.mark.anyio
    async def test_caches_get_result_id_from_response(self, conn):
        conn._call_mcp = AsyncMock(return_value={"id": 42, "name": "Queue"})

        await conn.call_tool("get_queue", {})

        assert ("queue", "42") in conn._read_cache

    @pytest.mark.anyio
    async def test_caches_pydantic_model_result(self, conn):
        from pydantic import BaseModel

        class FakeSchema(BaseModel):
            id: int
            name: str
            content: list = []

        conn._call_mcp = AsyncMock(return_value=FakeSchema(id=1, name="Schema"))

        await conn.call_tool("get_queue", {"queue_id": "1"})

        assert ("queue", "1") in conn._read_cache
        assert conn._read_cache[("queue", "1")] == {"id": 1, "name": "Schema", "content": []}

    @pytest.mark.anyio
    async def test_caches_dataclass_result(self, conn):
        @dataclass
        class FakeEntity:
            id: int
            name: str

        conn._call_mcp = AsyncMock(return_value=FakeEntity(id=1, name="Entity"))

        await conn.call_tool("get_queue", {"queue_id": "1"})

        assert ("queue", "1") in conn._read_cache
        assert conn._read_cache[("queue", "1")] == {"id": 1, "name": "Entity"}

    @pytest.mark.anyio
    async def test_does_not_cache_non_dict_result(self, conn):
        conn._call_mcp = AsyncMock(return_value="some string")

        await conn.call_tool("get_queue", {"queue_id": "1"})

        assert len(conn._read_cache) == 0

    @pytest.mark.anyio
    async def test_does_not_cache_unknown_tool(self, conn):
        conn._call_mcp = AsyncMock(return_value={"id": 1})

        await conn.call_tool("run_export", {"queue_id": "1"})

        assert len(conn._read_cache) == 0


class TestWriteTracking:
    @pytest.mark.anyio
    async def test_creates_entity_change_on_update(self, conn):
        conn._read_cache[("queue", "1")] = {"id": 1, "name": "Before"}

        conn._call_mcp = AsyncMock(
            side_effect=[
                {"id": 1, "name": "Updated"},  # update_queue result
                {"id": 1, "name": "Updated"},  # get(entity="queue") after-snapshot
            ]
        )

        await conn.call_tool("update_queue", {"queue_id": "1", "name": "Updated"})

        assert len(conn._changes) == 1
        change = conn._changes[0]
        assert change.entity_type == "queue"
        assert change.entity_id == "1"
        assert change.operation == "update"
        assert change.before == {"id": 1, "name": "Before"}
        assert change.after == {"id": 1, "name": "Updated"}

    @pytest.mark.anyio
    async def test_create_extracts_id_from_result(self, conn):
        conn._call_mcp = AsyncMock(return_value={"id": 99, "name": "New Queue"})

        await conn.call_tool("create_queue", {"name": "New Queue"})

        assert len(conn._changes) == 1
        change = conn._changes[0]
        assert change.entity_type == "queue"
        assert change.entity_id == "99"
        assert change.operation == "create"
        assert change.before is None
        assert change.after == {"id": 99, "name": "New Queue"}

    @pytest.mark.anyio
    async def test_delete_has_after_none(self, conn):
        conn._read_cache[("queue", "5")] = {"id": 5, "name": "Doomed Queue"}
        conn._call_mcp = AsyncMock(return_value="deleted")

        await conn.call_tool("delete_queue", {"queue_id": "5"})

        assert len(conn._changes) == 1
        change = conn._changes[0]
        assert change.operation == "delete"
        assert change.before == {"id": 5, "name": "Doomed Queue"}
        assert change.after is None

    @pytest.mark.anyio
    async def test_update_fetches_after_snapshot(self, conn):
        conn._read_cache[("queue", "1")] = {"id": 1, "name": "Before"}
        conn._call_mcp = AsyncMock(
            side_effect=[
                "ok",  # update_queue result
                {"id": 1, "name": "After"},  # get(entity="queue") after-snapshot
            ]
        )

        await conn.call_tool("update_queue", {"queue_id": "1"})

        # Before is cached so only 2 calls: write + after-snapshot
        assert conn._call_mcp.call_count == 2
        after_call = conn._call_mcp.call_args_list[1]
        assert after_call.args[0] == "get"
        assert after_call.args[1] == {"entity": "queue", "entity_id": 1}

    @pytest.mark.anyio
    async def test_entity_name_from_before(self, conn):
        conn._read_cache[("queue", "1")] = {"id": 1, "name": "Original Name"}
        conn._call_mcp = AsyncMock(
            side_effect=[
                "ok",
                {"id": 1},  # after-snapshot without name
            ]
        )

        await conn.call_tool("update_queue", {"queue_id": "1"})

        assert conn._changes[0].entity_name == "Original Name"

    @pytest.mark.anyio
    async def test_entity_name_from_after(self, conn):
        conn._call_mcp = AsyncMock(return_value={"id": 10, "name": "Created"})

        await conn.call_tool("create_queue", {"name": "Created"})

        assert conn._changes[0].entity_name == "Created"

    @pytest.mark.anyio
    async def test_update_without_prior_read_fetches_before_snapshot(self, conn):
        """When the entity was never read, _handle_write proactively fetches a before snapshot."""
        conn._call_mcp = AsyncMock(
            side_effect=[
                {"id": 1, "name": "Before"},  # proactive get(entity="queue") before-snapshot
                "ok",  # update_queue result
                {"id": 1, "name": "After"},  # get(entity="queue") after-snapshot
            ]
        )

        await conn.call_tool("update_queue", {"queue_id": "1", "name": "After"})

        assert conn._call_mcp.call_count == 3
        before_call = conn._call_mcp.call_args_list[0]
        assert before_call.args == ("get", {"entity": "queue", "entity_id": 1})
        write_call = conn._call_mcp.call_args_list[1]
        assert write_call.args == ("update_queue", {"queue_id": "1", "name": "After"})

        assert len(conn._changes) == 1
        change = conn._changes[0]
        assert change.before == {"id": 1, "name": "Before"}
        assert change.after == {"id": 1, "name": "After"}
        # Cache reflects latest state (after-snapshot) for correct "before" in subsequent writes
        assert conn._read_cache[("queue", "1")] == {"id": 1, "name": "After"}

    @pytest.mark.anyio
    async def test_update_without_prior_read_fetches_pydantic_before(self, conn):
        """Proactive fetch returns Pydantic model — should still capture before."""
        from pydantic import BaseModel

        class FakeSchema(BaseModel):
            id: int
            name: str

        conn._call_mcp = AsyncMock(
            side_effect=[
                FakeSchema(id=1, name="Before"),  # proactive before-snapshot (Pydantic)
                "ok",  # update_queue result
                FakeSchema(id=1, name="After"),  # after-snapshot (Pydantic)
            ]
        )

        await conn.call_tool("update_queue", {"queue_id": "1"})

        change = conn._changes[0]
        assert change.before == {"id": 1, "name": "Before"}
        assert change.after == {"id": 1, "name": "After"}


class TestAutoCommitOnEntityConflict:
    """Tests that writes auto-commit when the same entity already has pending changes."""

    @pytest.fixture
    def committed_changes(self, conn):
        """Set up auto-commit tracking that captures flushed changes."""
        batches: list[list[EntityChange]] = []
        # Set _commit_store to a truthy sentinel so _auto_commit_if_needed proceeds
        conn._commit_store = object()  # type: ignore[assignment]

        def capture_flush(user_request: str) -> None:
            batches.append(conn.get_changes())
            conn.clear_changes()

        conn.flush_and_commit = capture_flush  # type: ignore[method-assign]
        return batches

    @pytest.mark.anyio
    async def test_create_then_delete_flushes(self, conn, committed_changes):
        """Create then delete same entity: callback flushes creates before delete is recorded."""
        conn._call_mcp = AsyncMock(return_value={"id": 5, "name": "My Queue"})
        await conn.call_tool("create_queue", {"name": "My Queue"})

        conn._call_mcp = AsyncMock(return_value="deleted")
        conn._read_cache[("queue", "5")] = {"id": 5, "name": "My Queue"}
        await conn.call_tool("delete_queue", {"queue_id": "5"})

        assert len(committed_changes) == 1
        assert committed_changes[0][0].operation == "create"
        assert committed_changes[0][0].entity_id == "5"
        assert len(conn._changes) == 1
        assert conn._changes[0].operation == "delete"

    @pytest.mark.anyio
    async def test_create_then_patch_flushes(self, conn, committed_changes):
        """Create then patch same entity: callback flushes create before patch is recorded."""
        conn._call_mcp = AsyncMock(return_value={"id": 7, "name": "My Hook"})
        await conn.call_tool("create_queue", {"name": "My Hook"})

        conn._call_mcp = AsyncMock(
            side_effect=[
                "ok",  # patch result
                {"id": 7, "name": "Patched Hook"},  # after-snapshot
            ]
        )
        await conn.call_tool("patch_queue", {"queue_id": "7", "name": "Patched Hook"})

        assert len(committed_changes) == 1
        assert committed_changes[0][0].operation == "create"
        assert committed_changes[0][0].entity_id == "7"
        assert len(conn._changes) == 1
        assert conn._changes[0].operation == "update"

    @pytest.mark.anyio
    async def test_create_then_update_flushes(self, conn, committed_changes):
        """Create then update same entity: callback flushes create before update is recorded."""
        conn._call_mcp = AsyncMock(return_value={"id": 3, "name": "Schema"})
        await conn.call_tool("create_queue", {"name": "Schema"})

        conn._call_mcp = AsyncMock(
            side_effect=[
                "ok",  # update result
                {"id": 3, "name": "Updated Schema"},  # after-snapshot
            ]
        )
        await conn.call_tool("update_queue", {"queue_id": "3", "name": "Updated Schema"})

        assert len(committed_changes) == 1
        assert committed_changes[0][0].operation == "create"
        assert len(conn._changes) == 1
        assert conn._changes[0].operation == "update"

    @pytest.mark.anyio
    async def test_different_entities_no_flush(self, conn, committed_changes):
        """Creating different entities does NOT trigger auto-commit."""
        conn._call_mcp = AsyncMock(return_value={"id": 1, "name": "Queue"})
        await conn.call_tool("create_queue", {"name": "Queue"})

        conn._call_mcp = AsyncMock(return_value="deleted")
        conn._read_cache[("queue", "99")] = {"id": 99, "name": "Other"}
        await conn.call_tool("delete_queue", {"queue_id": "99"})

        assert len(committed_changes) == 0
        assert len(conn._changes) == 2

    @pytest.mark.anyio
    async def test_no_pending_changes_skips_callback(self, conn, committed_changes):
        """Write with no pending changes does not call the callback."""
        conn._read_cache[("queue", "5")] = {"id": 5, "name": "Q"}
        conn._call_mcp = AsyncMock(return_value="deleted")

        await conn.call_tool("delete_queue", {"queue_id": "5"})

        assert len(committed_changes) == 0
        assert len(conn._changes) == 1

    @pytest.mark.anyio
    async def test_same_operation_type_no_flush(self, conn, committed_changes):
        """Two updates to same entity (e.g. prune+patch) stay in one commit."""
        conn._read_cache[("queue", "1")] = {"id": 1, "name": "Original"}
        conn._call_mcp = AsyncMock(
            side_effect=[
                "ok",  # first update result
                {"id": 1, "name": "Pruned"},  # after-snapshot
            ]
        )
        await conn.call_tool("update_queue", {"queue_id": "1", "name": "Pruned"})

        conn._call_mcp = AsyncMock(
            side_effect=[
                "ok",  # second update (patch) result
                {"id": 1, "name": "Patched"},  # after-snapshot
            ]
        )
        await conn.call_tool("patch_queue", {"queue_id": "1", "name": "Patched"})

        assert len(committed_changes) == 0
        assert len(conn._changes) == 2
        assert conn._changes[0].operation == "update"
        assert conn._changes[1].operation == "update"

    @pytest.mark.anyio
    async def test_without_callback_works_normally(self, conn):
        """Without a commit callback, writes behave as before."""
        conn._call_mcp = AsyncMock(return_value={"id": 5, "name": "Q"})
        await conn.call_tool("create_queue", {"name": "Q"})

        conn._call_mcp = AsyncMock(return_value="deleted")
        conn._read_cache[("queue", "5")] = {"id": 5, "name": "Q"}
        await conn.call_tool("delete_queue", {"queue_id": "5"})

        assert len(conn._changes) == 2


class TestRuleTracking:
    """Tests that rule tools are tracked correctly (standard prefix convention)."""

    @pytest.fixture
    def rule_conn(self, mock_client):
        write_tools = {"create_rule", "patch_rule", "delete_rule"}
        c = MCPConnection(client=mock_client, write_tools=write_tools)
        c._call_mcp = AsyncMock()
        return c

    @pytest.mark.anyio
    async def test_create_rule_tracked(self, rule_conn):
        rule_data = {"id": 42, "name": "Amount check", "actions": []}
        rule_conn._call_mcp = AsyncMock(return_value=rule_data)

        await rule_conn.call_tool("create_rule", {"name": "Amount check"})

        assert len(rule_conn._changes) == 1
        change = rule_conn._changes[0]
        assert change.entity_type == "rule"
        assert change.entity_id == "42"
        assert change.operation == "create"
        assert change.before is None
        assert change.after == rule_data

    @pytest.mark.anyio
    async def test_delete_rule_tracked(self, rule_conn):
        rule_conn._read_cache[("rule", "42")] = {"id": 42, "name": "Amount check"}
        rule_conn._call_mcp = AsyncMock(return_value="deleted")

        await rule_conn.call_tool("delete_rule", {"rule_id": "42"})

        assert len(rule_conn._changes) == 1
        change = rule_conn._changes[0]
        assert change.entity_type == "rule"
        assert change.entity_id == "42"
        assert change.operation == "delete"
        assert change.before == {"id": 42, "name": "Amount check"}
        assert change.after is None

    @pytest.mark.anyio
    async def test_patch_rule_tracked(self, rule_conn):
        original = {"id": 42, "name": "Amount check", "actions": []}
        patched = {"id": 42, "name": "Amount check", "actions": [{"type": "error"}]}
        rule_conn._read_cache[("rule", "42")] = original
        rule_conn._call_mcp = AsyncMock(
            side_effect=[
                "ok",  # patch result
                patched,  # after-snapshot
            ]
        )

        await rule_conn.call_tool("patch_rule", {"rule_id": "42", "actions": [{"type": "error"}]})

        assert len(rule_conn._changes) == 1
        change = rule_conn._changes[0]
        assert change.entity_type == "rule"
        assert change.operation == "update"
        assert change.before == original
        assert change.after == patched

    @pytest.mark.anyio
    async def test_create_then_delete_rule_auto_commits(self, rule_conn):
        """Create + delete same rule triggers auto-commit when callback is set."""
        committed: list[list[EntityChange]] = []
        rule_conn._commit_store = object()  # type: ignore[assignment]

        def capture_flush(user_request: str) -> None:
            committed.append(rule_conn.get_changes())
            rule_conn.clear_changes()

        rule_conn.flush_and_commit = capture_flush  # type: ignore[method-assign]

        rule_conn._call_mcp = AsyncMock(return_value={"id": 10, "name": "Rule"})
        await rule_conn.call_tool("create_rule", {"name": "Rule"})

        rule_conn._read_cache[("rule", "10")] = {"id": 10, "name": "Rule"}
        rule_conn._call_mcp = AsyncMock(return_value="deleted")
        await rule_conn.call_tool("delete_rule", {"rule_id": "10"})

        assert len(committed) == 1
        assert committed[0][0].operation == "create"
        assert rule_conn._changes[0].operation == "delete"


class TestOverrideToolTracking:
    """Tests for non-standard tool names that use _TOOL_OVERRIDES."""

    @pytest.mark.anyio
    async def test_prune_schema_fields_tracked_as_schema_update(self):
        write_tools = {"prune_schema_fields", "patch_schema"}
        conn = MCPConnection(client=AsyncMock(), write_tools=write_tools)

        original = {"id": 100, "name": "Invoice", "content": [{"id": "field1"}]}
        pruned = {"id": 100, "name": "Invoice", "content": []}

        conn._call_mcp = AsyncMock(
            side_effect=[
                original,  # get(entity="schema") before-snapshot
                {"status": "ok"},  # prune result
                pruned,  # get(entity="schema") after-snapshot
            ]
        )

        await conn.call_tool("prune_schema_fields", {"schema_id": 100, "fields_to_keep": []})

        assert len(conn._changes) == 1
        change = conn._changes[0]
        assert change.entity_type == "schema"
        assert change.entity_id == "100"
        assert change.operation == "update"
        assert change.before == original
        assert change.after == pruned

    @pytest.mark.anyio
    async def test_prune_then_patch_captures_correct_before_after(self):
        """Prune then patch: second write should use post-prune state as before."""
        write_tools = {"prune_schema_fields", "patch_schema"}
        conn = MCPConnection(client=AsyncMock(), write_tools=write_tools)

        original = {"id": 100, "name": "Invoice", "content": [{"id": "field1"}]}
        pruned = {"id": 100, "name": "Invoice", "content": []}
        patched = {"id": 100, "name": "Invoice", "content": [{"id": "formula1"}]}

        conn._call_mcp = AsyncMock(
            side_effect=[
                original,  # get(entity="schema") before prune
                {"status": "ok"},  # prune result
                pruned,  # get(entity="schema") after prune
                {"status": "ok"},  # patch result
                patched,  # get(entity="schema") after patch
            ]
        )

        await conn.call_tool("prune_schema_fields", {"schema_id": 100, "fields_to_keep": []})
        await conn.call_tool("patch_schema", {"schema_id": 100, "operation": "add", "node_data": {}})

        assert len(conn._changes) == 2
        assert conn._changes[0].before == original
        assert conn._changes[0].after == pruned
        assert conn._changes[1].before == pruned
        assert conn._changes[1].after == patched

    @pytest.mark.anyio
    async def test_create_queue_from_template_tracked_as_queue_create(self):
        write_tools = {"create_queue_from_template"}
        conn = MCPConnection(client=AsyncMock(), write_tools=write_tools)
        conn._call_mcp = AsyncMock(return_value={"id": 42, "name": "Test Queue"})

        await conn.call_tool("create_queue_from_template", {"template_name": "EU Invoice", "workspace_id": 1})

        assert len(conn._changes) == 1
        change = conn._changes[0]
        assert change.entity_type == "queue"
        assert change.entity_id == "42"
        assert change.operation == "create"
        assert change.before is None
        assert change.after == {"id": 42, "name": "Test Queue"}


class TestSubAgentSchemaFlow:
    """End-to-end test simulating the schema patching sub-agent flow."""

    @pytest.fixture
    def schema_conn(self, mock_client):
        write_tools = {"update_schema", "delete_schema", "patch_schema"}
        c = MCPConnection(client=mock_client, write_tools=write_tools)
        c._call_mcp = AsyncMock()
        return c

    @pytest.mark.anyio
    async def test_read_then_update_captures_before(self, schema_conn):
        """Simulates: get (read) → update_schema (write). Before must be captured."""
        original = {"result": {"id": 100, "name": "My Schema", "content": [{"id": "section", "category": "section"}]}}
        updated = {"result": {"id": 100, "name": "My Schema", "content": []}}

        schema_conn._call_mcp = AsyncMock(
            side_effect=[
                original,  # get (read)
                "ok",  # update_schema (write)
                updated,  # get(entity="schema") after-snapshot
            ]
        )

        # Sub-agent step 1: read schema via unified get tool
        await schema_conn.call_tool("get", {"entity": "schema", "entity_id": 100})

        # Sub-agent step 2: update schema
        await schema_conn.call_tool("update_schema", {"schema_id": 100, "schema_data": {"content": []}})

        assert len(schema_conn._changes) == 1
        change = schema_conn._changes[0]
        assert change.before == original
        assert change.after == updated
        assert change.entity_name == "My Schema"

    @pytest.mark.anyio
    async def test_read_then_update_pydantic_captures_before(self, schema_conn):
        """Same flow but MCP returns Pydantic models instead of dicts."""
        from pydantic import BaseModel

        class FakeSchema(BaseModel):
            id: int
            name: str
            content: list = []

        original_model = FakeSchema(id=100, name="My Schema", content=[{"id": "s"}])
        updated_model = FakeSchema(id=100, name="My Schema", content=[])

        schema_conn._call_mcp = AsyncMock(
            side_effect=[
                original_model,  # get (read) — Pydantic model
                "ok",  # update_schema (write)
                updated_model,  # get(entity="schema") after-snapshot — Pydantic model
            ]
        )

        await schema_conn.call_tool("get", {"entity": "schema", "entity_id": 100})
        await schema_conn.call_tool("update_schema", {"schema_id": 100, "schema_data": {"content": []}})

        assert len(schema_conn._changes) == 1
        change = schema_conn._changes[0]
        assert change.before is not None, "before must NOT be None"
        assert change.before == {"id": 100, "name": "My Schema", "content": [{"id": "s"}]}
        assert change.after == {"id": 100, "name": "My Schema", "content": []}
        assert change.entity_name == "My Schema"


class TestNonEntityPassthrough:
    @pytest.mark.anyio
    async def test_non_write_tool_passes_through(self, conn):
        conn._call_mcp = AsyncMock(return_value="result")

        result = await conn.call_tool("run_export", {"format": "csv"})

        assert result == "result"
        assert not conn.has_changes()


class TestChangeManagement:
    def test_has_changes_initially_false(self, conn):
        assert not conn.has_changes()

    @pytest.mark.anyio
    async def test_has_changes_true_after_write(self, conn):
        conn._call_mcp = AsyncMock(return_value={"id": 1, "name": "Q"})

        await conn.call_tool("create_queue", {"name": "Q"})

        assert conn.has_changes()

    def test_get_changes_returns_copy(self, conn):
        conn._changes.append(
            EntityChange(
                entity_type="queue",
                entity_id="1",
                entity_name="Q",
                operation="create",
                before=None,
                after={"id": 1},
            )
        )
        changes = conn.get_changes()
        changes.clear()
        assert conn.has_changes()

    def test_clear_changes(self, conn):
        conn._changes.append(
            EntityChange(
                entity_type="queue",
                entity_id="1",
                entity_name="Q",
                operation="create",
                before=None,
                after={"id": 1},
            )
        )
        conn.clear_changes()
        assert not conn.has_changes()


class TestRedisCacheHelpers:
    """Tests for _cache_get/_cache_set with a mock Redis client."""

    @pytest.fixture
    def mock_redis(self):
        """In-memory dict-backed mock Redis client."""
        store: dict[str, bytes] = {}
        client = MagicMock()
        client.get = MagicMock(side_effect=lambda k: store.get(k))
        client.setex = MagicMock(
            side_effect=lambda k, ttl, v: store.__setitem__(
                k, v if isinstance(v, bytes) else v.encode("utf-8") if isinstance(v, str) else v
            )
        )
        return client

    @pytest.fixture
    def redis_conn(self, mock_client, write_tools, mock_redis):
        c = MCPConnection(
            client=mock_client,
            write_tools=write_tools,
            chat_id="test-chat-123",
            redis_client=mock_redis,
        )
        c._call_mcp = AsyncMock()
        return c

    def test_cache_set_and_get_roundtrip(self, redis_conn):
        data = {"id": 1, "name": "Queue"}
        redis_conn._cache_set("queue", "1", data)

        result = redis_conn._cache_get("queue", "1")
        assert result == data

    def test_cache_get_returns_none_for_missing_key(self, redis_conn):
        assert redis_conn._cache_get("queue", "999") is None

    def test_cache_set_writes_to_redis_only_when_redis_available(self, redis_conn, mock_redis):
        data = {"id": 2, "name": "Schema"}
        redis_conn._cache_set("schema", "2", data)

        # In-memory is NOT populated when Redis is available
        assert ("schema", "2") not in redis_conn._read_cache
        # Redis received a setex call
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "read_cache:test-chat-123:schema:2"
        assert call_args[0][1] == 30 * 24 * 3600

    def test_cache_get_prefers_redis(self, redis_conn, mock_redis):
        """When Redis has data, _cache_get returns it even if in-memory is empty."""
        redis_data = {"id": 1, "name": "From Redis"}
        key = "read_cache:test-chat-123:queue:1"
        mock_redis.get.side_effect = lambda k: json.dumps(redis_data).encode() if k == key else None

        result = redis_conn._cache_get("queue", "1")
        assert result == redis_data
        assert ("queue", "1") not in redis_conn._read_cache

    def test_fallback_to_memory_without_redis(self, mock_client, write_tools):
        """Without redis_client, behaves like the original in-memory cache."""
        conn = MCPConnection(client=mock_client, write_tools=write_tools)
        conn._cache_set("queue", "1", {"id": 1})
        assert conn._cache_get("queue", "1") == {"id": 1}

    def test_fallback_to_memory_without_chat_id(self, mock_client, write_tools, mock_redis):
        """With redis_client but no chat_id, falls back to in-memory."""
        conn = MCPConnection(client=mock_client, write_tools=write_tools, redis_client=mock_redis)
        conn._cache_set("queue", "1", {"id": 1})
        assert conn._cache_get("queue", "1") == {"id": 1}
        mock_redis.setex.assert_not_called()
        mock_redis.get.assert_not_called()

    @pytest.mark.anyio
    async def test_read_caches_to_redis(self, redis_conn, mock_redis):
        """A read tool call stores its result in Redis."""
        redis_conn._call_mcp = AsyncMock(return_value={"id": 5, "name": "Cached"})

        await redis_conn.call_tool("get_queue", {"queue_id": "5"})

        mock_redis.setex.assert_called_once()
        key = mock_redis.setex.call_args[0][0]
        assert key == "read_cache:test-chat-123:queue:5"

    @pytest.mark.anyio
    async def test_proactive_fetch_stores_to_redis(self, redis_conn, mock_redis):
        """When a write triggers a proactive before-fetch, it stores to Redis."""
        redis_conn._call_mcp = AsyncMock(
            side_effect=[
                {"id": 1, "name": "Before"},  # proactive get(entity="queue") before-snapshot
                "ok",  # update result
                {"id": 1, "name": "After"},  # get(entity="queue") after-snapshot
            ]
        )

        await redis_conn.call_tool("update_queue", {"queue_id": "1"})

        # The proactive fetch should have stored to Redis
        redis_keys = [call[0][0] for call in mock_redis.setex.call_args_list]
        assert "read_cache:test-chat-123:queue:1" in redis_keys

    @pytest.mark.anyio
    async def test_write_uses_redis_cached_before(self, redis_conn, mock_redis):
        """A write reads the before-snapshot from Redis when not in local memory."""
        before_data = {"id": 3, "name": "Cached Before"}
        redis_key = "read_cache:test-chat-123:queue:3"
        mock_redis.get.side_effect = lambda k: json.dumps(before_data).encode() if k == redis_key else None

        redis_conn._call_mcp = AsyncMock(
            side_effect=[
                "ok",  # update result
                {"id": 3, "name": "After"},  # after-snapshot
            ]
        )

        await redis_conn.call_tool("update_queue", {"queue_id": "3"})

        # Should NOT have made a proactive fetch — only write + after-snapshot
        assert redis_conn._call_mcp.call_count == 2
        change = redis_conn._changes[0]
        assert change.before == before_data
        assert change.after == {"id": 3, "name": "After"}


class TestSchemaRewriteAndRevert:
    """End-to-end: rewrite schema content to [], verify before-state persisted, revert."""

    @pytest.fixture
    def schema_conn(self, mock_client):
        write_tools = {"update_schema"}
        c = MCPConnection(client=mock_client, write_tools=write_tools)
        c._call_mcp = AsyncMock()
        return c

    @pytest.mark.anyio
    @pytest.mark.parametrize("with_prior_read", [True, False], ids=["with_get_schema", "without_get_schema"])
    async def test_rewrite_to_empty_persists_before_and_reverts(self, schema_conn, with_prior_read):
        original = {
            "id": 100,
            "name": "Invoice Schema",
            "content": [{"id": "invoice_id", "category": "datapoint", "label": "Invoice ID"}],
        }
        empty = {"id": 100, "name": "Invoice Schema", "content": []}

        # 1. Optionally read schema first (populates cache)
        if with_prior_read:
            schema_conn._call_mcp.return_value = original
            await schema_conn.call_tool("get", {"entity": "schema", "entity_id": 100})
            assert schema_conn._read_cache[("schema", "100")] == original

        # 2. Rewrite schema content to []
        #    Without prior read, _handle_write proactively fetches a before-snapshot
        if with_prior_read:
            schema_conn._call_mcp = AsyncMock(
                side_effect=[
                    "ok",  # update_schema result
                    empty,  # get(entity="schema") after-snapshot
                ]
            )
        else:
            schema_conn._call_mcp = AsyncMock(
                side_effect=[
                    original,  # proactive get(entity="schema") before-snapshot
                    "ok",  # update_schema result
                    empty,  # get(entity="schema") after-snapshot
                ]
            )
        await schema_conn.call_tool("update_schema", {"schema_id": 100, "content": []})

        # 3. Verify initial state was persisted in the tracked change
        changes = schema_conn.get_changes()
        assert len(changes) == 1
        change = changes[0]
        assert change.entity_type == "schema"
        assert change.entity_id == "100"
        assert change.operation == "update"
        assert change.before == original
        assert change.after == empty
        assert change.entity_name == "Invoice Schema"

        # 4. Create commit from tracked changes
        mock_store = MagicMock()
        mock_store.get_latest_hash.return_value = None
        commit_service = CommitService(store=mock_store, snapshot_store=MagicMock())
        with patch(
            "rossum_agent.change_tracking.commit_service.generate_commit_message",
            return_value="Clear Invoice Schema content",
        ):
            commit = commit_service.create_commit(
                tracking_connection=schema_conn,
                chat_id="test-chat",
                user_request="Clear all fields from Invoice Schema",
                environment="https://api.elis.rossum.ai/v1",
            )

        assert commit is not None
        assert len(commit.changes) == 1
        assert commit.changes[0].before == original
        mock_store.save_commit.assert_called_once_with(commit)
        assert not schema_conn.has_changes()  # cleared after commit

        # 5. Revert the commit
        mock_store.get_commit.return_value = commit

        mock_http_client = MagicMock()
        mock_http_client.update = AsyncMock()
        mock_http_client.request_json = AsyncMock(return_value={"content": []})
        mock_api_client = MagicMock()
        mock_api_client._http_client = mock_http_client

        revert_loop = asyncio.new_event_loop()
        thread = threading.Thread(target=revert_loop.run_forever)
        thread.start()

        set_context(
            AgentContext(
                commit_store=mock_store,
                rossum_environment="https://api.elis.rossum.ai/v1",
                rossum_credentials=("https://api.elis.rossum.ai/v1", "test-token"),
                mcp_event_loop=revert_loop,
            )
        )
        try:
            with patch("rossum_agent.tools.change_history.AsyncRossumAPIClient", return_value=mock_api_client):
                result = json.loads(revert_commit(commit_hash=commit.hash))
        finally:
            set_context(AgentContext())
            revert_loop.call_soon_threadsafe(revert_loop.stop)
            thread.join()
            revert_loop.close()

        assert result["status"] == "completed"
        assert len(result["executed"]) == 1
        assert result["executed"][0]["entity_type"] == "schema"
        assert result["executed"][0]["entity_id"] == "100"
        assert "remaining_actions" not in result

        # Verify the API was called to restore the original schema
        mock_http_client.update.assert_called_once()
        restored_data = mock_http_client.update.call_args.args[2]
        assert restored_data["content"] == original["content"]
