"""Tests for rossum_mcp.tools.update.hooks module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_hook, create_mock_queue
from fastmcp.exceptions import ToolError
from rossum_api.domain_logic.resources import Resource
from rossum_mcp.tools.search.registry import _list_hooks
from rossum_mcp.tools.update.hooks import (
    _generate_hook_payload,
    register_hook_tools,
)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.fixture
def mock_mcp() -> Mock:
    """Create a mock FastMCP instance that captures registered tools."""
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


@pytest.mark.unit
class TestUpdateHook:
    """Tests for update_hook tool."""

    @pytest.mark.asyncio
    async def test_update_hook_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful hook update."""
        register_hook_tools(mock_mcp, mock_client)

        existing_hook = create_mock_hook(
            id=100,
            name="Old Name",
            queues=["https://api.test.rossum.ai/v1/queues/1"],
            events=["annotation_content.initialize"],
            config={"runtime": "python3.12"},
        )
        mock_client.retrieve_hook.return_value = existing_hook

        updated_hook = create_mock_hook(id=100, name="New Name")
        mock_client.update_part_hook.return_value = updated_hook

        update_hook = mock_mcp._tools["update_hook"]
        result = await update_hook(hook_id=100, name="New Name")

        assert result.id == 100
        assert result.name == "New Name"
        mock_client.retrieve_hook.assert_called_once_with(100)
        mock_client.update_part_hook.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_hook_with_all_fields(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test hook update with all optional fields."""
        register_hook_tools(mock_mcp, mock_client)

        existing_hook = create_mock_hook(id=100, name="Old Name", config=None)
        mock_client.retrieve_hook.return_value = existing_hook

        updated_hook = create_mock_hook(id=100, name="Updated")
        mock_client.update_part_hook.return_value = updated_hook

        update_hook = mock_mcp._tools["update_hook"]
        result = await update_hook(
            hook_id=100,
            name="Updated",
            queues=["https://api.test.rossum.ai/v1/queues/2"],
            events=["annotation_content.export"],
            config={"new": "config"},
            settings={"setting": "value"},
            active=False,
            secrets={"slack_token": "xoxb-456"},
            token_owner="https://api.test.rossum.ai/v1/users/42",
            run_after=["https://api.test.rossum.ai/v1/hooks/99"],
        )

        assert result.id == 100
        call_args = mock_client.update_part_hook.call_args[0][1]
        assert call_args["name"] == "Updated"
        assert call_args["queues"] == ["https://api.test.rossum.ai/v1/queues/2"]
        assert call_args["events"] == ["annotation_content.export"]
        assert call_args["config"] == {"new": "config"}
        assert call_args["settings"] == {"setting": "value"}
        assert call_args["active"] is False
        assert call_args["secrets"] == {"slack_token": "xoxb-456"}
        assert call_args["token_owner"] == "https://api.test.rossum.ai/v1/users/42"
        assert call_args["run_after"] == ["https://api.test.rossum.ai/v1/hooks/99"]

    @pytest.mark.asyncio
    async def test_update_hook_with_sideload(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test hook update with sideload parameter."""
        register_hook_tools(mock_mcp, mock_client)

        existing_hook = create_mock_hook(id=100, name="Old Name", config=None)
        mock_client.retrieve_hook.return_value = existing_hook

        updated_hook = create_mock_hook(id=100, name="Old Name")
        mock_client.update_part_hook.return_value = updated_hook

        update_hook = mock_mcp._tools["update_hook"]
        result = await update_hook(
            hook_id=100,
            sideload=["schemas", "queues"],
        )

        assert result.id == 100
        call_args = mock_client.update_part_hook.call_args[0][1]
        assert call_args["sideload"] == ["schemas", "queues"]


@pytest.mark.unit
class TestTestHook:
    """Tests for test_hook tool."""

    @pytest.mark.asyncio
    async def test_test_hook_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful hook test execution with auto-resolved annotation."""
        register_hook_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=123, queues=["https://api.test.rossum.ai/v1/queues/100"])
        mock_client.retrieve_hook.return_value = mock_hook

        mock_annotation = Mock()
        mock_annotation.url = "https://api.test.rossum.ai/v1/annotations/789"

        async def mock_list_all(**kwargs):
            yield mock_annotation

        mock_client.list_annotations = mock_list_all

        generated_payload = {"payload": {"annotation": {}}}
        test_response = {"response": {"status_code": 200}}
        mock_client._http_client.request_json.side_effect = [generated_payload, test_response]

        test_hook = mock_mcp._tools["test_hook"]
        result = await test_hook(hook_id=123, event="annotation_content", action="initialize")

        assert result == {"response": {"status_code": 200}}
        assert mock_client._http_client.request_json.call_count == 2
        mock_client._http_client.request_json.assert_any_call(
            "POST",
            "hooks/123/generate_payload",
            json={
                "event": "annotation_content",
                "action": "initialize",
                "annotation": "https://api.test.rossum.ai/v1/annotations/789",
                "status": "to_review",
                "previous_status": "importing",
            },
        )
        mock_client._http_client.request_json.assert_any_call(
            "POST",
            "hooks/123/test",
            json={"payload": generated_payload},
        )

    @pytest.mark.asyncio
    async def test_test_hook_with_config(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test hook test with optional config override."""
        register_hook_tools(mock_mcp, mock_client)

        generated_payload = {"payload": {"annotation": {"id": 456}}}
        test_response = {"response": {"status_code": 200}}
        mock_client._http_client.request_json.side_effect = [generated_payload, test_response]

        test_hook = mock_mcp._tools["test_hook"]
        result = await test_hook(
            hook_id=123,
            event="annotation_content",
            action="initialize",
            annotation="https://api.test.rossum.ai/v1/annotations/456",
            status="confirmed",
            previous_status="to_review",
            config={"timeout_s": 30},
        )

        assert result == {"response": {"status_code": 200}}
        mock_client._http_client.request_json.assert_any_call(
            "POST",
            "hooks/123/test",
            json={
                "payload": generated_payload,
                "config": {"timeout_s": 30},
            },
        )


@pytest.mark.unit
class TestGenerateHookPayload:
    """Tests for _generate_hook_payload internal function."""

    @pytest.mark.asyncio
    async def test_generate_payload_auto_resolves_annotation(self, mock_client: AsyncMock) -> None:
        """Test that annotation_content events auto-resolve annotation and status from hook's queues."""
        mock_hook = create_mock_hook(id=123, queues=["https://api.test.rossum.ai/v1/queues/100"])
        mock_client.retrieve_hook.return_value = mock_hook

        mock_annotation = Mock()
        mock_annotation.url = "https://api.test.rossum.ai/v1/annotations/789"

        async def mock_list_all(**kwargs):
            yield mock_annotation

        mock_client.list_annotations = mock_list_all
        mock_client._http_client.request_json.return_value = {"payload": {"annotation": {}}}

        result = await _generate_hook_payload(
            mock_client, hook_id=123, event="annotation_content", action="initialize"
        )

        assert "payload" in result
        mock_client._http_client.request_json.assert_called_once_with(
            "POST",
            "hooks/123/generate_payload",
            json={
                "event": "annotation_content",
                "action": "initialize",
                "annotation": "https://api.test.rossum.ai/v1/annotations/789",
                "status": "to_review",
                "previous_status": "importing",
            },
        )

    @pytest.mark.asyncio
    async def test_generate_payload_with_explicit_annotation(self, mock_client: AsyncMock) -> None:
        """Test payload generation with explicitly provided annotation URL."""
        mock_client._http_client.request_json.return_value = {"payload": {"annotation": {"id": 456}}}

        result = await _generate_hook_payload(
            mock_client,
            hook_id=123,
            event="annotation_content",
            action="initialize",
            annotation="https://api.test.rossum.ai/v1/annotations/456",
            status="confirmed",
            previous_status="to_review",
        )

        assert "payload" in result
        mock_client._http_client.request_json.assert_called_once_with(
            "POST",
            "hooks/123/generate_payload",
            json={
                "event": "annotation_content",
                "action": "initialize",
                "annotation": "https://api.test.rossum.ai/v1/annotations/456",
                "status": "confirmed",
                "previous_status": "to_review",
            },
        )

    @pytest.mark.asyncio
    async def test_generate_payload_no_annotations_found(self, mock_client: AsyncMock) -> None:
        """Test error when no annotations found on hook's queues."""
        mock_hook = create_mock_hook(id=123, queues=["https://api.test.rossum.ai/v1/queues/100"])
        mock_client.retrieve_hook.return_value = mock_hook

        async def mock_list_empty(**kwargs):
            return
            yield

        mock_client.list_annotations = mock_list_empty

        with pytest.raises(ToolError, match="requires an annotation"):
            await _generate_hook_payload(mock_client, hook_id=123, event="annotation_content", action="initialize")

    @pytest.mark.asyncio
    async def test_generate_payload_non_annotation_event(self, mock_client: AsyncMock) -> None:
        """Test that non-annotation events skip auto-resolution."""
        mock_client._http_client.request_json.return_value = {"payload": {}}

        result = await _generate_hook_payload(mock_client, hook_id=123, event="invocation", action="scheduled")

        assert "payload" in result
        mock_client._http_client.request_json.assert_called_once_with(
            "POST",
            "hooks/123/generate_payload",
            json={"event": "invocation", "action": "scheduled"},
        )


@pytest.mark.unit
class TestListHooks:
    """Tests for _list_hooks workspace resolution."""

    @pytest.mark.asyncio
    async def test_list_hooks_resolves_workspaces(self, mock_client: AsyncMock) -> None:
        """Test that workspace URLs are resolved from queue data."""
        mock_hooks = [
            create_mock_hook(
                id=1,
                name="Hook 1",
                queues=[
                    "https://api.test.rossum.ai/v1/queues/10",
                    "https://api.test.rossum.ai/v1/queues/20",
                ],
            ),
            create_mock_hook(
                id=2,
                name="Hook 2",
                queues=["https://api.test.rossum.ai/v1/queues/20"],
            ),
        ]
        mock_queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
            create_mock_queue(
                id=20,
                url="https://api.test.rossum.ai/v1/queues/20",
                workspace="https://api.test.rossum.ai/v1/workspaces/200",
            ),
        ]

        async def mock_cursor_fetch_all(resource, **filters):
            items = mock_hooks if resource == Resource.Hook else mock_queues
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_hooks(mock_client)

        assert len(result) == 2
        assert sorted(result[0].workspaces) == [
            "https://api.test.rossum.ai/v1/workspaces/100",
            "https://api.test.rossum.ai/v1/workspaces/200",
        ]
        assert result[1].workspaces == ["https://api.test.rossum.ai/v1/workspaces/200"]

    @pytest.mark.asyncio
    async def test_list_hooks_empty_workspaces_when_no_queues(self, mock_client: AsyncMock) -> None:
        """Test that workspaces is empty when hook has no queues."""
        mock_hooks = [create_mock_hook(id=1, name="Hook 1", queues=[])]

        async def mock_cursor_fetch_all(resource, **filters):
            for hook in mock_hooks:
                yield hook

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_hooks(mock_client)

        assert len(result) == 1
        assert result[0].workspaces == []

    @pytest.mark.asyncio
    async def test_list_hooks_filter_by_workspace_id(self, mock_client: AsyncMock) -> None:
        """Test that workspace_id filters hooks to those belonging to the workspace."""
        mock_hooks = [
            create_mock_hook(
                id=1,
                name="Hook A",
                queues=["https://api.test.rossum.ai/v1/queues/10"],
            ),
            create_mock_hook(
                id=2,
                name="Hook B",
                queues=["https://api.test.rossum.ai/v1/queues/20"],
            ),
            create_mock_hook(
                id=3,
                name="Hook C",
                queues=[
                    "https://api.test.rossum.ai/v1/queues/10",
                    "https://api.test.rossum.ai/v1/queues/20",
                ],
            ),
        ]
        mock_queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
            create_mock_queue(
                id=20,
                url="https://api.test.rossum.ai/v1/queues/20",
                workspace="https://api.test.rossum.ai/v1/workspaces/200",
            ),
        ]

        async def mock_cursor_fetch_all(resource, **filters):
            items = mock_hooks if resource == Resource.Hook else mock_queues
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_hooks(mock_client, workspace_id=100)

        assert len(result) == 2
        assert {h.id for h in result} == {1, 3}

    @pytest.mark.asyncio
    async def test_list_hooks_filter_by_workspace_id_no_match(self, mock_client: AsyncMock) -> None:
        """Test that workspace_id returns empty list when no hooks belong to the workspace."""
        mock_hooks = [
            create_mock_hook(
                id=1,
                name="Hook A",
                queues=["https://api.test.rossum.ai/v1/queues/10"],
            ),
        ]
        mock_queues = [
            create_mock_queue(
                id=10,
                url="https://api.test.rossum.ai/v1/queues/10",
                workspace="https://api.test.rossum.ai/v1/workspaces/100",
            ),
        ]

        async def mock_cursor_fetch_all(resource, **filters):
            items = mock_hooks if resource == Resource.Hook else mock_queues
            for item in items:
                yield item

        mock_client._http_client.cursor_fetch_all = mock_cursor_fetch_all

        result = await _list_hooks(mock_client, workspace_id=999)

        assert len(result) == 0
