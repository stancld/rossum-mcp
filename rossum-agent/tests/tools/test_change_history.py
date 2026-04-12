"""Tests for rossum_agent.tools.change_history module."""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from rossum_agent.change_tracking.models import ConfigCommit, EntityChange
from rossum_agent.rossum_mcp_integration.tools import unwrap
from rossum_agent.tools.change_history import (
    _collapsed_operation,
    _compute_revert_patch,
    _deduplicate_changes,
    _flush_pending_changes,
    _revert_schema_with_retry,
    _unwrap_snapshot,
    diff_objects,
    restore_entity_version,
    revert_commit,
    show_change_history,
    show_commit_details,
    show_entity_history,
)
from rossum_agent.tools.core import AgentContext, set_context
from rossum_api import APIClientError


def _ec(
    entity_type: str,
    entity_id: str,
    entity_name: str,
    operation: str,
    before: dict | None,
    after: dict | None,
) -> EntityChange:
    return EntityChange(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        operation=operation,
        before=before,
        after=after,
    )


def _make_commit(
    hash: str = "abc123",
    parent: str | None = None,
    message: str = "Updated queue settings",
    user_request: str = "Change queue timeout",
    changes: list[EntityChange] | None = None,
) -> ConfigCommit:
    return ConfigCommit(
        hash=hash,
        parent=parent,
        chat_id="chat_1",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        message=message,
        user_request=user_request,
        environment="https://api.elis.rossum.ai/v1",
        changes=changes or [],
    )


class TestShowChangeHistory:
    """Tests for the show_change_history tool."""

    def test_no_store(self) -> None:
        set_context(AgentContext(commit_store=None, rossum_environment=None))
        try:
            result = json.loads(show_change_history())
            assert result["error"] == "Change tracking not available"
        finally:
            set_context(AgentContext())

    def test_empty(self) -> None:
        store = MagicMock()
        store.list_commits.return_value = []
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            result = json.loads(show_change_history())
            assert result["message"] == "No configuration changes recorded"
        finally:
            set_context(AgentContext())

    def test_with_commits(self) -> None:
        store = MagicMock()
        store.list_commits.return_value = [
            _make_commit(changes=[_ec("queue", "123", "My Queue", "update", {"timeout": 60}, {"timeout": 120})])
        ]
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            result = json.loads(show_change_history())
            assert len(result) == 1
            assert result[0]["hash"] == "abc123"
            assert result[0]["message"] == "Updated queue settings"
            assert result[0]["changes"] == 1
            assert result[0]["user_request"] == "Change queue timeout"
            assert result[0]["reverted"] is False
            store.list_commits.assert_called_once_with("https://api.elis.rossum.ai/v1", limit=10)
        finally:
            set_context(AgentContext())

    def test_reverted_commit_shows_reverted_true(self) -> None:
        store = MagicMock()
        commit = _make_commit(changes=[_ec("queue", "123", "My Queue", "update", {"timeout": 60}, {"timeout": 120})])
        commit.reverted = True
        store.list_commits.return_value = [commit]
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            result = json.loads(show_change_history())
            assert result[0]["reverted"] is True
        finally:
            set_context(AgentContext())


class TestShowCommitDetails:
    """Tests for the show_commit_details tool."""

    def test_found(self) -> None:
        store = MagicMock()
        store.get_commit.return_value = _make_commit(
            parent="parent_hash",
            changes=[_ec("queue", "123", "My Queue", "update", {"timeout": 60}, {"timeout": 120})],
        )
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            result = json.loads(show_commit_details(commit_hash="abc123"))
            assert result["hash"] == "abc123"
            assert result["parent"] == "parent_hash"
            assert len(result["changes"]) == 1
            assert result["changes"][0]["entity_type"] == "queue"
            assert result["changes"][0]["before"] == {"timeout": 60}
            assert result["changes"][0]["after"] == {"timeout": 120}
        finally:
            set_context(AgentContext())

    def test_not_found(self) -> None:
        store = MagicMock()
        store.get_commit.return_value = None
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            result = json.loads(show_commit_details(commit_hash="nonexistent"))
            assert "error" in result
            assert "nonexistent" in result["error"]
        finally:
            set_context(AgentContext())


