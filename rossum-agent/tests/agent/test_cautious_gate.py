"""Tests for rossum_agent.agent.cautious_gate module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.agent import AgentConfig, RossumAgent, ToolCall, ToolResult
from rossum_agent.agent.cautious_gate import is_write_tool
from rossum_agent.agent.tool_execution import execute_tool_with_progress
from rossum_agent.tools.core import CAUTIOUS_CONFIRMATION_MARKER, AgentContext, reset_context, set_context


class TestCautiousWriteGate:
    """Test the cautious persona write confirmation gate."""

    def _create_agent(self) -> RossumAgent:
        """Helper to create an agent with mocked dependencies."""
        mock_client = MagicMock()
        mock_mcp_connection = AsyncMock()
        mock_mcp_connection.get_tools.return_value = []
        config = AgentConfig()
        return RossumAgent(
            client=mock_client,
            mcp_connection=mock_mcp_connection,
            system_prompt="Test prompt",
            config=config,
        )

    async def _get_final_result(self, agent: RossumAgent, tool_call: ToolCall) -> ToolResult:
        """Helper to get the final ToolResult from execute_tool_with_progress."""
        result = None
        async for item in execute_tool_with_progress(
            tool_call, 1, [tool_call], (1, 1), agent.mcp_connection, agent.tokens
        ):
            if isinstance(item, ToolResult):
                result = item
        assert result is not None
        return result

    @pytest.mark.asyncio
    async def test_blocks_mcp_write_tool_in_cautious_mode(self):
        """Write MCP tools are blocked and an AgentQuestion is emitted."""
        agent = self._create_agent()
        agent.mcp_connection.fetch_snapshot = AsyncMock(return_value=None)
        question_received = []

        ctx = AgentContext(
            persona="cautious",
            question_callback=lambda q: question_received.append(q),
        )
        token = set_context(ctx)
        try:
            tool_call = ToolCall(id="tc_1", name="update_queue", arguments={"queue_id": 123})

            with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=True):
                result = await self._get_final_result(agent, tool_call)

            assert result.is_error is True
            assert CAUTIOUS_CONFIRMATION_MARKER in result.content
            assert "update_queue" in ctx.cautious_blocked_writes
            assert len(question_received) == 1
            assert "update_queue" in question_received[0].questions[0].question
        finally:
            reset_context(token)

    @pytest.mark.asyncio
    async def test_blocks_internal_write_tool_in_cautious_mode(self):
        """Internal write tools (revert_commit, etc.) are blocked in cautious mode."""
        agent = self._create_agent()
        question_received = []

        ctx = AgentContext(
            persona="cautious",
            question_callback=lambda q: question_received.append(q),
        )
        token = set_context(ctx)
        try:
            tool_call = ToolCall(id="tc_1", name="revert_commit", arguments={"commit_hash": "abc123"})

            with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=False):
                result = await self._get_final_result(agent, tool_call)

            assert result.is_error is True
            assert CAUTIOUS_CONFIRMATION_MARKER in result.content
            assert "revert_commit" in ctx.cautious_blocked_writes
            assert len(question_received) == 1
        finally:
            reset_context(token)

    @pytest.mark.asyncio
    async def test_allows_preapproved_write_tool(self):
        """Pre-approved write tools execute without blocking."""
        agent = self._create_agent()
        agent.mcp_connection.call_tool.return_value = {"status": "ok"}

        ctx = AgentContext(
            persona="cautious",
            cautious_preapproved_writes={"update_queue"},
        )
        token = set_context(ctx)
        try:
            tool_call = ToolCall(id="tc_1", name="update_queue", arguments={"queue_id": 123})

            with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=True):
                result = await self._get_final_result(agent, tool_call)

            assert result.is_error is False
            assert "update_queue" not in ctx.cautious_preapproved_writes
        finally:
            reset_context(token)

    @pytest.mark.asyncio
    async def test_does_not_block_in_default_persona(self):
        """Write tools are not blocked when persona is default."""
        agent = self._create_agent()
        agent.mcp_connection.call_tool.return_value = {"status": "ok"}

        ctx = AgentContext(persona="default")
        token = set_context(ctx)
        try:
            tool_call = ToolCall(id="tc_1", name="update_queue", arguments={"queue_id": 123})

            with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=True):
                result = await self._get_final_result(agent, tool_call)

            assert result.is_error is False
        finally:
            reset_context(token)

    @pytest.mark.asyncio
    async def test_does_not_block_read_tools_in_cautious_mode(self):
        """Read tools are not blocked even in cautious mode."""
        agent = self._create_agent()
        agent.mcp_connection.call_tool.return_value = {"queues": []}

        ctx = AgentContext(persona="cautious")
        token = set_context(ctx)
        try:
            tool_call = ToolCall(id="tc_1", name="list_queues", arguments={})

            with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=False):
                result = await self._get_final_result(agent, tool_call)

            assert result.is_error is False
        finally:
            reset_context(token)

    @pytest.mark.asyncio
    async def test_question_shows_diff_for_update_tool(self):
        """Update tools show a field-level diff when existing object is found."""
        agent = self._create_agent()
        agent.mcp_connection.fetch_snapshot = AsyncMock(
            return_value={"name": "Old Name", "locale": "en_US", "rir_url": "https://example.com"}
        )
        agent.mcp_connection._cache_set = MagicMock()
        question_received = []

        ctx = AgentContext(
            persona="cautious",
            question_callback=lambda q: question_received.append(q),
        )
        token = set_context(ctx)
        try:
            tool_call = ToolCall(id="tc_1", name="update_queue", arguments={"queue_id": 456, "name": "New Name"})

            with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=True):
                await self._get_final_result(agent, tool_call)

            question_text = question_received[0].questions[0].question
            # Should show unified diff with -/+ lines
            assert "Changes to queue 456" in question_text
            assert "```diff" in question_text
            assert '-  "name": "Old Name"' in question_text
            assert '+  "name": "New Name"' in question_text
        finally:
            reset_context(token)

    @pytest.mark.asyncio
    async def test_question_falls_back_to_args_when_no_snapshot(self):
        """Falls back to raw arguments when snapshot fetch returns None."""
        agent = self._create_agent()
        agent.mcp_connection.fetch_snapshot = AsyncMock(return_value=None)
        question_received = []

        ctx = AgentContext(
            persona="cautious",
            question_callback=lambda q: question_received.append(q),
        )
        token = set_context(ctx)
        try:
            tool_call = ToolCall(id="tc_1", name="update_queue", arguments={"queue_id": 456, "name": "New Name"})

            with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=True):
                await self._get_final_result(agent, tool_call)

            question_text = question_received[0].questions[0].question
            assert "Arguments" in question_text
            assert "New Name" in question_text
        finally:
            reset_context(token)

    @pytest.mark.asyncio
    async def test_question_shows_args_for_create_tool(self):
        """Create tools show raw arguments (no existing object to diff against)."""
        agent = self._create_agent()
        question_received = []

        ctx = AgentContext(
            persona="cautious",
            question_callback=lambda q: question_received.append(q),
        )
        token = set_context(ctx)
        try:
            tool_call = ToolCall(
                id="tc_1", name="create_hook", arguments={"name": "My Hook", "config": {"url": "https://x.com"}}
            )

            with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=True):
                await self._get_final_result(agent, tool_call)

            question_text = question_received[0].questions[0].question
            assert "Arguments" in question_text
            assert "My Hook" in question_text
        finally:
            reset_context(token)

    @pytest.mark.asyncio
    async def test_question_shows_diff_with_nested_data(self):
        """Update tools with nested *_data objects are flattened for diff."""
        agent = self._create_agent()
        agent.mcp_connection.fetch_snapshot = AsyncMock(return_value={"name": "Old", "locale": "en_US"})
        agent.mcp_connection._cache_set = MagicMock()
        question_received = []

        ctx = AgentContext(
            persona="cautious",
            question_callback=lambda q: question_received.append(q),
        )
        token = set_context(ctx)
        try:
            tool_call = ToolCall(
                id="tc_1",
                name="update_queue",
                arguments={"queue_id": 1, "queue_data": {"name": "New", "locale": "cs_CZ"}},
            )

            with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=True):
                await self._get_final_result(agent, tool_call)

            question_text = question_received[0].questions[0].question
            assert "Changes to queue 1" in question_text
            assert "```diff" in question_text
            assert '-  "name": "Old"' in question_text
            assert '+  "name": "New"' in question_text
            assert '-  "locale": "en_US"' in question_text
            assert '+  "locale": "cs_CZ"' in question_text
        finally:
            reset_context(token)

    @pytest.mark.asyncio
    async def test_question_has_yes_no_chat_options(self):
        """The confirmation question offers yes/no/chat options."""
        agent = self._create_agent()
        agent.mcp_connection.fetch_snapshot = AsyncMock(return_value=None)
        question_received = []

        ctx = AgentContext(
            persona="cautious",
            question_callback=lambda q: question_received.append(q),
        )
        token = set_context(ctx)
        try:
            tool_call = ToolCall(id="tc_1", name="update_queue", arguments={})

            with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=True):
                await self._get_final_result(agent, tool_call)

            options = question_received[0].questions[0].options
            option_values = {o.value for o in options}
            assert option_values == {"yes", "no", "chat"}
        finally:
            reset_context(token)

    @pytest.mark.asyncio
    async def test_question_shows_no_changes_for_identical_update(self):
        """Update with no effective changes shows 'No effective changes' message."""
        agent = self._create_agent()
        agent.mcp_connection.fetch_snapshot = AsyncMock(return_value={"name": "Same", "locale": "en_US"})
        agent.mcp_connection._cache_set = MagicMock()
        question_received = []

        ctx = AgentContext(
            persona="cautious",
            question_callback=lambda q: question_received.append(q),
        )
        token = set_context(ctx)
        try:
            tool_call = ToolCall(id="tc_1", name="update_queue", arguments={"queue_id": 1, "name": "Same"})

            with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=True):
                await self._get_final_result(agent, tool_call)

            question_text = question_received[0].questions[0].question
            assert "No effective changes" in question_text
        finally:
            reset_context(token)

    def test_is_write_tool_internal(self):
        """_is_write_tool recognizes internal write tools."""
        with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=False):
            assert is_write_tool("revert_commit") is True
            assert is_write_tool("restore_entity_version") is True
            assert is_write_tool("patch_schema_with_subagent") is True
            assert is_write_tool("search_knowledge_base") is False

    def test_is_write_tool_mcp(self):
        """_is_write_tool delegates to is_mcp_write_tool for non-internal tools."""
        with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=True):
            assert is_write_tool("update_queue") is True
        with patch("rossum_agent.agent.cautious_gate.is_mcp_write_tool", return_value=False):
            assert is_write_tool("list_queues") is False


class TestExtractUpdateFields:
    """Test extract_update_fields function."""

    def test_extracts_flat_fields(self):
        """Extracts fields from flat arguments, skipping entity id."""
        from rossum_agent.agent.cautious_gate import extract_update_fields

        args = {"queue_id": 123, "name": "New", "locale": "cs_CZ"}
        result = extract_update_fields(args, "queue")

        assert result == {"name": "New", "locale": "cs_CZ"}
        assert "queue_id" not in result

    def test_skips_generic_id_key(self):
        """Skips the generic 'id' key."""
        from rossum_agent.agent.cautious_gate import extract_update_fields

        args = {"id": 456, "name": "Updated"}
        result = extract_update_fields(args, "hook")

        assert result == {"name": "Updated"}

    def test_skips_none_values(self):
        """None values are excluded from update fields."""
        from rossum_agent.agent.cautious_gate import extract_update_fields

        args = {"queue_id": 1, "name": "New", "locale": None}
        result = extract_update_fields(args, "queue")

        assert result == {"name": "New"}
        assert "locale" not in result

    def test_flattens_nested_data_object(self):
        """Nested *_data dicts are flattened into the update fields."""
        from rossum_agent.agent.cautious_gate import extract_update_fields

        args = {"queue_id": 1, "queue_data": {"name": "New", "locale": "cs_CZ"}}
        result = extract_update_fields(args, "queue")

        assert result == {"name": "New", "locale": "cs_CZ"}

    def test_non_data_dict_kept_as_is(self):
        """Dict values not ending with _data are kept as-is."""
        from rossum_agent.agent.cautious_gate import extract_update_fields

        args = {"hook_id": 1, "config": {"url": "https://example.com"}}
        result = extract_update_fields(args, "hook")

        assert result == {"config": {"url": "https://example.com"}}

    def test_empty_arguments(self):
        """Empty arguments return empty dict."""
        from rossum_agent.agent.cautious_gate import extract_update_fields

        result = extract_update_fields({}, "queue")

        assert result == {}


class TestFormatFieldDiff:
    """Test format_field_diff function."""

    def test_shows_unified_diff(self):
        """Shows unified diff for changed fields."""
        from rossum_agent.agent.cautious_gate import format_field_diff

        existing = {"name": "Old", "locale": "en_US"}
        args = {"queue_id": 1, "name": "New"}

        result = format_field_diff(existing, args, "queue", "1")

        assert "Changes to queue 1" in result
        assert "```diff" in result
        assert "-" in result
        assert "+" in result

    def test_empty_update_fields_shows_raw_args(self):
        """When extract_update_fields returns empty dict, shows raw arguments."""
        from rossum_agent.agent.cautious_gate import format_field_diff

        existing = {"name": "Existing"}
        # Only entity id in arguments — no actual fields to update
        args = {"queue_id": 1}

        result = format_field_diff(existing, args, "queue", "1")

        assert "Arguments" in result
        assert "```json" in result

    def test_no_effective_changes(self):
        """When proposed changes match existing values, shows no-change message."""
        from rossum_agent.agent.cautious_gate import format_field_diff

        existing = {"name": "Same", "locale": "en_US"}
        args = {"queue_id": 1, "name": "Same"}

        result = format_field_diff(existing, args, "queue", "1")

        assert "No effective changes" in result
