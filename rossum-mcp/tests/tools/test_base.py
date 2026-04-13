"""Tests for rossum_mcp.tools.base module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.domain_logic.resources import Resource
from rossum_mcp.tools.base import (
    filter_by_workspace_id,
    resolve_workspace_from_queue,
    resolve_workspaces_from_queues,
)


@pytest.mark.unit
class TestBuildResourceUrl:
    """Tests for build_resource_url function."""

    def test_build_resource_url_with_base_url(self) -> None:
        from rossum_mcp.tools.base import build_resource_url

        result = build_resource_url("https://api.test.rossum.ai/v1", "queues", 123)
        assert result == "https://api.test.rossum.ai/v1/queues/123"

    def test_build_resource_url_different_resources(self) -> None:
        from rossum_mcp.tools.base import build_resource_url

        base = "https://api.test.rossum.ai/v1"
        assert build_resource_url(base, "schemas", 456) == "https://api.test.rossum.ai/v1/schemas/456"
        assert build_resource_url(base, "workspaces", 789) == "https://api.test.rossum.ai/v1/workspaces/789"


@pytest.mark.unit
class TestExtractIdFromUrl:
    """Tests for extract_id_from_url function."""

    def test_extract_id_from_url(self) -> None:
        from rossum_mcp.tools.base import extract_id_from_url

        assert extract_id_from_url("https://api.test.rossum.ai/v1/queues/123") == 123

    def test_extract_id_from_url_trailing_slash(self) -> None:
        from rossum_mcp.tools.base import extract_id_from_url

        assert extract_id_from_url("https://api.test.rossum.ai/v1/queues/123/") == 123

    def test_extract_id_from_url_invalid(self) -> None:
        from rossum_mcp.tools.base import extract_id_from_url

        with pytest.raises(ValueError, match="Cannot extract resource ID"):
            extract_id_from_url("not-a-url")


@pytest.mark.unit
class TestDeleteResource:
    """Tests for delete_resource function."""

    @pytest.mark.asyncio
    async def test_delete_resource_success(self) -> None:
        from rossum_mcp.tools.base import delete_resource

        mock_delete_fn = AsyncMock()
        result = await delete_resource("queue", 123, mock_delete_fn)

        assert result == {"message": "Queue 123 deleted successfully"}
        mock_delete_fn.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_delete_resource_custom_message(self) -> None:
        from rossum_mcp.tools.base import delete_resource

        mock_delete_fn = AsyncMock()
        result = await delete_resource("queue", 123, mock_delete_fn, "Queue 123 scheduled for deletion")

        assert result == {"message": "Queue 123 scheduled for deletion"}

    @pytest.mark.asyncio
    async def test_delete_resource_propagates_exception(self) -> None:
        from rossum_mcp.tools.base import delete_resource

        mock_delete_fn = AsyncMock(side_effect=ValueError("Not Found"))
        with pytest.raises(ValueError, match="Not Found"):
            await delete_resource("queue", 99999, mock_delete_fn)


@pytest.mark.unit
class TestGracefulList:
    """Tests for graceful_list function."""

    @pytest.mark.asyncio
    async def test_graceful_list_success(self) -> None:
        """Test graceful_list returns all items when none are broken."""
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()
        client._deserializer = Mock(side_effect=lambda r, raw: raw)

        async def mock_cursor_fetch_all(resource, **filters):
            for item in [{"id": 1, "name": "item1"}, {"id": 2, "name": "item2"}]:
                yield item

        client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await graceful_list(client, Resource.Queue, "queue")
        assert len(result.items) == 2
        assert len(result.skipped_ids) == 0
        assert result.skipped_ids == []

    @pytest.mark.asyncio
    async def test_graceful_list_skips_broken_items(self) -> None:
        """Test graceful_list skips items that fail deserialization."""
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()

        def mock_deserializer(resource, raw):
            if raw.get("id") == 2:
                raise ValueError("broken item")
            return raw

        client._deserializer = mock_deserializer

        async def mock_cursor_fetch_all(resource, **filters):
            for item in [{"id": 1, "name": "ok"}, {"id": 2, "name": "broken"}, {"id": 3, "name": "ok2"}]:
                yield item

        client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await graceful_list(client, Resource.Queue, "queue")
        assert len(result.items) == 2
        assert len(result.skipped_ids) == 1
        assert result.skipped_ids == [2]

    @pytest.mark.asyncio
    async def test_graceful_list_respects_max_items(self) -> None:
        """Test graceful_list respects max_items limit (counting only successful items)."""
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()

        def mock_deserializer(resource, raw):
            if raw.get("id") == 1:
                raise ValueError("broken")
            return raw

        client._deserializer = mock_deserializer

        async def mock_cursor_fetch_all(resource, **filters):
            for item in [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]:
                yield item

        client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await graceful_list(client, Resource.Queue, "queue", max_items=2)
        assert len(result.items) == 2
        assert result.items[0]["id"] == 2
        assert result.items[1]["id"] == 3
        assert len(result.skipped_ids) == 1
        assert result.skipped_ids == [1]

    @pytest.mark.asyncio
    async def test_graceful_list_passes_filters(self) -> None:
        """Test graceful_list passes filters to cursor_fetch_all."""
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()
        client._deserializer = Mock(side_effect=lambda r, raw: raw)

        received_filters = {}

        async def mock_cursor_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            return
            yield

        client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        await graceful_list(client, Resource.Queue, "queue", workspace=5, name="Test")
        assert received_filters == {"workspace": 5, "name": "Test"}

    @pytest.mark.asyncio
    async def test_graceful_list_all_broken(self) -> None:
        """Test graceful_list returns empty when all items fail deserialization."""
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()
        client._deserializer = Mock(side_effect=ValueError("broken"))

        async def mock_cursor_fetch_all(resource, **filters):
            for item in [{"id": 1}, {"id": 2}]:
                yield item

        client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await graceful_list(client, Resource.Queue, "queue")
        assert len(result.items) == 0
        assert len(result.skipped_ids) == 2
        assert result.skipped_ids == [1, 2]

    @pytest.mark.asyncio
    async def test_graceful_list_empty(self) -> None:
        """Test graceful_list with no items."""
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()
        client._deserializer = Mock()

        async def mock_cursor_fetch_all(resource, **filters):
            return
            yield

        client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await graceful_list(client, Resource.Queue, "queue")
        assert len(result.items) == 0
        assert len(result.skipped_ids) == 0
        assert result.skipped_ids == []

    @pytest.mark.asyncio
    async def test_graceful_list_logs_warning_for_broken_items(self, caplog) -> None:
        """Test graceful_list logs warnings for broken items."""
        import logging

        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()
        client._deserializer = Mock(side_effect=ValueError("bad data"))

        async def mock_cursor_fetch_all(resource, **filters):
            yield {"id": 42}

        client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        with caplog.at_level(logging.WARNING):
            result = await graceful_list(client, Resource.Queue, "queue")

        assert len(result.skipped_ids) == 1
        assert "Failed to deserialize queue (id=42)" in caplog.text
        assert "Skipped 1 queue item(s)" in caplog.text


@pytest.mark.unit
class TestResolveWorkspacesFromQueues:
    """Tests for resolve_workspaces_from_queues function."""

    def test_resolves_all_queues(self) -> None:
        queue_workspace_map = {
            "https://api.rossum.ai/v1/queues/1": "https://api.rossum.ai/v1/workspaces/10",
            "https://api.rossum.ai/v1/queues/2": "https://api.rossum.ai/v1/workspaces/20",
        }
        result = resolve_workspaces_from_queues(
            ["https://api.rossum.ai/v1/queues/1", "https://api.rossum.ai/v1/queues/2"], queue_workspace_map
        )
        assert sorted(result) == [
            "https://api.rossum.ai/v1/workspaces/10",
            "https://api.rossum.ai/v1/workspaces/20",
        ]

    def test_deduplicates_workspaces(self) -> None:
        queue_workspace_map = {
            "https://api.rossum.ai/v1/queues/1": "https://api.rossum.ai/v1/workspaces/10",
            "https://api.rossum.ai/v1/queues/2": "https://api.rossum.ai/v1/workspaces/10",
        }
        result = resolve_workspaces_from_queues(
            ["https://api.rossum.ai/v1/queues/1", "https://api.rossum.ai/v1/queues/2"], queue_workspace_map
        )
        assert result == ["https://api.rossum.ai/v1/workspaces/10"]

    def test_skips_unknown_queues(self) -> None:
        queue_workspace_map = {
            "https://api.rossum.ai/v1/queues/1": "https://api.rossum.ai/v1/workspaces/10",
        }
        result = resolve_workspaces_from_queues(
            ["https://api.rossum.ai/v1/queues/1", "https://api.rossum.ai/v1/queues/999"], queue_workspace_map
        )
        assert result == ["https://api.rossum.ai/v1/workspaces/10"]

    def test_empty_queue_list(self) -> None:
        result = resolve_workspaces_from_queues([], {"q1": "w1"})
        assert result == []

    def test_empty_map(self) -> None:
        result = resolve_workspaces_from_queues(["https://api.rossum.ai/v1/queues/1"], {})
        assert result == []


@pytest.mark.unit
class TestResolveWorkspaceFromQueue:
    """Tests for resolve_workspace_from_queue function."""

    def test_returns_workspace_when_found(self) -> None:
        queue_workspace_map = {
            "https://api.rossum.ai/v1/queues/1": "https://api.rossum.ai/v1/workspaces/10",
        }
        assert resolve_workspace_from_queue("https://api.rossum.ai/v1/queues/1", queue_workspace_map) == (
            "https://api.rossum.ai/v1/workspaces/10"
        )

    def test_returns_none_when_not_found(self) -> None:
        assert resolve_workspace_from_queue("https://api.rossum.ai/v1/queues/999", {}) is None

    def test_returns_none_when_queue_url_is_none(self) -> None:
        assert resolve_workspace_from_queue(None, {"q1": "w1"}) is None

    def test_returns_none_for_none_with_empty_map(self) -> None:
        assert resolve_workspace_from_queue(None, {}) is None


@pytest.mark.unit
class TestFilterByWorkspaceId:
    """Tests for filter_by_workspace_id function."""

    def test_returns_all_items_when_workspace_id_is_none(self) -> None:
        items = [Mock(workspaces=["https://api.rossum.ai/v1/workspaces/10"])]
        assert filter_by_workspace_id(items, None) is items

    def test_filters_by_workspace_id(self) -> None:
        item_match = Mock(workspaces=["https://api.rossum.ai/v1/workspaces/10"])
        item_no_match = Mock(workspaces=["https://api.rossum.ai/v1/workspaces/20"])
        result = filter_by_workspace_id([item_match, item_no_match], 10)
        assert result == [item_match]

    def test_filters_items_with_multiple_workspaces(self) -> None:
        item = Mock(workspaces=["https://api.rossum.ai/v1/workspaces/10", "https://api.rossum.ai/v1/workspaces/20"])
        assert filter_by_workspace_id([item], 20) == [item]

    def test_excludes_items_without_workspaces_attr(self) -> None:
        item = Mock(spec=[])  # no attributes at all
        assert filter_by_workspace_id([item], 10) == []

    def test_excludes_items_with_empty_workspaces(self) -> None:
        item = Mock(workspaces=[])
        assert filter_by_workspace_id([item], 10) == []

    def test_excludes_items_with_none_workspaces(self) -> None:
        item = Mock(workspaces=None)
        assert filter_by_workspace_id([item], 10) == []

    def test_empty_items_list(self) -> None:
        assert filter_by_workspace_id([], 10) == []


@pytest.mark.unit
class TestGetMultiQueueUrls:
    """Tests for get_multi_queue_urls function."""

    def test_collects_urls_from_multiple_items(self) -> None:
        from rossum_mcp.tools.base import get_multi_queue_urls

        items = [
            Mock(queues=["https://api.rossum.ai/v1/queues/1", "https://api.rossum.ai/v1/queues/2"]),
            Mock(queues=["https://api.rossum.ai/v1/queues/2", "https://api.rossum.ai/v1/queues/3"]),
        ]
        result = get_multi_queue_urls(items)
        assert result == {
            "https://api.rossum.ai/v1/queues/1",
            "https://api.rossum.ai/v1/queues/2",
            "https://api.rossum.ai/v1/queues/3",
        }

    def test_empty_queues(self) -> None:
        from rossum_mcp.tools.base import get_multi_queue_urls

        items = [Mock(queues=[]), Mock(queues=[])]
        assert get_multi_queue_urls(items) == set()

    def test_empty_items(self) -> None:
        from rossum_mcp.tools.base import get_multi_queue_urls

        assert get_multi_queue_urls([]) == set()


@pytest.mark.unit
class TestGetSingleQueueUrls:
    """Tests for get_single_queue_urls function."""

    def test_collects_urls_from_multiple_items(self) -> None:
        from rossum_mcp.tools.base import get_single_queue_urls

        items = [
            Mock(queue="https://api.rossum.ai/v1/queues/1"),
            Mock(queue="https://api.rossum.ai/v1/queues/2"),
        ]
        result = get_single_queue_urls(items)
        assert result == {
            "https://api.rossum.ai/v1/queues/1",
            "https://api.rossum.ai/v1/queues/2",
        }

    def test_skips_none_queues(self) -> None:
        from rossum_mcp.tools.base import get_single_queue_urls

        items = [
            Mock(queue="https://api.rossum.ai/v1/queues/1"),
            Mock(queue=None),
            Mock(queue="https://api.rossum.ai/v1/queues/3"),
        ]
        result = get_single_queue_urls(items)
        assert result == {
            "https://api.rossum.ai/v1/queues/1",
            "https://api.rossum.ai/v1/queues/3",
        }

    def test_deduplicates(self) -> None:
        from rossum_mcp.tools.base import get_single_queue_urls

        items = [
            Mock(queue="https://api.rossum.ai/v1/queues/1"),
            Mock(queue="https://api.rossum.ai/v1/queues/1"),
        ]
        assert get_single_queue_urls(items) == {"https://api.rossum.ai/v1/queues/1"}

    def test_empty_items(self) -> None:
        from rossum_mcp.tools.base import get_single_queue_urls

        assert get_single_queue_urls([]) == set()


@pytest.mark.unit
class TestSearchWithWorkspaceResolution:
    """Tests for search_with_workspace_resolution function."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client._http_client = AsyncMock()
        client._deserializer = Mock(side_effect=lambda r, raw: raw)
        return client

    @pytest.mark.asyncio
    async def test_basic_list_enrich_and_return(self, mock_client: AsyncMock) -> None:
        from conftest import create_mock_queue, create_mock_rule
        from rossum_mcp.tools.base import get_multi_queue_urls, search_with_workspace_resolution

        mock_rules = [
            create_mock_rule(id=1, name="Rule 1", queues=["https://api.rossum.ai/v1/queues/10"]),
        ]
        mock_queues = [
            create_mock_queue(
                id=10, url="https://api.rossum.ai/v1/queues/10", workspace="https://api.rossum.ai/v1/workspaces/100"
            ),
        ]

        async def mock_cursor_fetch_all(resource, **filters):
            items = mock_rules if resource == Resource.Rule else mock_queues
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        def enrich(rule, queue_ws_map):
            return {"id": rule.id, "ws": list(queue_ws_map.values())}

        result = await search_with_workspace_resolution(
            mock_client,
            Resource.Rule,
            "rule",
            enrich=enrich,
            get_queue_urls=get_multi_queue_urls,
        )
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["ws"] == ["https://api.rossum.ai/v1/workspaces/100"]

    @pytest.mark.asyncio
    async def test_filters_by_workspace_id(self, mock_client: AsyncMock) -> None:
        from conftest import create_mock_queue, create_mock_rule
        from rossum_mcp.models.rule import Rule as McpRule
        from rossum_mcp.tools.base import (
            get_multi_queue_urls,
            resolve_workspaces_from_queues,
            search_with_workspace_resolution,
        )

        mock_rules = [
            create_mock_rule(id=1, name="R1", queues=["https://api.rossum.ai/v1/queues/10"]),
            create_mock_rule(id=2, name="R2", queues=["https://api.rossum.ai/v1/queues/20"]),
        ]
        mock_queues = [
            create_mock_queue(
                id=10, url="https://api.rossum.ai/v1/queues/10", workspace="https://api.rossum.ai/v1/workspaces/100"
            ),
            create_mock_queue(
                id=20, url="https://api.rossum.ai/v1/queues/20", workspace="https://api.rossum.ai/v1/workspaces/200"
            ),
        ]

        async def mock_cursor_fetch_all(resource, **filters):
            items = mock_rules if resource == Resource.Rule else mock_queues
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        def enrich(rule, queue_ws_map):
            return McpRule.from_base(rule, workspaces=resolve_workspaces_from_queues(rule.queues, queue_ws_map))

        result = await search_with_workspace_resolution(
            mock_client,
            Resource.Rule,
            "rule",
            enrich=enrich,
            get_queue_urls=get_multi_queue_urls,
            workspace_id=100,
        )
        assert len(result) == 1
        assert result[0].id == 1

    @pytest.mark.asyncio
    async def test_filters_by_name_regex(self, mock_client: AsyncMock) -> None:
        from conftest import create_mock_rule
        from rossum_mcp.models.rule import Rule as McpRule
        from rossum_mcp.tools.base import (
            get_multi_queue_urls,
            resolve_workspaces_from_queues,
            search_with_workspace_resolution,
        )

        mock_rules = [
            create_mock_rule(id=1, name="Invoice Rule", queues=[]),
            create_mock_rule(id=2, name="Receipt Rule", queues=[]),
            create_mock_rule(id=3, name="Invoice Validator", queues=[]),
        ]

        async def mock_cursor_fetch_all(resource, **filters):
            for item in mock_rules:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        def enrich(rule, queue_ws_map):
            return McpRule.from_base(rule, workspaces=resolve_workspaces_from_queues(rule.queues, queue_ws_map))

        result = await search_with_workspace_resolution(
            mock_client,
            Resource.Rule,
            "rule",
            enrich=enrich,
            get_queue_urls=get_multi_queue_urls,
            name="Invoice",
            use_regex=True,
        )
        assert len(result) == 2
        assert {r.id for r in result} == {1, 3}

    @pytest.mark.asyncio
    async def test_passes_filters_to_graceful_list(self, mock_client: AsyncMock) -> None:
        from rossum_mcp.tools.base import get_multi_queue_urls, search_with_workspace_resolution

        received_filters: dict = {}

        async def mock_cursor_fetch_all(resource, **filters):
            nonlocal received_filters
            if resource == Resource.Hook:
                received_filters = filters
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        await search_with_workspace_resolution(
            mock_client,
            Resource.Hook,
            "hook",
            enrich=lambda item, m: item,
            get_queue_urls=get_multi_queue_urls,
            filters={"queue": 5, "active": True},
        )
        assert received_filters == {"queue": 5, "active": True}

    @pytest.mark.asyncio
    async def test_passes_max_items(self, mock_client: AsyncMock) -> None:
        from conftest import create_mock_rule
        from rossum_mcp.tools.base import get_multi_queue_urls, search_with_workspace_resolution

        mock_rules = [create_mock_rule(id=i, name=f"Rule {i}", queues=[]) for i in range(5)]

        async def mock_cursor_fetch_all(resource, **filters):
            for item in mock_rules:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await search_with_workspace_resolution(
            mock_client,
            Resource.Rule,
            "rule",
            enrich=lambda item, m: item,
            get_queue_urls=get_multi_queue_urls,
            max_items=2,
        )
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_client: AsyncMock) -> None:
        from rossum_mcp.tools.base import get_single_queue_urls, search_with_workspace_resolution

        async def mock_cursor_fetch_all(resource, **filters):
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await search_with_workspace_resolution(
            mock_client,
            Resource.EmailTemplate,
            "email_template",
            enrich=lambda item, m: item,
            get_queue_urls=get_single_queue_urls,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_no_filters_defaults_to_empty(self, mock_client: AsyncMock) -> None:
        from rossum_mcp.tools.base import get_multi_queue_urls, search_with_workspace_resolution

        received_filters: dict = {}

        async def mock_cursor_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            return
            yield

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        await search_with_workspace_resolution(
            mock_client,
            Resource.Rule,
            "rule",
            enrich=lambda item, m: item,
            get_queue_urls=get_multi_queue_urls,
        )
        assert received_filters == {}