class TestRevertCommit:
    """Tests for the revert_commit tool."""

    def test_commit_not_found(self) -> None:
        store = MagicMock()
        store.get_commit.return_value = None
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            result = json.loads(revert_commit(commit_hash="nonexistent"))
            assert "error" in result
            assert "not found" in result["error"].lower()
        finally:
            set_context(AgentContext())

    def test_calls_mark_reverted_after_revert(self) -> None:
        store = MagicMock()
        store.get_commit.return_value = _make_commit(
            changes=[_ec("queue", "123", "My Queue", "update", {"timeout": 60}, {"timeout": 120})]
        )
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            revert_commit(commit_hash="abc123")
            store.mark_reverted.assert_called_once_with("https://api.elis.rossum.ai/v1", "abc123")
        finally:
            set_context(AgentContext())

    def test_mark_reverted_not_called_when_commit_not_found(self) -> None:
        store = MagicMock()
        store.get_commit.return_value = None
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            revert_commit(commit_hash="nonexistent")
            store.mark_reverted.assert_not_called()
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_direct_revert_queue_create(self, mock_client_cls: MagicMock) -> None:
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()

        mock_client_instance = MagicMock()
        mock_client_instance.delete_queue = AsyncMock()
        mock_client_cls.return_value = mock_client_instance

        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[_ec("queue", "123", "My Queue", "create", None, {"name": "My Queue"})]
        )
        set_context(
            AgentContext(
                commit_store=store,
                rossum_environment="https://api.elis.rossum.ai/v1",
                rossum_credentials=("https://api.elis.rossum.ai/v1", "test-token"),
                mcp_event_loop=loop,
            )
        )

        try:
            result = json.loads(revert_commit(commit_hash="abc123"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()
            set_context(AgentContext())

        assert result["status"] == "completed"
        assert len(result["executed"]) == 1
        assert result["executed"][0]["status"] == "deleted"
        assert result["executed"][0]["entity_id"] == "123"
        assert "remaining_actions" not in result
        mock_client_instance.delete_queue.assert_called_once_with(123)

    def test_plan_for_update(self) -> None:
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[_ec("queue", "123", "My Queue", "update", {"timeout": 60}, {"timeout": 120})]
        )
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            result = json.loads(revert_commit(commit_hash="abc123"))
            assert result["status"] == "partial"
            assert len(result["remaining_actions"]) == 1
            assert result["remaining_actions"][0]["action"] == "restore"
            assert result["remaining_actions"][0]["tool"] == "update_queue"
            assert result["remaining_actions"][0]["restore_to"] == {"timeout": 60}
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_direct_revert_hook_delete(self, mock_client_cls: MagicMock) -> None:
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()

        mock_result = MagicMock()
        mock_result.id = 999
        mock_client_instance = MagicMock()
        mock_client_instance.create_new_hook = AsyncMock(return_value=mock_result)
        mock_client_cls.return_value = mock_client_instance

        before_hook = {
            "id": 789,
            "url": "https://api.elis.rossum.ai/v1/hooks/789",
            "name": "My Hook",
            "active": True,
            "config": {"url": "https://example.com"},
        }
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[_ec("hook", "789", "My Hook", "delete", before_hook, None)]
        )
        set_context(
            AgentContext(
                commit_store=store,
                rossum_environment="https://api.elis.rossum.ai/v1",
                rossum_credentials=("https://api.elis.rossum.ai/v1", "test-token"),
                mcp_event_loop=loop,
            )
        )

        try:
            result = json.loads(revert_commit(commit_hash="abc123"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()
            set_context(AgentContext())

        assert result["status"] == "completed"
        assert len(result["executed"]) == 1
        assert result["executed"][0]["status"] == "recreated"
        assert result["executed"][0]["entity_id"] == "789"
        assert result["executed"][0]["new_entity_id"] == "999"
        assert "remaining_actions" not in result
        # Verify read-only fields were stripped
        call_data = mock_client_instance.create_new_hook.call_args.args[0]
        assert "id" not in call_data
        assert "url" not in call_data
        assert call_data["name"] == "My Hook"
        assert call_data["active"] is True

    def test_plan_for_inbox_create(self) -> None:
        """Inbox create falls back to plan -- no delete_inbox SDK method."""
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[_ec("inbox", "55", "My Inbox", "create", None, {"name": "My Inbox"})]
        )
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            result = json.loads(revert_commit(commit_hash="abc123"))
            assert result["status"] == "partial"
            assert len(result["remaining_actions"]) == 1
            assert result["remaining_actions"][0]["action"] == "delete"
            assert result["remaining_actions"][0]["tool"] == "delete_inbox"
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_direct_revert_schema_update(self, mock_client_cls: MagicMock) -> None:
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()

        mock_http_client = MagicMock()
        mock_http_client.update = AsyncMock()
        mock_http_client.request_json = AsyncMock(
            return_value={"content": [{"category": "datapoint"}, {"category": "new"}]}
        )
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_cls.return_value = mock_client_instance

        before_schema = {"name": "Invoice", "content": [{"category": "datapoint"}]}
        after_schema = {"name": "Invoice", "content": [{"category": "datapoint"}, {"category": "new"}]}
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[_ec("schema", "456", "Invoice", "update", before_schema, after_schema)]
        )
        set_context(
            AgentContext(
                commit_store=store,
                rossum_environment="https://api.elis.rossum.ai/v1",
                rossum_credentials=("https://api.elis.rossum.ai/v1", "test-token"),
                mcp_event_loop=loop,
            )
        )

        try:
            result = json.loads(revert_commit(commit_hash="abc123"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()
            set_context(AgentContext())

        assert result["status"] == "completed"
        assert len(result["executed"]) == 1
        assert result["executed"][0]["entity_type"] == "schema"
        assert result["executed"][0]["entity_id"] == "456"
        assert "remaining_actions" not in result
        mock_http_client.request_json.assert_called_once_with("GET", "schemas/456")
        mock_http_client.update.assert_called_once()
        # Only content should be sent, not the full snapshot with read-only fields
        call_args = mock_http_client.update.call_args
        restored_data = call_args.args[2]
        assert list(restored_data.keys()) == ["content"]
        assert restored_data["content"] == [{"category": "datapoint"}]

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_direct_revert_hook_update(self, mock_client_cls: MagicMock) -> None:
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()

        mock_http_client = MagicMock()
        mock_http_client.update = AsyncMock()
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_cls.return_value = mock_client_instance

        before_hook = {"id": 789, "name": "My Hook", "active": True, "config": {"url": "https://old.example.com"}}
        after_hook = {"id": 789, "name": "My Hook", "active": False, "config": {"url": "https://new.example.com"}}
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[_ec("hook", "789", "My Hook", "update", before_hook, after_hook)]
        )
        set_context(
            AgentContext(
                commit_store=store,
                rossum_environment="https://api.elis.rossum.ai/v1",
                rossum_credentials=("https://api.elis.rossum.ai/v1", "test-token"),
                mcp_event_loop=loop,
            )
        )

        try:
            result = json.loads(revert_commit(commit_hash="abc123"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()
            set_context(AgentContext())

        assert result["status"] == "completed"
        assert len(result["executed"]) == 1
        assert result["executed"][0]["entity_type"] == "hook"
        assert result["executed"][0]["entity_id"] == "789"
        assert "remaining_actions" not in result
        mock_http_client.update.assert_called_once()
        # Should only patch changed fields (active, config), not read-only (id)
        call_args = mock_http_client.update.call_args
        restored_data = call_args.args[2]
        assert "id" not in restored_data
        assert restored_data["active"] is True
        assert restored_data["config"] == {"url": "https://old.example.com"}
        # name didn't change, so it shouldn't be in the patch
        assert "name" not in restored_data


class TestFlushPendingChanges:
    """Tests for the _flush_pending_changes helper."""

    def test_no_connection(self) -> None:
        set_context(AgentContext(mcp_connection=None))
        try:
            _flush_pending_changes()
        finally:
            set_context(AgentContext())

    def test_no_pending_changes(self) -> None:
        conn = MagicMock()
        conn.has_changes.return_value = False
        set_context(AgentContext(mcp_connection=conn))
        try:
            _flush_pending_changes()
            conn.flush_and_commit.assert_not_called()
        finally:
            set_context(AgentContext())

    def test_flushes_pending_changes(self) -> None:
        conn = MagicMock()
        conn.has_changes.return_value = True
        set_context(AgentContext(mcp_connection=conn))
        try:
            _flush_pending_changes()
            conn.flush_and_commit.assert_called_once_with("auto-flush before history query")
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.change_history._flush_pending_changes")
    def test_show_change_history_flushes_before_listing(self, mock_flush: MagicMock) -> None:
        store = MagicMock()
        store.list_commits.return_value = []
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            show_change_history()
            mock_flush.assert_called_once()
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.change_history._flush_pending_changes")
    def test_revert_commit_flushes_before_reverting(self, mock_flush: MagicMock) -> None:
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[_ec("queue", "123", "My Queue", "create", None, {"name": "My Queue"})]
        )
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            revert_commit(commit_hash="abc123")
            mock_flush.assert_called_once()
        finally:
            set_context(AgentContext())


class TestUnwrap:
    def test_unwraps_result_key(self) -> None:
        assert unwrap({"result": {"id": 1, "name": "Test"}}) == {"id": 1, "name": "Test"}

    def test_returns_as_is_when_no_result(self) -> None:
        data = {"id": 1, "name": "Test"}
        assert unwrap(data) == data

    def test_returns_as_is_when_result_is_not_dict(self) -> None:
        data = {"result": "not a dict"}
        assert unwrap(data) == data


class TestUnwrapSnapshot:
    """Tests for _unwrap_snapshot defense-in-depth helper."""

    def test_bare_entity_dict(self) -> None:
        data = {"id": 1, "name": "Schema", "content": [{"id": "f1"}]}
        assert _unwrap_snapshot(data) == data

    def test_fastmcp_result_wrapper(self) -> None:
        data = {"result": {"id": 1, "name": "Schema", "content": [{"id": "f1"}]}}
        assert _unwrap_snapshot(data) == {"id": 1, "name": "Schema", "content": [{"id": "f1"}]}

    def test_unified_get_wrapper(self) -> None:
        data = {"entity": "schema", "id": 1, "data": {"id": 1, "content": [{"id": "f1"}]}}
        assert _unwrap_snapshot(data) == {"id": 1, "content": [{"id": "f1"}]}

    def test_double_wrapped_fastmcp_plus_unified_get(self) -> None:
        """Regression: the exact scenario that caused the 'before snapshot has no content' error."""
        data = {"result": {"entity": "schema", "id": 1, "data": {"id": 1, "content": [{"id": "f1"}]}}}
        assert _unwrap_snapshot(data) == {"id": 1, "content": [{"id": "f1"}]}


class TestDeduplicateChanges:
    def test_no_duplicates(self) -> None:
        changes = [
            _ec("queue", "1", "Q1", "create", None, {"name": "Q1"}),
            _ec("schema", "2", "S1", "update", {"content": []}, {"content": [{"id": "f1"}]}),
        ]
        result = _deduplicate_changes(changes)
        assert len(result) == 2
        assert result[0] is changes[0]
        assert result[1] is changes[1]

    def test_same_entity_updated_twice(self) -> None:
        original = {"id": 100, "content": [{"id": "f1"}, {"id": "f2"}]}
        pruned = {"id": 100, "content": []}
        patched = {"id": 100, "content": [{"id": "formula1"}]}

        changes = [
            _ec("schema", "100", "Invoice", "update", original, pruned),
            _ec("schema", "100", "Invoice", "update", pruned, patched),
        ]
        result = _deduplicate_changes(changes)

        assert len(result) == 1
        assert result[0].before == original
        assert result[0].after == patched
        assert result[0].operation == "update"

    def test_three_updates_keeps_first_before_last_after(self) -> None:
        changes = [
            _ec("schema", "1", "S", "update", {"v": 1}, {"v": 2}),
            _ec("schema", "1", "S", "update", {"v": 2}, {"v": 3}),
            _ec("schema", "1", "S", "update", {"v": 3}, {"v": 4}),
        ]
        result = _deduplicate_changes(changes)

        assert len(result) == 1
        assert result[0].before == {"v": 1}
        assert result[0].after == {"v": 4}

    def test_mixed_entities_only_dedupes_same(self) -> None:
        changes = [
            _ec("queue", "1", "Q", "create", None, {"name": "Q"}),
            _ec("schema", "2", "S", "update", {"v": 1}, {"v": 2}),
            _ec("schema", "2", "S", "update", {"v": 2}, {"v": 3}),
        ]
        result = _deduplicate_changes(changes)

        assert len(result) == 2
        assert result[0].entity_type == "queue"
        assert result[1].entity_type == "schema"
        assert result[1].before == {"v": 1}
        assert result[1].after == {"v": 3}

    def test_preserves_entity_name_from_first(self) -> None:
        changes = [
            _ec("schema", "1", "Invoice", "update", {"v": 1}, {"v": 2}),
            _ec("schema", "1", "", "update", {"v": 2}, {"v": 3}),
        ]
        result = _deduplicate_changes(changes)
        assert result[0].entity_name == "Invoice"

    def test_create_then_delete_is_noop(self) -> None:
        """Create + delete of same entity -> no-op, dropped from result."""
        changes = [
            _ec("queue", "1", "Q", "create", None, {"name": "Q"}),
            _ec("hook", "5", "H", "create", None, {"name": "H"}),
            _ec("hook", "5", "H", "delete", {"name": "H"}, None),
        ]
        result = _deduplicate_changes(changes)
        assert len(result) == 1
        assert result[0].entity_type == "queue"

    def test_create_then_delete_with_other_entities_preserved(self) -> None:
        """Only the no-op entity is dropped; other entities kept."""
        changes = [
            _ec("queue", "1", "Q1", "create", None, {"name": "Q1"}),
            _ec("hook", "5", "H", "create", None, {"name": "H"}),
            _ec("schema", "10", "S", "update", {"v": 1}, {"v": 2}),
            _ec("hook", "5", "H", "delete", {"name": "H"}, None),
        ]
        result = _deduplicate_changes(changes)
        assert len(result) == 2
        assert result[0].entity_type == "queue"
        assert result[1].entity_type == "schema"

    def test_update_then_delete_collapses_to_delete(self) -> None:
        changes = [
            _ec("schema", "1", "S", "update", {"v": 1}, {"v": 2}),
            _ec("schema", "1", "S", "delete", {"v": 2}, None),
        ]
        result = _deduplicate_changes(changes)
        assert len(result) == 1
        assert result[0].operation == "delete"
        assert result[0].before == {"v": 1}
        assert result[0].after is None

    def test_create_then_update_collapses_to_create(self) -> None:
        changes = [
            _ec("queue", "1", "Q", "create", None, {"name": "Q"}),
            _ec("queue", "1", "Q", "update", {"name": "Q"}, {"name": "Q2"}),
        ]
        result = _deduplicate_changes(changes)
        assert len(result) == 1
        assert result[0].operation == "create"
        assert result[0].before is None
        assert result[0].after == {"name": "Q2"}


class TestCollapsedOperation:
    def test_same_operations(self) -> None:
        assert _collapsed_operation("update", "update") == "update"
        assert _collapsed_operation("create", "create") == "create"
        assert _collapsed_operation("delete", "delete") == "delete"

    def test_create_then_update(self) -> None:
        assert _collapsed_operation("create", "update") == "create"

    def test_create_then_delete(self) -> None:
        assert _collapsed_operation("create", "delete") == "delete"

    def test_update_then_delete(self) -> None:
        assert _collapsed_operation("update", "delete") == "delete"


class TestRevertWithResultWrapper:
    """Tests that revert correctly unwraps FastMCP's {"result": ...} wrapper."""

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_revert_unwraps_result_before_api_call(self, mock_client_cls: MagicMock) -> None:
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()

        mock_http_client = MagicMock()
        mock_http_client.update = AsyncMock()
        mock_http_client.request_json = AsyncMock(return_value={"content": []})
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_cls.return_value = mock_client_instance

        # Snapshot wrapped in {"result": {...}} as FastMCP returns
        before_schema = {"result": {"id": 456, "name": "Invoice", "content": [{"category": "datapoint"}]}}
        after_schema = {"result": {"id": 456, "name": "Invoice", "content": []}}
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[_ec("schema", "456", "Invoice", "update", before_schema, after_schema)]
        )
        set_context(
            AgentContext(
                commit_store=store,
                rossum_environment="https://api.elis.rossum.ai/v1",
                rossum_credentials=("https://api.elis.rossum.ai/v1", "test-token"),
                mcp_event_loop=loop,
            )
        )

        try:
            result = json.loads(revert_commit(commit_hash="abc123"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()
            set_context(AgentContext())

        assert result["status"] == "completed"
        assert len(result["executed"]) == 1

        # Verify the API received only content, unwrapped from {"result": ...}
        call_args = mock_http_client.update.call_args
        restored_data = call_args.args[2]
        assert list(restored_data.keys()) == ["content"]
        assert restored_data["content"] == [{"category": "datapoint"}]

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_revert_deduplicates_multiple_schema_updates(self, mock_client_cls: MagicMock) -> None:
        """Prune + patch on same schema should revert to the pre-prune state."""
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()

        mock_http_client = MagicMock()
        mock_http_client.update = AsyncMock()
        mock_http_client.request_json = AsyncMock(return_value={"content": [{"id": "formula1"}]})
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_instance.delete_queue = AsyncMock()
        mock_client_cls.return_value = mock_client_instance

        original = {"id": 100, "name": "Invoice", "content": [{"id": "f1"}, {"id": "f2"}]}
        pruned = {"id": 100, "name": "Invoice", "content": []}
        patched = {"id": 100, "name": "Invoice", "content": [{"id": "formula1"}]}

        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[
                _ec("queue", "42", "My Queue", "create", None, {"id": 42, "name": "My Queue"}),
                _ec("schema", "100", "Invoice", "update", original, pruned),
                _ec("schema", "100", "Invoice", "update", pruned, patched),
            ]
        )
        set_context(
            AgentContext(
                commit_store=store,
                rossum_environment="https://api.elis.rossum.ai/v1",
                rossum_credentials=("https://api.elis.rossum.ai/v1", "test-token"),
                mcp_event_loop=loop,
            )
        )

        try:
            result = json.loads(revert_commit(commit_hash="abc123"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()
            set_context(AgentContext())

        assert result["status"] == "completed"
        # Queue create auto-deleted + schema update reverted (deduplicated)
        assert len(result["executed"]) == 2
        assert result["executed"][0]["status"] == "deleted"
        assert result["executed"][0]["entity_id"] == "42"
        assert result["executed"][1]["entity_id"] == "100"
        assert "remaining_actions" not in result

        # Schema API called once with only the content from the original (pre-prune) state
        mock_http_client.update.assert_called_once()
        restored_data = mock_http_client.update.call_args.args[2]
        assert list(restored_data.keys()) == ["content"]
        assert restored_data["content"] == original["content"]
        mock_client_instance.delete_queue.assert_called_once_with(42)


class TestRevertSchemaWith412:
    """Tests for 412 retry logic and inter-revert staggering."""

    def _make_loop(self):
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()
        return loop, thread

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_schema_revert_retries_on_412(self, mock_client_cls: MagicMock) -> None:
        """Schema revert retries automatically on 412 Precondition Failed."""
        loop, thread = self._make_loop()

        mock_http_client = MagicMock()
        # First update call raises 412, second succeeds
        err_412 = APIClientError("PATCH", "schemas/999", 412, Exception("Precondition Failed"))
        mock_http_client.update = AsyncMock(side_effect=[err_412, None])
        mock_http_client.request_json = AsyncMock(return_value={"content": []})
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_cls.return_value = mock_client_instance

        before_schema = {"content": [{"id": "field_a"}]}
        after_schema = {"content": []}
        store = MagicMock()
        store.get_commit.return_value = _make_commit(
            changes=[_ec("schema", "999", "Invoice", "update", before_schema, after_schema)]
        )
        set_context(
            AgentContext(
                commit_store=store,
                rossum_environment="https://api.elis.rossum.ai/v1",
                rossum_credentials=("https://api.elis.rossum.ai/v1", "test-token"),
                mcp_event_loop=loop,
            )
        )

        with patch("rossum_agent.tools.change_history.asyncio.sleep", new=AsyncMock()):
            try:
                result = json.loads(revert_commit(commit_hash="abc123"))
            finally:
                loop.call_soon_threadsafe(loop.stop)
                thread.join()
                loop.close()
                set_context(AgentContext())

        assert result["status"] == "completed"
        assert mock_http_client.update.call_count == 2
        # GET called twice -- once before each PATCH attempt
        assert mock_http_client.request_json.call_count == 2

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_schema_revert_raises_after_max_retries(self, mock_client_cls: MagicMock) -> None:
        """After exhausting retries the 412 is surfaced as an error."""
        loop, thread = self._make_loop()

        err_412 = APIClientError("PATCH", "schemas/999", 412, Exception("Precondition Failed"))
        mock_http_client = MagicMock()
        mock_http_client.update = AsyncMock(side_effect=err_412)
        mock_http_client.request_json = AsyncMock(return_value={"content": []})
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_cls.return_value = mock_client_instance

        before_schema = {"content": [{"id": "field_a"}]}
        after_schema = {"content": []}
        store = MagicMock()
        store.get_commit.return_value = _make_commit(
            changes=[_ec("schema", "999", "Invoice", "update", before_schema, after_schema)]
        )
        set_context(
            AgentContext(
                commit_store=store,
                rossum_environment="https://api.elis.rossum.ai/v1",
                rossum_credentials=("https://api.elis.rossum.ai/v1", "test-token"),
                mcp_event_loop=loop,
            )
        )

        with patch("rossum_agent.tools.change_history.asyncio.sleep", new=AsyncMock()):
            try:
                result = json.loads(revert_commit(commit_hash="abc123"))
            finally:
                loop.call_soon_threadsafe(loop.stop)
                thread.join()
                loop.close()
                set_context(AgentContext())

        assert result["status"] == "partial"
        assert len(result["errors"]) == 1
        assert "412" in result["errors"][0]["error"] or "Precondition" in result["errors"][0]["error"]

    @patch("rossum_agent.tools.change_history.time.sleep")
    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_inter_revert_delay_between_changes(
        self,
        mock_client_cls: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        """A 0.5s delay is inserted between successive change reverts."""
        loop, thread = self._make_loop()

        mock_http_client = MagicMock()
        mock_http_client.update = AsyncMock()
        mock_http_client.request_json = AsyncMock(return_value={"content": []})
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_cls.return_value = mock_client_instance

        before1 = {"content": [{"id": "f1"}]}
        after1 = {"content": []}
        before2 = {"content": [{"id": "f2"}]}
        after2 = {"content": []}

        store = MagicMock()
        store.get_commit.return_value = _make_commit(
            changes=[
                _ec("schema", "100", "S1", "update", before1, after1),
                _ec("schema", "200", "S2", "update", before2, after2),
            ]
        )
        set_context(
            AgentContext(
                commit_store=store,
                rossum_environment="https://api.elis.rossum.ai/v1",
                rossum_credentials=("https://api.elis.rossum.ai/v1", "test-token"),
                mcp_event_loop=loop,
            )
        )

        try:
            revert_commit(commit_hash="abc123")
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()
            set_context(AgentContext())

        # sleep(0.5) called once -- between the two changes (not before the first)
        mock_sleep.assert_called_once_with(0.5)


class TestRevertSchemaWithRetryUnit:
    """Unit tests for _revert_schema_with_retry."""

    def test_succeeds_on_first_attempt(self) -> None:
        loop = asyncio.new_event_loop()

        async def run():
            client = MagicMock()
            client._http_client.request_json = AsyncMock(return_value={"content": []})
            client._http_client.update = AsyncMock()
            await _revert_schema_with_retry(client, 42, {"content": []})
            client._http_client.request_json.assert_called_once_with("GET", "schemas/42")
            client._http_client.update.assert_called_once()

        try:
            loop.run_until_complete(run())
        finally:
            loop.close()

    def test_retries_on_412_then_succeeds(self) -> None:
        loop = asyncio.new_event_loop()

        async def run():
            err = APIClientError("PATCH", "schemas/99", 412, Exception("Precondition Failed"))
            client = MagicMock()
            client._http_client.request_json = AsyncMock(return_value={"content": []})
            client._http_client.update = AsyncMock(side_effect=[err, None])
            with patch("rossum_agent.tools.change_history.asyncio.sleep", new=AsyncMock()):
                await _revert_schema_with_retry(client, 99, {"content": []})
            assert client._http_client.update.call_count == 2
            assert client._http_client.request_json.call_count == 2

        try:
            loop.run_until_complete(run())
        finally:
            loop.close()

    def test_non_412_error_not_retried(self) -> None:
        loop = asyncio.new_event_loop()

        async def run():
            err = APIClientError("PATCH", "schemas/1", 404, Exception("Not Found"))
            client = MagicMock()
            client._http_client.request_json = AsyncMock(return_value={"content": []})
            client._http_client.update = AsyncMock(side_effect=err)
            import pytest

            with pytest.raises(APIClientError):
                await _revert_schema_with_retry(client, 1, {"content": []})
            assert client._http_client.update.call_count == 1

        try:
            loop.run_until_complete(run())
        finally:
            loop.close()


class TestComputeRevertPatch:
    def test_only_changed_fields(self) -> None:
        before = {"name": "Old", "active": True, "config": {"url": "https://old.com"}}
        after = {"name": "Old", "active": False, "config": {"url": "https://new.com"}}
        patch = _compute_revert_patch(before, after)
        assert patch == {"active": True, "config": {"url": "https://old.com"}}

    def test_excludes_read_only_fields(self) -> None:
        before = {"id": 1, "url": "https://api/v1/hooks/1", "name": "Hook", "active": True}
        after = {"id": 1, "url": "https://api/v1/hooks/1", "name": "Hook", "active": False}
        patch = _compute_revert_patch(before, after)
        assert patch == {"active": True}
        assert "id" not in patch
        assert "url" not in patch

    def test_unwraps_result_wrapper(self) -> None:
        before = {"result": {"name": "Old", "active": True}}
        after = {"result": {"name": "Old", "active": False}}
        patch = _compute_revert_patch(before, after)
        assert patch == {"active": True}

    def test_empty_patch_when_no_changes(self) -> None:
        data = {"name": "Same", "active": True}
        patch = _compute_revert_patch(data, data)
        assert patch == {}


class TestShowEntityHistory:
    """Tests for the show_entity_history tool."""

    @patch("rossum_agent.tools.change_history._flush_pending_changes")
    def test_flushes_before_listing(self, mock_flush: MagicMock) -> None:
        snap_store = MagicMock()
        snap_store.list_versions.return_value = []
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=MagicMock(),
                rossum_environment="https://api.elis.rossum.ai/v1",
            )
        )
        try:
            show_entity_history(entity_type="schema", entity_id="100")
            mock_flush.assert_called_once()
        finally:
            set_context(AgentContext())

    def test_custom_limit(self) -> None:
        env = "https://api.elis.rossum.ai/v1"
        snap_store = MagicMock()
        snap_store.list_versions.return_value = []
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=MagicMock(),
                rossum_environment=env,
            )
        )
        try:
            show_entity_history(entity_type="schema", entity_id="100", limit=5)
            snap_store.list_versions.assert_called_once_with(env, "schema", "100", limit=5)
        finally:
            set_context(AgentContext())

    def test_no_store(self) -> None:
        set_context(AgentContext(snapshot_store=None, commit_store=None, rossum_environment=None))
        try:
            result = json.loads(show_entity_history(entity_type="schema", entity_id="100"))
            assert "error" in result
        finally:
            set_context(AgentContext())

    def test_no_versions(self) -> None:
        snap_store = MagicMock()
        snap_store.list_versions.return_value = []
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=MagicMock(),
                rossum_environment="https://api.elis.rossum.ai/v1",
            )
        )
        try:
            result = json.loads(show_entity_history(entity_type="schema", entity_id="100"))
            assert "message" in result
        finally:
            set_context(AgentContext())

    def test_with_versions(self) -> None:
        env = "https://api.elis.rossum.ai/v1"
        ts = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
        snap_store = MagicMock()
        snap_store.list_versions.return_value = [("abc123", ts)]
        snap_store.get_snapshot.return_value = {"content": []}

        commit_store = MagicMock()
        commit_store.get_commit.return_value = _make_commit(hash="abc123", message="Updated schema")
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=commit_store,
                rossum_environment=env,
            )
        )
        try:
            result = json.loads(show_entity_history(entity_type="schema", entity_id="100"))
            assert len(result) == 1
            assert result[0]["commit_hash"] == "abc123"
            assert result[0]["commit_message"] == "Updated schema"
            assert result[0]["available"] is True
            snap_store.list_versions.assert_called_once_with(env, "schema", "100", limit=10)
        finally:
            set_context(AgentContext())

    def test_expired_snapshot_marked_unavailable(self) -> None:
        """Versions whose snapshot data has expired are marked available=False."""
        env = "https://api.elis.rossum.ai/v1"
        ts_old = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
        ts_new = datetime(2026, 1, 10, tzinfo=UTC).timestamp()
        snap_store = MagicMock()
        snap_store.list_versions.return_value = [("new_hash", ts_new), ("old_hash", ts_old)]
        snap_store.get_snapshot.side_effect = lambda _env, _et, _eid, h: {"content": []} if h == "new_hash" else None

        commit_store = MagicMock()
        commit_store.get_commit.side_effect = lambda _env, h: _make_commit(hash=h, message=f"Commit {h}")
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=commit_store,
                rossum_environment=env,
            )
        )
        try:
            result = json.loads(show_entity_history(entity_type="schema", entity_id="100"))
            assert len(result) == 2
            assert result[0]["available"] is True
            assert result[1]["available"] is False
        finally:
            set_context(AgentContext())


