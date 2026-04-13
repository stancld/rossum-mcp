"""Tests for the dynamic tools module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.tools.core import AgentContext, DynamicToolsState, get_context, set_context
from rossum_agent.tools.dynamic_tools import (
    DELETE_TOOL_NAME,
    DISCOVERY_TOOL_NAME,
    CatalogData,
    _fetch_catalog_async,
    _fetch_catalog_from_mcp,
    _filter_mcp_tools_by_names,
    _load_categories_impl,
    get_dynamic_tools,
    get_load_tool_definition,
    get_write_tools,
    get_write_tools_async,
    load_tool,
    preload_categories_for_request,
    reset_dynamic_tools,
    suggest_categories_for_request,
)


class TestDiscoveryToolName:
    """Tests for DISCOVERY_TOOL_NAME constant."""

    def test_discovery_tool_name(self) -> None:
        assert DISCOVERY_TOOL_NAME == "list_tool_categories"


class TestDynamicToolState:
    """Tests for dynamic tool state management."""

    def test_reset_clears_state(self) -> None:
        reset_dynamic_tools()
        assert get_context().dynamic_tools.loaded_categories == set()
        assert get_dynamic_tools() == []

    def test_initial_state_is_empty(self) -> None:
        reset_dynamic_tools()
        assert len(get_context().dynamic_tools.loaded_categories) == 0
        assert len(get_dynamic_tools()) == 0


class TestSuggestCategories:
    """Tests for suggest_categories_for_request function."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        import rossum_agent.tools.dynamic_tools as dt

        dt._catalog_cache = None

    def teardown_method(self) -> None:
        """Clear cache after each test."""
        import rossum_agent.tools.dynamic_tools as dt

        dt._catalog_cache = None

    @patch("rossum_agent.tools.dynamic_tools._fetch_catalog_from_mcp")
    def test_suggests_queues_for_queue_keyword(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = CatalogData(
            catalog={"queues": {"get_queue", "list_queues"}},
            keywords={"queues": ["queue", "inbox"]},
        )
        # Word boundary matching requires exact word - "queue" won't match "queues"
        suggestions = suggest_categories_for_request("Show me the queue")
        assert "queues" in suggestions

    @patch("rossum_agent.tools.dynamic_tools._fetch_catalog_from_mcp")
    def test_suggests_schemas_for_schema_keyword(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = CatalogData(
            catalog={"schemas": {"get_schema", "list_schemas"}},
            keywords={"schemas": ["schema", "field"]},
        )
        suggestions = suggest_categories_for_request("Modify the schema")
        assert "schemas" in suggestions

    @patch("rossum_agent.tools.dynamic_tools._fetch_catalog_from_mcp")
    def test_returns_empty_for_unrelated_text(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = CatalogData(
            catalog={"queues": {"get_queue"}},
            keywords={"queues": ["queue"]},
        )
        suggestions = suggest_categories_for_request("Hello, how are you?")
        assert suggestions == []

    @patch("rossum_agent.tools.dynamic_tools._fetch_catalog_from_mcp")
    def test_case_insensitive(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = CatalogData(
            catalog={"queues": {"get_queue"}},
            keywords={"queues": ["queue"]},
        )
        # Word boundary matching requires exact word - use singular "queue"
        suggestions = suggest_categories_for_request("LIST THE QUEUE")
        assert "queues" in suggestions


class TestFilterMcpToolsByNames:
    """Tests for _filter_mcp_tools_by_names function."""

    def _create_mock_tool(self, name: str) -> MagicMock:
        tool = MagicMock()
        tool.name = name
        return tool

    def test_filters_tools_by_names(self) -> None:
        tools = [
            self._create_mock_tool("get_queue"),
            self._create_mock_tool("list_queues"),
            self._create_mock_tool("get_schema"),
            self._create_mock_tool("unrelated_tool"),
        ]
        result = _filter_mcp_tools_by_names(tools, {"get_queue", "list_queues"})
        assert len(result) == 2
        assert all(t.name in {"get_queue", "list_queues"} for t in result)

    def test_returns_empty_for_no_matching_tools(self) -> None:
        tools = [self._create_mock_tool("unrelated_tool")]
        result = _filter_mcp_tools_by_names(tools, {"get_queue"})
        assert result == []


class TestLoadCategoriesImpl:
    """Tests for _load_categories_impl function."""

    @patch("rossum_agent.tools.dynamic_tools.get_category_tool_names")
    def test_returns_error_for_unknown_category(self, mock_get_catalog: MagicMock) -> None:
        reset_dynamic_tools()
        mock_get_catalog.return_value = {"queues": {"get_queue"}}
        result = _load_categories_impl(["nonexistent"])
        assert "Error: Unknown categories" in result

    @patch("rossum_agent.tools.dynamic_tools.get_category_tool_names")
    def test_returns_already_loaded_message(self, mock_get_catalog: MagicMock) -> None:
        reset_dynamic_tools()
        mock_get_catalog.return_value = {"queues": {"get_queue"}}
        # Manually add category to loaded set
        get_context().dynamic_tools.loaded_categories.add("queues")
        result = _load_categories_impl(["queues"])
        assert result == "Categories already loaded: ['queues']"

    @patch("rossum_agent.tools.dynamic_tools.get_category_tool_names")
    def test_returns_error_when_no_mcp_connection(self, mock_get_catalog: MagicMock) -> None:
        reset_dynamic_tools()
        mock_get_catalog.return_value = {"queues": {"get_queue"}}
        set_context(AgentContext(mcp_connection=None, mcp_event_loop=MagicMock()))
        try:
            result = _load_categories_impl(["queues"])
            assert result == "Error: MCP connection not available"
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.dynamic_tools.get_category_tool_names")
    def test_returns_error_when_no_event_loop(self, mock_get_catalog: MagicMock) -> None:
        reset_dynamic_tools()
        mock_get_catalog.return_value = {"queues": {"get_queue"}}
        set_context(AgentContext(mcp_connection=MagicMock(), mcp_event_loop=None))
        try:
            result = _load_categories_impl(["queues"])
            assert result == "Error: MCP connection not available"
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.dynamic_tools.mcp_tools_to_anthropic_format")
    @patch("rossum_agent.tools.dynamic_tools.asyncio.run_coroutine_threadsafe")
    @patch("rossum_agent.tools.dynamic_tools.get_category_tool_names")
    def test_successful_load_adds_tools_and_marks_category(
        self,
        mock_get_catalog: MagicMock,
        mock_run_coro: MagicMock,
        mock_convert: MagicMock,
    ) -> None:
        reset_dynamic_tools()
        mock_get_catalog.return_value = {"queues": {"get_queue", "list_queues"}}

        mock_connection = MagicMock()
        mock_loop = MagicMock()
        set_context(AgentContext(mcp_connection=mock_connection, mcp_event_loop=mock_loop, mcp_mode="read-write"))
        try:
            # Create mock tools that match the queues category
            mock_tool1 = MagicMock()
            mock_tool1.name = "get_queue"
            mock_tool2 = MagicMock()
            mock_tool2.name = "list_queues"
            mock_future = MagicMock()
            mock_future.result.return_value = [mock_tool1, mock_tool2]
            mock_run_coro.return_value = mock_future

            # Mock the conversion function
            mock_anthropic_tool = {"type": "function", "function": {"name": "get_queue"}}
            mock_convert.return_value = [mock_anthropic_tool]

            result = _load_categories_impl(["queues"])

            assert "Loaded" in result
            assert "get_queue" in result or "list_queues" in result
            assert "queues" in get_context().dynamic_tools.loaded_categories
            assert len(get_dynamic_tools()) == 1
        finally:
            set_context(AgentContext())


class TestPreloadCategoriesForRequest:
    """Tests for preload_categories_for_request function."""

    @patch("rossum_agent.tools.dynamic_tools._load_categories_impl")
    @patch("rossum_agent.tools.dynamic_tools.suggest_categories_for_request")
    def test_preloads_suggested_categories_with_read(self, mock_suggest: MagicMock, mock_load: MagicMock) -> None:
        mock_suggest.return_value = ["queues", "schemas"]
        mock_load.return_value = "Loaded 10 tools from ['queues', 'schemas']"

        result = preload_categories_for_request("Show me all queues and schemas")

        # read is already not in suggestions, so it gets prepended
        mock_load.assert_called_once_with(["read", "queues", "schemas"])
        assert result is not None

    @patch("rossum_agent.tools.dynamic_tools._load_categories_impl")
    @patch("rossum_agent.tools.dynamic_tools.suggest_categories_for_request")
    def test_does_not_duplicate_read_when_already_suggested(
        self, mock_suggest: MagicMock, mock_load: MagicMock
    ) -> None:
        mock_suggest.return_value = ["read", "queues"]
        mock_load.return_value = "Loaded 10 tools from ['read', 'queues']"

        result = preload_categories_for_request("List all queues")

        mock_load.assert_called_once_with(["read", "queues"])
        assert result is not None

    @patch("rossum_agent.tools.dynamic_tools._load_categories_impl")
    @patch("rossum_agent.tools.dynamic_tools.suggest_categories_for_request")
    def test_preloads_read_even_when_no_keyword_matches(self, mock_suggest: MagicMock, mock_load: MagicMock) -> None:
        mock_suggest.return_value = []
        mock_load.return_value = "Loaded 2 tools from ['read']"

        result = preload_categories_for_request("Hello, how are you?")

        mock_load.assert_called_once_with(["read"])
        assert result is not None

    @patch("rossum_agent.tools.dynamic_tools._load_categories_impl")
    @patch("rossum_agent.tools.dynamic_tools.suggest_categories_for_request")
    def test_returns_none_on_error(self, mock_suggest: MagicMock, mock_load: MagicMock) -> None:
        mock_suggest.return_value = ["queues"]
        mock_load.return_value = "Error: MCP connection not available"

        result = preload_categories_for_request("Show me all queues")

        assert result is None


class TestDynamicToolsState:
    """Tests for DynamicToolsState class methods."""

    def test_initial_state_is_empty(self) -> None:
        state = DynamicToolsState()
        assert state.loaded_categories == set()
        assert state.tools == []

    def test_reset_clears_loaded_categories(self) -> None:
        state = DynamicToolsState()
        state.loaded_categories.add("queues")
        state.loaded_categories.add("schemas")

        state.reset()

        assert state.loaded_categories == set()

    def test_reset_clears_tools(self) -> None:
        state = DynamicToolsState()
        state.tools.append({"name": "test_tool"})

        state.reset()

        assert state.tools == []

    def test_loaded_categories_is_mutable(self) -> None:
        """Test that loaded_categories can be modified."""
        state = DynamicToolsState()
        state.loaded_categories.add("queues")
        assert "queues" in state.loaded_categories

    def test_tools_is_mutable(self) -> None:
        """Test that tools list can be modified."""
        state = DynamicToolsState()
        state.tools.append({"name": "test"})
        assert len(state.tools) == 1


class TestContextHoldsDynamicToolsState:
    """Tests that AgentContext properly holds DynamicToolsState."""

    def test_new_context_has_empty_state(self) -> None:
        ctx = AgentContext()
        assert ctx.dynamic_tools.loaded_categories == set()
        assert ctx.dynamic_tools.tools == []
        assert ctx.dynamic_tools.loaded_skills == set()
        assert ctx.dynamic_tools.version == 0

    def test_set_context_isolates_state(self) -> None:
        """Different contexts have independent DynamicToolsState."""
        ctx1 = AgentContext()
        ctx1.dynamic_tools.loaded_categories.add("queues")

        ctx2 = AgentContext()
        assert ctx2.dynamic_tools.loaded_categories == set()


class TestFetchCatalogAsync:
    """Tests for _fetch_catalog_async — source of truth for fetching + parsing."""

    def setup_method(self) -> None:
        import rossum_agent.tools.dynamic_tools as dt

        dt._catalog_cache = None

    def teardown_method(self) -> None:
        import rossum_agent.tools.dynamic_tools as dt

        dt._catalog_cache = None
        set_context(AgentContext())

    @pytest.mark.asyncio
    async def test_parses_list_result_directly(self) -> None:
        connection = AsyncMock()
        connection.call_tool.return_value = [
            {
                "name": "queues",
                "tools": [{"name": "get_queue"}, {"name": "list_queues"}],
                "keywords": ["queue", "inbox"],
            }
        ]

        result = await _fetch_catalog_async(connection)

        assert result.catalog["queues"] == {"get_queue", "list_queues"}
        assert result.keywords["queues"] == ["queue", "inbox"]
        assert result.write_tools == set()

    @pytest.mark.asyncio
    async def test_parses_json_string_result(self) -> None:
        import json

        connection = AsyncMock()
        connection.call_tool.return_value = json.dumps(
            [{"name": "schemas", "tools": [{"name": "get_schema"}], "keywords": ["schema"]}]
        )

        result = await _fetch_catalog_async(connection)

        assert result.catalog["schemas"] == {"get_schema"}

    @pytest.mark.asyncio
    async def test_parses_wrapped_result(self) -> None:
        connection = AsyncMock()
        connection.call_tool.return_value = {
            "result": [{"name": "hooks", "tools": [{"name": "get_hook"}], "keywords": ["hook", "extension"]}]
        }

        result = await _fetch_catalog_async(connection)

        assert result.catalog["hooks"] == {"get_hook"}

    @pytest.mark.asyncio
    async def test_parses_double_wrapped_json_string(self) -> None:
        import json

        connection = AsyncMock()
        inner_list = [{"name": "users", "tools": [{"name": "list_users"}], "keywords": ["user"]}]
        connection.call_tool.return_value = {"result": json.dumps(inner_list)}

        result = await _fetch_catalog_async(connection)

        assert "users" in result.catalog

    @pytest.mark.asyncio
    async def test_handles_missing_keywords(self) -> None:
        connection = AsyncMock()
        connection.call_tool.return_value = [{"name": "rules", "tools": [{"name": "get_rule"}]}]

        result = await _fetch_catalog_async(connection)

        assert result.keywords["rules"] == []

    @pytest.mark.asyncio
    async def test_caches_result(self) -> None:
        connection = AsyncMock()
        connection.call_tool.return_value = [{"name": "queues", "tools": [{"name": "get_queue"}], "keywords": []}]

        await _fetch_catalog_async(connection)
        await _fetch_catalog_async(connection)

        assert connection.call_tool.call_count == 1

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self) -> None:
        connection = AsyncMock()
        connection.call_tool.side_effect = Exception("Network error")

        result = await _fetch_catalog_async(connection)

        assert result.catalog == {}
        assert result.keywords == {}
        assert result.write_tools == set()


class TestFetchCatalogFromMcp:
    """Tests for the sync wrapper _fetch_catalog_from_mcp."""

    def setup_method(self) -> None:
        import rossum_agent.tools.dynamic_tools as dt

        dt._catalog_cache = None

    def teardown_method(self) -> None:
        import rossum_agent.tools.dynamic_tools as dt

        dt._catalog_cache = None
        set_context(AgentContext())

    def test_returns_empty_when_no_connection(self) -> None:
        set_context(AgentContext(mcp_connection=None, mcp_event_loop=MagicMock()))

        result = _fetch_catalog_from_mcp()

        assert result == CatalogData()

    def test_returns_empty_when_no_event_loop(self) -> None:
        set_context(AgentContext(mcp_connection=MagicMock(), mcp_event_loop=None))

        result = _fetch_catalog_from_mcp()

        assert result == CatalogData()

    @patch("rossum_agent.tools.dynamic_tools.asyncio.run_coroutine_threadsafe")
    def test_delegates_to_async(self, mock_run_coro: MagicMock) -> None:
        """Sync wrapper schedules the async fetch on the MCP event loop."""
        set_context(AgentContext(mcp_connection=MagicMock(), mcp_event_loop=MagicMock()))

        expected = CatalogData(catalog={"queues": {"get_queue"}}, keywords={"queues": []}, write_tools=set())
        mock_future = MagicMock()
        mock_future.result.return_value = expected
        mock_run_coro.return_value = mock_future

        result = _fetch_catalog_from_mcp()

        # The coroutine returned by _fetch_catalog_async was scheduled via run_coroutine_threadsafe.
        # Close it to avoid "coroutine was never awaited" warnings.
        scheduled_coro = mock_run_coro.call_args.args[0]
        scheduled_coro.close()

        assert result is expected
        mock_run_coro.assert_called_once()

    def test_returns_cached_result_without_scheduling(self) -> None:
        """When cache is populated, sync wrapper returns it without touching the event loop."""
        import rossum_agent.tools.dynamic_tools as dt

        cached = CatalogData(catalog={"queues": {"get_queue"}}, keywords={"queues": []}, write_tools=set())
        dt._catalog_cache = cached
        set_context(AgentContext(mcp_connection=MagicMock(), mcp_event_loop=MagicMock()))

        with patch("rossum_agent.tools.dynamic_tools.asyncio.run_coroutine_threadsafe") as mock_run_coro:
            result = _fetch_catalog_from_mcp()

        assert result is cached
        mock_run_coro.assert_not_called()


class TestGetLoadToolDefinition:
    """Tests for get_load_tool_definition function."""

    def test_returns_valid_tool_definition(self) -> None:
        definition = get_load_tool_definition()
        assert definition["name"] == "load_tool"
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["input_schema"]["properties"]["tool_names"]["type"] == "array"
        assert "required" in definition["input_schema"]
        assert "tool_names" in definition["input_schema"]["required"]


class TestLoadToolsByName:
    """Tests for load_tool function."""

    def test_returns_error_when_no_mcp_connection(self) -> None:
        reset_dynamic_tools()
        set_context(AgentContext(mcp_connection=None))
        try:
            result = load_tool(["delete_hook"])
            assert result == "Error: MCP connection not available"
        finally:
            set_context(AgentContext())

    def test_returns_error_when_no_event_loop(self) -> None:
        reset_dynamic_tools()
        set_context(AgentContext(mcp_connection=MagicMock(), mcp_event_loop=None))
        try:
            result = load_tool(["delete_hook"])
            assert result == "Error: MCP connection not available"
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.dynamic_tools.asyncio.run_coroutine_threadsafe")
    def test_returns_error_for_unknown_tool(self, mock_run_coro: MagicMock) -> None:
        reset_dynamic_tools()
        set_context(AgentContext(mcp_connection=MagicMock(), mcp_event_loop=MagicMock()))
        try:
            mock_tool = MagicMock()
            mock_tool.name = "get_queue"
            mock_future = MagicMock()
            mock_future.result.return_value = [mock_tool]
            mock_run_coro.return_value = mock_future

            result = load_tool(["nonexistent_tool"])
            assert "Error: Unknown tools" in result
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.dynamic_tools.mcp_tools_to_anthropic_format")
    @patch("rossum_agent.tools.dynamic_tools.asyncio.run_coroutine_threadsafe")
    def test_loads_tool_by_name(
        self,
        mock_run_coro: MagicMock,
        mock_convert: MagicMock,
    ) -> None:
        reset_dynamic_tools()
        set_context(AgentContext(mcp_connection=MagicMock(), mcp_event_loop=MagicMock(), mcp_mode="read-write"))
        try:
            mock_tool = MagicMock()
            mock_tool.name = "delete_hook"
            mock_future = MagicMock()
            mock_future.result.return_value = [mock_tool]
            mock_run_coro.return_value = mock_future

            mock_convert.return_value = [{"name": "delete_hook"}]

            result = load_tool(["delete_hook"])

            assert "Loaded tools: delete_hook" in result
            assert len(get_dynamic_tools()) == 1
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.dynamic_tools.asyncio.run_coroutine_threadsafe")
    def test_returns_already_loaded_message(self, mock_run_coro: MagicMock) -> None:
        reset_dynamic_tools()
        set_context(AgentContext(mcp_connection=MagicMock(), mcp_event_loop=MagicMock(), mcp_mode="read-write"))
        try:
            mock_tool = MagicMock()
            mock_tool.name = "delete_hook"
            mock_future = MagicMock()
            mock_future.result.return_value = [mock_tool]
            mock_run_coro.return_value = mock_future

            # Manually add tool to loaded state
            get_context().dynamic_tools.tools.append({"name": "delete_hook"})

            result = load_tool(["delete_hook"])
            assert result == "Tools already loaded: ['delete_hook']"
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.dynamic_tools.get_write_tools")
    @patch("rossum_agent.tools.dynamic_tools.asyncio.run_coroutine_threadsafe")
    def test_blocks_write_tools_in_read_only_mode(
        self,
        mock_run_coro: MagicMock,
        mock_get_write: MagicMock,
    ) -> None:
        reset_dynamic_tools()
        set_context(AgentContext(mcp_connection=MagicMock(), mcp_event_loop=MagicMock(), mcp_mode="read-only"))
        try:
            mock_get_write.return_value = {"create_hook", "delete_schema"}

            mock_tool1 = MagicMock()
            mock_tool1.name = "create_hook"
            mock_tool2 = MagicMock()
            mock_tool2.name = "get_schema"
            mock_future = MagicMock()
            mock_future.result.return_value = [mock_tool1, mock_tool2]
            mock_run_coro.return_value = mock_future

            result = load_tool(["create_hook"])

            assert "Error: Write tools not available in read-only mode" in result
            assert "create_hook" in result
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.dynamic_tools.mcp_tools_to_anthropic_format")
    @patch("rossum_agent.tools.dynamic_tools.asyncio.run_coroutine_threadsafe")
    def test_allows_write_tools_in_read_write_mode(
        self,
        mock_run_coro: MagicMock,
        mock_convert: MagicMock,
    ) -> None:
        reset_dynamic_tools()
        set_context(AgentContext(mcp_connection=MagicMock(), mcp_event_loop=MagicMock(), mcp_mode="read-write"))
        try:
            mock_tool = MagicMock()
            mock_tool.name = "create_hook"
            mock_future = MagicMock()
            mock_future.result.return_value = [mock_tool]
            mock_run_coro.return_value = mock_future

            mock_convert.return_value = [{"name": "create_hook"}]

            result = load_tool(["create_hook"])

            assert "Loaded tools: create_hook" in result
        finally:
            set_context(AgentContext())


class TestGetWriteTools:
    """Tests for get_write_tools function."""

    def setup_method(self) -> None:
        import rossum_agent.tools.dynamic_tools as dt

        dt._catalog_cache = None

    def teardown_method(self) -> None:
        import rossum_agent.tools.dynamic_tools as dt

        dt._catalog_cache = None

    @patch("rossum_agent.tools.dynamic_tools._fetch_catalog_from_mcp")
    def test_returns_write_tools_from_catalog(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = CatalogData(
            catalog={"schemas": {"get_schema", "create_hook"}},
            keywords={"schemas": ["schema"]},
            write_tools={"create_hook"},
        )

        result = get_write_tools()

        assert result == {"create_hook", DELETE_TOOL_NAME}

    @patch("rossum_agent.tools.dynamic_tools._fetch_catalog_from_mcp")
    def test_always_includes_unified_delete_tool(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = CatalogData(
            catalog={"schemas": {"get_schema", "list_schemas"}},
            keywords={"schemas": ["schema"]},
            write_tools=set(),
        )

        result = get_write_tools()

        assert result == {DELETE_TOOL_NAME}

    @patch("rossum_agent.tools.dynamic_tools._fetch_catalog_from_mcp")
    def test_does_not_mutate_cached_write_tools(self, mock_fetch: MagicMock) -> None:
        """Ensure the unified delete tool is not added back into the cached set."""
        cached = CatalogData(write_tools={"create_hook"})
        mock_fetch.return_value = cached

        get_write_tools()

        assert cached.write_tools == {"create_hook"}


class TestGetWriteToolsAsync:
    """Tests for get_write_tools_async function."""

    def setup_method(self) -> None:
        import rossum_agent.tools.dynamic_tools as dt

        dt._catalog_cache = None

    def teardown_method(self) -> None:
        import rossum_agent.tools.dynamic_tools as dt

        dt._catalog_cache = None

    @pytest.mark.asyncio
    async def test_always_includes_unified_delete_tool(self) -> None:
        mock_connection = AsyncMock()
        with patch(
            "rossum_agent.tools.dynamic_tools._fetch_catalog_async",
            AsyncMock(return_value=CatalogData(catalog={}, keywords={}, write_tools=set())),
        ):
            result = await get_write_tools_async(mock_connection)
        assert DELETE_TOOL_NAME in result

    @pytest.mark.asyncio
    async def test_includes_catalog_write_tools_plus_delete(self) -> None:
        mock_connection = AsyncMock()
        with patch(
            "rossum_agent.tools.dynamic_tools._fetch_catalog_async",
            AsyncMock(
                return_value=CatalogData(
                    catalog={"schemas": {"create_hook", "get_schema"}},
                    keywords={},
                    write_tools={"create_hook"},
                )
            ),
        ):
            result = await get_write_tools_async(mock_connection)
        assert result == {"create_hook", DELETE_TOOL_NAME}


class TestFetchCatalogParsesWriteTools:
    """Tests for catalog parsing of the read_only field."""

    def setup_method(self) -> None:
        import rossum_agent.tools.dynamic_tools as dt

        dt._catalog_cache = None

    def teardown_method(self) -> None:
        import rossum_agent.tools.dynamic_tools as dt

        dt._catalog_cache = None
        set_context(AgentContext())

    @pytest.mark.asyncio
    async def test_parses_write_tools_from_read_only_field(self) -> None:
        connection = AsyncMock()
        connection.call_tool.return_value = [
            {
                "name": "schemas",
                "tools": [
                    {"name": "get_schema", "read_only": True},
                    {"name": "create_hook", "read_only": False},
                    {"name": "update_schema", "read_only": False},
                ],
                "keywords": ["schema"],
            }
        ]

        result = await _fetch_catalog_async(connection)

        assert result.catalog["schemas"] == {"get_schema", "create_hook", "update_schema"}
        assert result.write_tools == {"create_hook", "update_schema"}

    @pytest.mark.asyncio
    async def test_defaults_to_read_only_when_field_missing(self) -> None:
        connection = AsyncMock()
        connection.call_tool.return_value = [
            {
                "name": "schemas",
                "tools": [{"name": "get_schema"}, {"name": "list_schemas"}],
                "keywords": ["schema"],
            }
        ]

        result = await _fetch_catalog_async(connection)

        assert result.write_tools == set()


class TestLoadCategoriesImplReadOnlyMode:
    """Tests for _load_categories_impl filtering write tools in read-only mode."""

    @patch("rossum_agent.tools.dynamic_tools.mcp_tools_to_anthropic_format")
    @patch("rossum_agent.tools.dynamic_tools.asyncio.run_coroutine_threadsafe")
    @patch("rossum_agent.tools.dynamic_tools.get_write_tools")
    @patch("rossum_agent.tools.dynamic_tools.get_category_tool_names")
    def test_excludes_write_tools_in_read_only_mode(
        self,
        mock_get_catalog: MagicMock,
        mock_get_write: MagicMock,
        mock_run_coro: MagicMock,
        mock_convert: MagicMock,
    ) -> None:
        reset_dynamic_tools()
        mock_get_catalog.return_value = {"schemas": {"get_schema", "list_schemas", "create_hook", "update_queue"}}
        mock_get_write.return_value = {"create_hook", "update_queue"}
        set_context(AgentContext(mcp_connection=MagicMock(), mcp_event_loop=MagicMock(), mcp_mode="read-only"))
        try:
            mock_tool1 = MagicMock()
            mock_tool1.name = "get_schema"
            mock_tool2 = MagicMock()
            mock_tool2.name = "list_schemas"
            mock_tool3 = MagicMock()
            mock_tool3.name = "create_hook"
            mock_tool4 = MagicMock()
            mock_tool4.name = "update_queue"
            mock_future = MagicMock()
            mock_future.result.return_value = [mock_tool1, mock_tool2, mock_tool3, mock_tool4]
            mock_run_coro.return_value = mock_future

            mock_convert.return_value = [{"name": "get_schema"}, {"name": "list_schemas"}]

            result = _load_categories_impl(["schemas"])

            assert "Loaded" in result
            assert "(read-only mode)" in result
            call_args = mock_convert.call_args[0][0]
            tool_names_loaded = {t.name for t in call_args}
            assert "create_hook" not in tool_names_loaded
            assert "update_queue" not in tool_names_loaded
            assert "get_schema" in tool_names_loaded
            assert "list_schemas" in tool_names_loaded
        finally:
            set_context(AgentContext())

    @patch("rossum_agent.tools.dynamic_tools.mcp_tools_to_anthropic_format")
    @patch("rossum_agent.tools.dynamic_tools.asyncio.run_coroutine_threadsafe")
    @patch("rossum_agent.tools.dynamic_tools.get_write_tools")
    @patch("rossum_agent.tools.dynamic_tools.get_category_tool_names")
    def test_includes_write_tools_in_read_write_mode(
        self,
        mock_get_catalog: MagicMock,
        mock_get_write: MagicMock,
        mock_run_coro: MagicMock,
        mock_convert: MagicMock,
    ) -> None:
        reset_dynamic_tools()
        mock_get_catalog.return_value = {"schemas": {"get_schema", "create_hook"}}
        mock_get_write.return_value = {"create_hook"}
        set_context(AgentContext(mcp_connection=MagicMock(), mcp_event_loop=MagicMock(), mcp_mode="read-write"))
        try:
            mock_tool1 = MagicMock()
            mock_tool1.name = "get_schema"
            mock_tool2 = MagicMock()
            mock_tool2.name = "create_hook"
            mock_future = MagicMock()
            mock_future.result.return_value = [mock_tool1, mock_tool2]
            mock_run_coro.return_value = mock_future

            mock_convert.return_value = [{"name": "get_schema"}, {"name": "create_hook"}]

            result = _load_categories_impl(["schemas"])

            assert "Loaded" in result
            assert "(read-only mode)" not in result
            call_args = mock_convert.call_args[0][0]
            tool_names_loaded = {t.name for t in call_args}
            assert "create_hook" in tool_names_loaded
            assert "get_schema" in tool_names_loaded
        finally:
            set_context(AgentContext())
