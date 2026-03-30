"""Tests for rossum_mcp.tools.get.handler — unified get + search tools."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from conftest import (
    create_mock_annotation,
    create_mock_email_template,
    create_mock_engine,
    create_mock_hook,
    create_mock_queue,
    create_mock_rule,
    create_mock_schema,
    create_mock_workspace,
)
from fastmcp.exceptions import ToolError
from rossum_mcp.tools.get.handler import register_get_tools
from rossum_mcp.tools.get.registry import build_get_registry
from rossum_mcp.tools.search.models import (
    AnnotationSearch,
    DocumentRelationSearch,
    EngineSearch,
    HookSearch,
    HookTemplateSearch,
    QueueSearch,
    QueueTemplateNameSearch,
    RelationSearch,
    SchemaSearch,
    WorkspaceSearch,
)
from rossum_mcp.tools.search.registry import extract_search_kwargs

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.fixture
def mock_mcp() -> Mock:
    """Create a mock FastMCP that captures registered tools by name."""
    tools: dict = {}

    def tool_decorator(**kwargs):
        def wrapper(fn):
            tools[fn.__name__] = fn
            return fn

        return wrapper

    mcp = Mock()
    mcp.tool = tool_decorator
    mcp._tools = tools
    return mcp


@pytest.fixture
def setup_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
    monkeypatch.setenv("ROSSUM_API_TOKEN", "test-token-123")
    monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")


# ───────────────────────── Tool Registration ─────────────────────────


@pytest.mark.unit
class TestToolRegistration:
    def test_registers_get_and_search(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        register_get_tools(mock_mcp, mock_client)
        assert "get" in mock_mcp._tools
        assert "search" in mock_mcp._tools

    def test_registers_exactly_five_tools(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        register_get_tools(mock_mcp, mock_client)
        assert len(mock_mcp._tools) == 5
        assert "get_annotation_content" in mock_mcp._tools
        assert "get_schema_tree_structure" in mock_mcp._tools
        assert "get_engine_fields" in mock_mcp._tools


# ───────────────────────── GET Routing ─────────────────────────


@pytest.mark.unit
class TestGetRouting:
    @pytest.mark.asyncio
    async def test_get_queue(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_queue = create_mock_queue(id=42, name="My Queue")
        mock_client.retrieve_queue.return_value = mock_queue
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="queue", entity_id=42)
        assert result["entity"] == "queue"
        assert result["id"] == 42
        mock_client.retrieve_queue.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_get_schema(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_schema = create_mock_schema(id=10)
        mock_client.retrieve_schema.return_value = mock_schema
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="schema", entity_id=10)
        assert result["entity"] == "schema"
        assert result["id"] == 10

    @pytest.mark.asyncio
    async def test_get_hook(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_hook = create_mock_hook(id=5)
        mock_client.retrieve_hook.return_value = mock_hook
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="hook", entity_id=5)
        assert result["entity"] == "hook"
        assert result["id"] == 5
        mock_client.retrieve_hook.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_get_engine(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_engine = create_mock_engine(id=7)
        mock_client.retrieve_engine.return_value = mock_engine
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="engine", entity_id=7)
        assert result["entity"] == "engine"
        assert result["id"] == 7
        mock_client.retrieve_engine.assert_called_once_with(7)

    @pytest.mark.asyncio
    async def test_get_annotation(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_ann = create_mock_annotation(id=99)
        mock_client.retrieve_annotation.return_value = mock_ann
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="annotation", entity_id=99)
        assert result["entity"] == "annotation"
        assert result["id"] == 99
        mock_client.retrieve_annotation.assert_called_once_with(99)

    @pytest.mark.asyncio
    async def test_get_workspace(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_ws = create_mock_workspace(id=3)
        mock_client.retrieve_workspace.return_value = mock_ws
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="workspace", entity_id=3)
        assert result["entity"] == "workspace"
        assert result["id"] == 3
        mock_client.retrieve_workspace.assert_called_once_with(3)

    @pytest.mark.asyncio
    async def test_get_user(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.retrieve_user.return_value = Mock(id=8, name="Test User")
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="user", entity_id=8)
        assert result["entity"] == "user"
        assert result["id"] == 8
        mock_client.retrieve_user.assert_called_once_with(8)

    @pytest.mark.asyncio
    async def test_get_rule(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        rule = create_mock_rule(id=11, queues=["https://q/1"])
        mock_client.retrieve_rule.return_value = rule

        mock_queues = [create_mock_queue(id=1, url="https://q/1", workspace="https://w/1")]

        async def mock_fetch_all(resource, **filters):
            for item in mock_queues:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="rule", entity_id=11)
        assert result["entity"] == "rule"
        assert result["id"] == 11
        mock_client.retrieve_rule.assert_called_once_with(11)

    @pytest.mark.asyncio
    async def test_get_email_template(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        template = create_mock_email_template(id=15, queue="https://q/1")
        mock_client.retrieve_email_template.return_value = template

        mock_queues = [create_mock_queue(id=1, url="https://q/1", workspace="https://w/1")]

        async def mock_fetch_all(resource, **filters):
            for item in mock_queues:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="email_template", entity_id=15)
        assert result["entity"] == "email_template"
        assert result["id"] == 15
        mock_client.retrieve_email_template.assert_called_once_with(15)

    @pytest.mark.asyncio
    async def test_get_organization_group(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.retrieve_organization_group.return_value = Mock(id=20)
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="organization_group", entity_id=20)
        assert result["entity"] == "organization_group"
        assert result["id"] == 20
        mock_client.retrieve_organization_group.assert_called_once_with(20)

    @pytest.mark.asyncio
    async def test_get_organization_limit(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.retrieve_organization_limit.return_value = Mock(id=30)
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="organization_limit", entity_id=30)
        assert result["entity"] == "organization_limit"
        assert result["id"] == 30
        mock_client.retrieve_organization_limit.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_get_relation(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client._http_client.fetch_one.return_value = {"id": 50, "type": "edit"}
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="relation", entity_id=50)
        assert result["entity"] == "relation"
        assert result["id"] == 50

    @pytest.mark.asyncio
    async def test_get_document_relation(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.retrieve_document_relation.return_value = Mock(id=60)
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="document_relation", entity_id=60)
        assert result["entity"] == "document_relation"
        assert result["id"] == 60

    @pytest.mark.asyncio
    async def test_get_hook_secrets_keys(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client._http_client.request_json.return_value = ["SLACK_TOKEN", "API_KEY"]
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="hook_secrets_keys", entity_id=123)
        assert result["entity"] == "hook_secrets_keys"
        assert result["id"] == 123
        assert result["data"] == ["SLACK_TOKEN", "API_KEY"]
        mock_client._http_client.request_json.assert_called_once_with("GET", "hooks/123/secrets_keys")

    @pytest.mark.asyncio
    async def test_get_hook_secrets_keys_empty(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client._http_client.request_json.return_value = []
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="hook_secrets_keys", entity_id=456)
        assert result["data"] == []


# ───────────────────────── GET Batch (list[int]) ─────────────────────────


@pytest.mark.unit
class TestGetBatch:
    @pytest.mark.asyncio
    async def test_get_multiple_queues(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        q1 = create_mock_queue(id=1, name="Q1")
        q2 = create_mock_queue(id=2, name="Q2")
        mock_client.retrieve_queue.side_effect = lambda qid: {1: q1, 2: q2}[qid]
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="queue", entity_id=[1, 2])
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2
        assert result[0]["entity"] == "queue"

    @pytest.mark.asyncio
    async def test_get_single_id_returns_dict(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.retrieve_queue.return_value = create_mock_queue(id=42)
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="queue", entity_id=42)
        assert isinstance(result, dict)
        assert result["id"] == 42

    @pytest.mark.asyncio
    async def test_get_batch_with_include_related(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        q1 = create_mock_queue(id=1)
        q2 = create_mock_queue(id=2)
        mock_client.retrieve_queue.side_effect = lambda qid: {1: q1, 2: q2}[qid]

        with (
            patch("rossum_mcp.tools.get.related._get_schema_tree_structure") as mock_tree,
            patch("rossum_mcp.tools.get.related._get_queue_engine") as mock_eng,
            patch("rossum_mcp.tools.get.related._list_hooks") as mock_hooks,
        ):
            mock_tree.return_value = [{"id": "section1"}]
            mock_eng.return_value = create_mock_engine(id=10)
            mock_hooks.return_value = [create_mock_hook(id=5, name="H1", active=True)]

            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["get"](entity="queue", entity_id=[1, 2], include_related=True)

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert "_related" in item
            assert "schema_tree" in item["_related"]

    @pytest.mark.asyncio
    async def test_get_empty_list_returns_empty(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="queue", entity_id=[])
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_batch_error_entity_returns_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        register_get_tools(mock_mcp, mock_client)
        with pytest.raises(ToolError, match="does not support get"):
            await mock_mcp._tools["get"](entity="hook_log", entity_id=[1, 2])


# ───────────────────────── GET Error Cases ─────────────────────────


@pytest.mark.unit
class TestGetErrors:
    @pytest.mark.asyncio
    async def test_get_search_only_entity_returns_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        register_get_tools(mock_mcp, mock_client)
        with pytest.raises(ToolError, match="does not support get"):
            await mock_mcp._tools["get"](entity="hook_log", entity_id=1)

    @pytest.mark.asyncio
    async def test_get_unknown_entity_returns_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        register_get_tools(mock_mcp, mock_client)
        with pytest.raises(ToolError, match="Unknown entity"):
            await mock_mcp._tools["get"](entity="nonexistent", entity_id=1)


# ───────────────────────── SEARCH Routing ─────────────────────────


@pytest.mark.unit
class TestSearchRouting:
    @pytest.mark.asyncio
    async def test_search_queues(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_queue = create_mock_queue(id=1, name="Q1")
        with patch("rossum_mcp.tools.search.registry.graceful_list") as mock_gl:
            mock_gl.return_value = Mock(items=[mock_queue])
            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["search"](query=QueueSearch(workspace_id=5))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_annotations(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_ann = create_mock_annotation(id=1)
        with patch("rossum_mcp.tools.search.registry.graceful_list") as mock_gl:
            mock_gl.return_value = Mock(items=[mock_ann])
            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["search"](query=AnnotationSearch(queue_id=10))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_hooks(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_hook = create_mock_hook(id=1)
        with patch("rossum_mcp.tools.search.registry.graceful_list") as mock_gl:
            mock_gl.return_value = Mock(items=[mock_hook])
            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["search"](query=HookSearch(queue_id=5))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_engines(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_engine = create_mock_engine(id=1)
        with patch("rossum_mcp.tools.search.registry.graceful_list") as mock_gl:
            mock_gl.return_value = Mock(items=[mock_engine])
            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["search"](query=EngineSearch(engine_type="extractor"))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_schemas(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_schema = create_mock_schema(id=1)
        with patch("rossum_mcp.tools.search.registry.graceful_list") as mock_gl:
            mock_gl.return_value = Mock(items=[mock_schema])
            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["search"](query=SchemaSearch(name="Test"))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_workspaces(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_ws = create_mock_workspace(id=1)
        with patch("rossum_mcp.tools.search.registry.graceful_list") as mock_gl:
            mock_gl.return_value = Mock(items=[mock_ws])
            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["search"](query=WorkspaceSearch(organization_id=1))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_first_n_passes_max_items(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        mock_queue = create_mock_queue(id=1, name="Q1")
        with patch("rossum_mcp.tools.search.registry.graceful_list") as mock_gl:
            mock_gl.return_value = Mock(items=[mock_queue])
            register_get_tools(mock_mcp, mock_client)
            await mock_mcp._tools["search"](query=QueueSearch(workspace_id=5), first_n=3)
        mock_gl.assert_called_once()
        assert mock_gl.call_args.kwargs.get("max_items") == 3


# ───────────────────────── include_related ─────────────────────────


@pytest.mark.unit
class TestIncludeRelated:
    @pytest.mark.asyncio
    async def test_get_queue_include_related(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_queue = create_mock_queue(id=42)
        mock_client.retrieve_queue.return_value = mock_queue

        mock_schema = create_mock_schema(id=1)
        mock_client.retrieve_schema.return_value = mock_schema

        mock_engine = create_mock_engine(id=1)
        mock_client.retrieve_engine.return_value = mock_engine

        mock_hook = create_mock_hook(id=1, name="Hook 1", active=True)

        with (
            patch("rossum_mcp.tools.get.related._get_schema_tree_structure") as mock_tree,
            patch("rossum_mcp.tools.get.related._get_queue_engine") as mock_eng,
            patch("rossum_mcp.tools.get.related._list_hooks") as mock_hooks,
        ):
            mock_tree.return_value = [{"id": "section1"}]
            mock_eng.return_value = mock_engine
            mock_hooks.return_value = [mock_hook]

            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["get"](entity="queue", entity_id=42, include_related=True)

        assert "_related" in result
        assert "schema_tree" in result["_related"]
        assert "engine" in result["_related"]
        assert "hooks" in result["_related"]
        assert result["_related"]["hooks_count"] == 1

    @pytest.mark.asyncio
    async def test_include_related_false_no_extra_fetches(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        mock_queue = create_mock_queue(id=42)
        mock_client.retrieve_queue.return_value = mock_queue

        with patch("rossum_mcp.tools.get.related.fetch_related") as mock_fetch:
            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["get"](entity="queue", entity_id=42, include_related=False)

        mock_fetch.assert_not_called()
        assert "_related" not in result

    @pytest.mark.asyncio
    async def test_include_related_on_entity_without_related(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        mock_client.retrieve_user.return_value = Mock(id=1, name="Test")
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="user", entity_id=1, include_related=True)
        assert "_related" not in result


# ───────────────────────── extract_search_kwargs ─────────────────────────


@pytest.mark.unit
class TestExtractSearchKwargs:
    def test_strips_entity_field(self) -> None:
        query = QueueSearch(workspace_id=5, name="test")
        kwargs = extract_search_kwargs(query)
        assert "entity" not in kwargs
        assert kwargs["workspace_id"] == 5
        assert kwargs["name"] == "test"

    def test_strips_none_values(self) -> None:
        query = HookSearch(queue_id=10)
        kwargs = extract_search_kwargs(query)
        assert "active" not in kwargs
        assert kwargs["queue_id"] == 10

    def test_annotation_keeps_required_field(self) -> None:
        query = AnnotationSearch(queue_id=100)
        kwargs = extract_search_kwargs(query)
        assert kwargs["queue_id"] == 100
        # Default status should be included since it's not None
        assert "status" in kwargs

    def test_hook_template_returns_empty(self) -> None:
        query = HookTemplateSearch()
        kwargs = extract_search_kwargs(query)
        assert kwargs == {}

    def test_queue_template_name_returns_empty(self) -> None:
        query = QueueTemplateNameSearch()
        kwargs = extract_search_kwargs(query)
        assert kwargs == {}


# ───────────────────────── Registry ─────────────────────────


@pytest.mark.unit
class TestRegistry:
    def test_all_entities_in_registry(self, mock_client: AsyncMock, setup_env: None) -> None:
        registry = build_get_registry(mock_client)
        expected = {
            "queue",
            "schema",
            "hook",
            "engine",
            "rule",
            "user",
            "workspace",
            "email_template",
            "organization_group",
            "organization_limit",
            "annotation",
            "relation",
            "document_relation",
            "hook_log",
            "hook_template",
            "user_role",
            "queue_template_name",
            "hook_secrets_keys",
        }
        assert set(registry.keys()) == expected

    def test_search_only_entities_have_no_retrieve(self, mock_client: AsyncMock, setup_env: None) -> None:
        registry = build_get_registry(mock_client)
        for entity_name in ("hook_log", "hook_template", "user_role", "queue_template_name"):
            assert registry[entity_name].retrieve_fn is None
            assert registry[entity_name].search_fn is not None

    def test_get_only_entity_has_no_search(self, mock_client: AsyncMock, setup_env: None) -> None:
        registry = build_get_registry(mock_client)
        assert registry["organization_limit"].search_fn is None
        assert registry["organization_limit"].retrieve_fn is not None


# ───────────────────────── SEARCH Error Cases ─────────────────────────


@pytest.mark.unit
class TestSearchErrors:
    @pytest.mark.asyncio
    async def test_search_unknown_entity_returns_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        register_get_tools(mock_mcp, mock_client)
        # organization_limit has no search_fn
        from rossum_mcp.tools.search.models import BaseModel

        class FakeSearch(BaseModel):
            entity: str = "organization_limit"

        # Build a query that mimics searching organization_limit
        registry = build_get_registry(mock_client)
        config = registry["organization_limit"]
        assert config.search_fn is None


# ───────────────────────── SEARCH Relations ─────────────────────────


@pytest.mark.unit
class TestSearchRelations:
    @pytest.mark.asyncio
    async def test_search_relations(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        with patch("rossum_mcp.tools.search.registry.graceful_list") as mock_gl:
            mock_gl.return_value = Mock(items=[Mock(id=1, type="edit")])
            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["search"](query=RelationSearch(type="edit"))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_document_relations(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        with patch("rossum_mcp.tools.search.registry.graceful_list") as mock_gl:
            mock_gl.return_value = Mock(items=[Mock(id=10, type="line_items")])
            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["search"](query=DocumentRelationSearch(type="line_items"))
        assert len(result) == 1


# ───────────────────────── include_related: schema ─────────────────────────


@pytest.mark.unit
class TestIncludeRelatedSchema:
    @pytest.mark.asyncio
    async def test_get_schema_include_related(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_schema = create_mock_schema(id=10)
        mock_client.retrieve_schema.return_value = mock_schema

        mock_queue = create_mock_queue(id=1, name="Q1")
        mock_rule = Mock(spec=["id", "name", "enabled"])
        mock_rule.id = 5
        mock_rule.name = "Rule 1"
        mock_rule.enabled = True

        with (
            patch("rossum_mcp.tools.get.related.graceful_list") as mock_gl,
        ):
            # First call returns queues, second returns rules
            mock_gl.side_effect = [
                Mock(items=[mock_queue]),
                Mock(items=[mock_rule]),
            ]
            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["get"](entity="schema", entity_id=10, include_related=True)

        assert "_related" in result
        assert "queues" in result["_related"]
        assert "rules" in result["_related"]
        assert len(result["_related"]["rules"]) == 1
        assert result["_related"]["rules"][0]["name"] == "Rule 1"


# ───────────────────────── include_related: hook ─────────────────────────


@pytest.mark.unit
class TestIncludeRelatedHook:
    @pytest.mark.asyncio
    async def test_get_hook_include_related_reuses_prefetched_hook(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        hook = create_mock_hook(id=5, queues=["https://q/1"], events=["annotation_status"])
        mock_client.retrieve_hook.return_value = hook

        mock_queues = [create_mock_queue(id=1, url="https://q/1", workspace="https://w/1")]

        async def mock_fetch_all(resource, **filters):
            for item in mock_queues:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="hook", entity_id=5, include_related=True)

        assert "_related" in result
        assert result["_related"]["queues"] == ["https://q/1"]
        assert result["_related"]["events"] == ["annotation_status"]
        # Should NOT call retrieve_hook a second time — the already-fetched object is reused
        mock_client.retrieve_hook.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_get_hook_include_related_with_empty_queues(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        hook = create_mock_hook(id=5, queues=[], events=[])
        mock_client.retrieve_hook.return_value = hook
        register_get_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get"](entity="hook", entity_id=5, include_related=True)

        assert result["_related"]["queues"] == []
        assert result["_related"]["events"] == []


# ───────────────────────── include_related: queue error handling ─────────────────────────


@pytest.mark.unit
class TestIncludeRelatedQueueErrors:
    @pytest.mark.asyncio
    async def test_partial_failure_still_returns_successful_related(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        mock_queue = create_mock_queue(id=42)
        mock_client.retrieve_queue.return_value = mock_queue

        mock_hook = create_mock_hook(id=1, name="Hook 1", active=True)

        with (
            patch("rossum_mcp.tools.get.related._get_schema_tree_structure") as mock_tree,
            patch("rossum_mcp.tools.get.related._get_queue_engine") as mock_eng,
            patch("rossum_mcp.tools.get.related._list_hooks") as mock_hooks,
        ):
            mock_tree.side_effect = RuntimeError("Schema tree failed")
            mock_eng.return_value = create_mock_engine(id=10)
            mock_hooks.return_value = [mock_hook]

            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["get"](entity="queue", entity_id=42, include_related=True)

        related = result["_related"]
        assert "schema_tree" not in related
        assert "engine" in related
        assert "hooks" in related
        assert related["hooks_count"] == 1

    @pytest.mark.asyncio
    async def test_all_related_fail_returns_empty_related(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        mock_queue = create_mock_queue(id=42)
        mock_client.retrieve_queue.return_value = mock_queue

        with (
            patch("rossum_mcp.tools.get.related._get_schema_tree_structure") as mock_tree,
            patch("rossum_mcp.tools.get.related._get_queue_engine") as mock_eng,
            patch("rossum_mcp.tools.get.related._list_hooks") as mock_hooks,
        ):
            mock_tree.side_effect = RuntimeError("fail")
            mock_eng.side_effect = RuntimeError("fail")
            mock_hooks.side_effect = RuntimeError("fail")

            register_get_tools(mock_mcp, mock_client)
            result = await mock_mcp._tools["get"](entity="queue", entity_id=42, include_related=True)

        # Empty dict from _fetch_queue_related is falsy, so _related is not set
        assert "_related" not in result or result["_related"] == {}