class TestRestoreEntityVersion:
    """Tests for the restore_entity_version tool."""

    @patch("rossum_agent.tools.change_history._flush_pending_changes")
    def test_flushes_before_restoring(self, mock_flush: MagicMock) -> None:
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = None
        snap_store.get_snapshot_at.return_value = None
        snap_store.get_earliest_version.return_value = None
        snap_store.list_versions.return_value = []
        commit_store = MagicMock()
        commit_store.get_commit.return_value = _make_commit(hash="abc")
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=commit_store,
                rossum_environment="https://api.elis.rossum.ai/v1",
            )
        )
        try:
            restore_entity_version(entity_type="schema", entity_id="100", commit_hash="abc")
            mock_flush.assert_called_once()
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_restore_unsupported_entity_type(self, mock_client_cls: MagicMock) -> None:
        env = "https://api.elis.rossum.ai/v1"

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()

        snapshot = {"name": "Some Widget", "data": "value"}
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = snapshot
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=MagicMock(),
                rossum_environment=env,
                rossum_credentials=(env, "test-token"),
                mcp_event_loop=loop,
            )
        )

        try:
            result = json.loads(restore_entity_version(entity_type="unknown_type", entity_id="1", commit_hash="abc"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()
            set_context(AgentContext())

        assert "error" in result
        assert "Unsupported entity type" in result["error"]

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_restore_schema_missing_content(self, mock_client_cls: MagicMock) -> None:
        env = "https://api.elis.rossum.ai/v1"

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()

        snapshot = {"name": "Invoice", "content": "not-a-list"}
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = snapshot
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=MagicMock(),
                rossum_environment=env,
                rossum_credentials=(env, "test-token"),
                mcp_event_loop=loop,
            )
        )

        try:
            result = json.loads(restore_entity_version(entity_type="schema", entity_id="456", commit_hash="abc"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()
            set_context(AgentContext())

        assert "error" in result
        assert "no content" in result["error"].lower() or "Cannot restore schema" in result["error"]

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_restore_no_changes_detected(self, mock_client_cls: MagicMock) -> None:
        """Restoring when snapshot matches current state returns no_changes."""
        env = "https://api.elis.rossum.ai/v1"

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()

        mock_http_client = MagicMock()
        # Current state matches snapshot exactly -- no diff
        current = {"name": "Queue", "timeout": 60}
        mock_http_client.fetch_one = AsyncMock(return_value=current)
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_cls.return_value = mock_client_instance

        snapshot = {"name": "Queue", "timeout": 60}
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = snapshot
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=MagicMock(),
                rossum_environment=env,
                rossum_credentials=(env, "test-token"),
                mcp_event_loop=loop,
            )
        )

        try:
            result = json.loads(restore_entity_version(entity_type="queue", entity_id="123", commit_hash="abc"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()
            set_context(AgentContext())

        assert result["status"] == "no_changes"
        mock_http_client.update.assert_not_called()

    def test_resolve_earliest_commit_missing(self) -> None:
        """Strategy 3 falls through when get_commit returns None for the earliest hash."""
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = None
        snap_store.get_snapshot_at.return_value = None
        snap_store.get_earliest_version.return_value = ("earliest_hash", 500.0)
        snap_store.list_versions.return_value = []
        commit_store = MagicMock()
        # Target commit exists but earliest commit has expired
        commit_store.get_commit.side_effect = lambda _env, h: _make_commit(hash="target") if h == "target" else None
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=commit_store,
                rossum_environment="https://api.elis.rossum.ai/v1",
            )
        )
        try:
            result = json.loads(restore_entity_version(entity_type="schema", entity_id="100", commit_hash="target"))
            assert "error" in result
            assert "No snapshot found" in result["error"]
        finally:
            set_context(AgentContext())

    def test_resolve_entity_not_in_earliest_commit(self) -> None:
        """Strategy 3 falls through when earliest commit doesn't contain the target entity."""
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = None
        snap_store.get_snapshot_at.return_value = None
        snap_store.get_earliest_version.return_value = ("earliest_hash", 500.0)
        snap_store.list_versions.return_value = []
        # Earliest commit exists but contains changes for a different entity
        earliest_commit = _make_commit(
            hash="earliest_hash",
            changes=[_ec("hook", "999", "Other Hook", "update", {"name": "H"}, {"name": "H2"})],
        )
        commit_store = MagicMock()
        commit_store.get_commit.side_effect = lambda _env, h: (
            _make_commit(hash="target") if h == "target" else earliest_commit
        )
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=commit_store,
                rossum_environment="https://api.elis.rossum.ai/v1",
            )
        )
        try:
            result = json.loads(restore_entity_version(entity_type="schema", entity_id="100", commit_hash="target"))
            assert "error" in result
            assert "No snapshot found" in result["error"]
        finally:
            set_context(AgentContext())

    def test_no_store(self) -> None:
        set_context(AgentContext(snapshot_store=None, commit_store=None, rossum_environment=None))
        try:
            result = json.loads(restore_entity_version(entity_type="schema", entity_id="100", commit_hash="abc"))
            assert "error" in result
        finally:
            set_context(AgentContext())

    def test_commit_not_found_when_no_snapshots(self) -> None:
        """When no exact snapshot and commit doesn't exist, error with commit not found."""
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = None
        commit_store = MagicMock()
        commit_store.get_commit.return_value = None
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=commit_store,
                rossum_environment="https://api.elis.rossum.ai/v1",
            )
        )
        try:
            result = json.loads(restore_entity_version(entity_type="schema", entity_id="100", commit_hash="missing"))
            assert "error" in result
            assert "not found" in result["error"]
        finally:
            set_context(AgentContext())

    def test_snapshot_not_found_after_all_fallbacks(self) -> None:
        """Returns error when all three lookup strategies fail and no index entries exist."""
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = None
        snap_store.get_snapshot_at.return_value = None
        snap_store.get_earliest_version.return_value = None
        snap_store.list_versions.return_value = []
        commit_store = MagicMock()
        commit_store.get_commit.return_value = _make_commit(hash="missing")
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=commit_store,
                rossum_environment="https://api.elis.rossum.ai/v1",
            )
        )
        try:
            result = json.loads(restore_entity_version(entity_type="schema", entity_id="100", commit_hash="missing"))
            assert "error" in result
            assert "No snapshot found" in result["error"]
        finally:
            set_context(AgentContext())

    def test_expired_snapshot_gives_clear_error(self) -> None:
        """When index entries exist but snapshot data has expired, error mentions expiration."""
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = None
        snap_store.get_snapshot_at.return_value = None
        snap_store.get_earliest_version.return_value = None
        snap_store.list_versions.return_value = [("old_hash", 1000.0)]
        commit_store = MagicMock()
        commit_store.get_commit.return_value = _make_commit(hash="target")
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=commit_store,
                rossum_environment="https://api.elis.rossum.ai/v1",
            )
        )
        try:
            result = json.loads(restore_entity_version(entity_type="schema", entity_id="100", commit_hash="target"))
            assert "error" in result
            assert "expired" in result["error"].lower()
        finally:
            set_context(AgentContext())

    def test_time_based_fallback(self) -> None:
        """Falls back to get_snapshot_at when no exact snapshot exists."""
        snapshot = {"name": "Queue", "content": []}
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = None
        snap_store.get_snapshot_at.return_value = snapshot
        commit_store = MagicMock()
        commit_store.get_commit.return_value = _make_commit(hash="queue-only-commit")
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=commit_store,
                rossum_environment="https://api.elis.rossum.ai/v1",
            )
        )
        try:
            # No API call needed -- just verify the snapshot is resolved (credentials absent -> error after snapshot found)
            result = json.loads(
                restore_entity_version(entity_type="schema", entity_id="100", commit_hash="queue-only-commit")
            )
            snap_store.get_snapshot_at.assert_called_once()
            # Error is about credentials, not missing snapshot
            assert "No snapshot found" not in result.get("error", "")
        finally:
            set_context(AgentContext())

    def test_pre_first_change_fallback(self) -> None:
        """Uses change.before from earliest recorded change when target is before all snapshots."""
        before_state = {"name": "Schema", "content": [{"id": "original"}]}
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = None
        snap_store.get_snapshot_at.return_value = None
        snap_store.get_earliest_version.return_value = ("first-schema-commit", 1000.0)
        first_commit = _make_commit(
            hash="first-schema-commit",
            changes=[_ec("schema", "100", "Schema", "update", before_state, {"name": "Schema", "content": []})],
        )
        commit_store = MagicMock()
        commit_store.get_commit.side_effect = lambda env, h: (
            _make_commit(hash="earlier-commit") if h == "earlier-commit" else first_commit
        )
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=commit_store,
                rossum_environment="https://api.elis.rossum.ai/v1",
            )
        )
        try:
            # No credentials -> error after snapshot resolved -- not "No snapshot found"
            result = json.loads(
                restore_entity_version(entity_type="schema", entity_id="100", commit_hash="earlier-commit")
            )
            snap_store.get_earliest_version.assert_called_once()
            assert "No snapshot found" not in result.get("error", "")
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_restore_schema(self, mock_client_cls: MagicMock) -> None:
        env = "https://api.elis.rossum.ai/v1"

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()

        mock_http_client = MagicMock()
        mock_http_client.update = AsyncMock()
        mock_http_client.request_json = AsyncMock(
            return_value={"content": [{"category": "datapoint"}, {"category": "new"}]}
        )
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_cls.return_value = mock_client_instance

        snapshot = {"name": "Invoice", "content": [{"category": "datapoint"}]}
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = snapshot
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=MagicMock(),
                rossum_environment=env,
                rossum_credentials=(env, "test-token"),
                mcp_event_loop=loop,
            )
        )

        try:
            result = json.loads(restore_entity_version(entity_type="schema", entity_id="456", commit_hash="abc123"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()
            set_context(AgentContext())

        assert result["status"] == "restored"
        assert result["entity_type"] == "schema"
        assert result["entity_id"] == "456"
        mock_http_client.update.assert_called_once()
        restored_data = mock_http_client.update.call_args.args[2]
        assert list(restored_data.keys()) == ["content"]

    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_restore_queue(self, mock_client_cls: MagicMock) -> None:
        env = "https://api.elis.rossum.ai/v1"

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()

        mock_http_client = MagicMock()
        mock_http_client.update = AsyncMock()
        mock_http_client.fetch_one = AsyncMock(return_value={"name": "Queue", "timeout": 120})
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_cls.return_value = mock_client_instance

        snapshot = {"name": "Queue", "timeout": 60}
        snap_store = MagicMock()
        snap_store.get_snapshot.return_value = snapshot
        set_context(
            AgentContext(
                snapshot_store=snap_store,
                commit_store=MagicMock(),
                rossum_environment=env,
                rossum_credentials=(env, "test-token"),
                mcp_event_loop=loop,
            )
        )

        try:
            result = json.loads(restore_entity_version(entity_type="queue", entity_id="123", commit_hash="abc123"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()
            set_context(AgentContext())

        assert result["status"] == "restored"
        mock_http_client.update.assert_called_once()
        restored_data = mock_http_client.update.call_args.args[2]
        assert restored_data == {"timeout": 60}


class TestRevertCommitRelaxed:
    """Test that revert_commit no longer requires latest-only."""

    def test_revert_non_latest_commit(self) -> None:
        """revert_commit should work on any commit, not just the latest."""
        store = MagicMock()
        # Commit exists but is NOT the latest
        store.get_latest_hash.return_value = "newer_hash"
        store.get_commit.return_value = _make_commit(
            hash="old_hash",
            changes=[_ec("queue", "123", "My Queue", "update", {"timeout": 60}, {"timeout": 120})],
        )
        set_context(AgentContext(commit_store=store, rossum_environment="https://api.elis.rossum.ai/v1"))
        try:
            result = json.loads(revert_commit(commit_hash="old_hash"))
            # Should NOT error -- the latest-only restriction is removed
            assert "error" not in result
            assert result["commit_hash"] == "old_hash"
        finally:
            set_context(AgentContext())


class TestDiffObjects:
    """Tests for the diff_objects tool."""

    def test_identical_objects(self) -> None:
        obj = json.dumps({"a": 1, "b": 2})
        assert diff_objects(obj, obj) == "No differences found."

    def test_added_key(self) -> None:
        before = json.dumps({"a": 1})
        after = json.dumps({"a": 1, "b": 2})
        result = diff_objects(before, after)
        assert '+  "b": 2' in result

    def test_removed_key(self) -> None:
        before = json.dumps({"a": 1, "b": 2})
        after = json.dumps({"a": 1})
        result = diff_objects(before, after)
        assert '-  "b": 2' in result

    def test_changed_value(self) -> None:
        before = json.dumps({"timeout": 60})
        after = json.dumps({"timeout": 120})
        result = diff_objects(before, after)
        assert "-" in result
        assert "+" in result
        assert "60" in result
        assert "120" in result

    def test_keys_sorted_for_stable_diff(self) -> None:
        # Key order in input should not affect diff output
        before = json.dumps({"b": 2, "a": 1})
        after = json.dumps({"a": 1, "b": 2})
        assert diff_objects(before, after) == "No differences found."

    def test_invalid_json_before(self) -> None:
        result = json.loads(diff_objects("not-json", json.dumps({})))
        assert "error" in result

    def test_invalid_json_after(self) -> None:
        result = json.loads(diff_objects(json.dumps({}), "not-json"))
        assert "error" in result

    def test_diff_has_unified_format_headers(self) -> None:
        before = json.dumps({"x": 1})
        after = json.dumps({"x": 2})
        result = diff_objects(before, after)
        assert result.startswith("---")
        assert "+++" in result

    def test_dict_input_instead_of_json_string(self) -> None:
        # Agent sometimes passes dict objects directly instead of JSON strings
        result = diff_objects({"a": 1}, {"a": 1, "b": 2})  # type: ignore[arg-type]
        assert '+  "b": 2' in result

    def test_double_encoded_json_string(self) -> None:
        # Agent sometimes double-encodes: json.dumps(json.dumps(obj))
        before = json.dumps(json.dumps({"x": 1}))
        after = json.dumps(json.dumps({"x": 2}))
        result = diff_objects(before, after)
        assert "-" in result
        assert "+" in result
        assert "1" in result
        assert "2" in result
        # Must produce a structured diff, not a single-line string diff
        assert result.startswith("---")
