"""Tests for rossum_mcp.tools.annotations module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.annotation import Annotation
from rossum_mcp.tools import base
from rossum_mcp.tools.annotations import register_annotation_tools

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch


def create_mock_annotation(**kwargs) -> Annotation:
    """Create a mock Annotation dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/annotations/1",
        "status": "to_review",
        "schema": "https://api.test.rossum.ai/v1/schemas/1",
        "modifier": None,
        "content": None,
        "queue": "https://api.test.rossum.ai/v1/queues/1",
        "creator": None,
        "created_at": "2025-01-01T00:00:00Z",
        "rir_poll_id": None,
        "email": None,
        "email_thread": None,
        "has_email_thread_with_replies": False,
        "has_email_thread_with_new_replies": False,
        "suggested_edit": None,
        "messages": [],
        "time_spent": 0,
        "relations": [],
        "pages": [],
        "document": "https://api.test.rossum.ai/v1/documents/1",
        "confirmed_at": None,
        "modified_at": "2025-01-01T00:00:00Z",
        "exported_at": None,
        "arrived_at": None,
        "assigned_at": None,
        "purged_at": None,
        "rejected_at": None,
        "deleted_at": None,
        "export_failed_at": None,
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "metadata": {},
        "automated": False,
        "automation_blocker": None,
        "related_emails": [],
        "automatically_rejected": False,
        "prediction": None,
        "assignees": [],
        "labels": [],
        "restricted_access": False,
        "training_enabled": True,
        "einvoice": None,
        "purged_by": None,
        "rejected_by": None,
        "deleted_by": None,
        "exported_by": None,
        "confirmed_by": None,
        "modified_by": None,
    }
    defaults.update(kwargs)
    return Annotation(**defaults)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    return AsyncMock()


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
class TestUploadDocument:
    """Tests for upload_document tool."""

    @pytest.mark.asyncio
    async def test_upload_document_success(
        self,
        mock_mcp: Mock,
        mock_client: AsyncMock,
        tmp_path: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test successful document upload."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_annotation_tools(mock_mcp, mock_client)

        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        mock_task = Mock()
        mock_task.id = 12345
        mock_task.status = "importing"
        mock_client.upload_document.return_value = [mock_task]

        upload_document = mock_mcp._tools["upload_document"]
        result = await upload_document(file_path=str(test_file), queue_id=100)

        assert result["task_id"] == 12345
        assert result["task_status"] == "importing"
        assert result["queue_id"] == 100
        assert "list_annotations" in result["message"]

    @pytest.mark.asyncio
    async def test_upload_document_file_not_found(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test upload fails when file doesn't exist."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_annotation_tools(mock_mcp, mock_client)

        upload_document = mock_mcp._tools["upload_document"]

        with pytest.raises(FileNotFoundError) as exc_info:
            await upload_document(file_path="/nonexistent/file.pdf", queue_id=100)

        assert "File not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_document_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test upload_document is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        register_annotation_tools(mock_mcp, mock_client)

        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        upload_document = mock_mcp._tools["upload_document"]
        result = await upload_document(file_path=str(test_file), queue_id=100)

        assert result["error"] == "upload_document is not available in read-only mode"
        mock_client.upload_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_document_key_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test upload fails when API response is missing expected key."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_annotation_tools(mock_mcp, mock_client)

        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        mock_client.upload_document.side_effect = KeyError("task")

        upload_document = mock_mcp._tools["upload_document"]

        with pytest.raises(ValueError) as exc_info:
            await upload_document(file_path=str(test_file), queue_id=100)

        assert "API response missing expected key" in str(exc_info.value)
        assert "queue_id (100)" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_document_index_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test upload fails when API returns empty list."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_annotation_tools(mock_mcp, mock_client)

        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        mock_client.upload_document.return_value = []

        upload_document = mock_mcp._tools["upload_document"]

        with pytest.raises(ValueError) as exc_info:
            await upload_document(file_path=str(test_file), queue_id=100)

        assert "no tasks were created" in str(exc_info.value)
        assert "queue_id (100)" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_document_generic_exception(
        self, mock_mcp: Mock, mock_client: AsyncMock, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test upload fails with generic exception."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_annotation_tools(mock_mcp, mock_client)

        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        mock_client.upload_document.side_effect = RuntimeError("Connection timeout")

        upload_document = mock_mcp._tools["upload_document"]

        with pytest.raises(ValueError) as exc_info:
            await upload_document(file_path=str(test_file), queue_id=100)

        assert "Document upload failed: RuntimeError: Connection timeout" in str(exc_info.value)


@pytest.mark.unit
class TestGetAnnotation:
    """Tests for get_annotation tool."""

    @pytest.mark.asyncio
    async def test_get_annotation_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful annotation retrieval."""
        register_annotation_tools(mock_mcp, mock_client)

        mock_annotation = create_mock_annotation(id=67890, status="confirmed")
        mock_client.retrieve_annotation.return_value = mock_annotation

        get_annotation = mock_mcp._tools["get_annotation"]
        result = await get_annotation(annotation_id=67890, sideloads=["content"])

        assert result.id == 67890
        assert result.status == "confirmed"
        mock_client.retrieve_annotation.assert_called_once_with(67890, ["content"])

    @pytest.mark.asyncio
    async def test_get_annotation_no_sideloads(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test annotation retrieval without sideloads."""
        register_annotation_tools(mock_mcp, mock_client)

        mock_annotation = create_mock_annotation(id=67890, status="to_review")
        mock_client.retrieve_annotation.return_value = mock_annotation

        get_annotation = mock_mcp._tools["get_annotation"]
        result = await get_annotation(annotation_id=67890, sideloads=())

        assert result.id == 67890
        mock_client.retrieve_annotation.assert_called_once_with(67890, ())


@pytest.mark.unit
class TestListAnnotations:
    """Tests for list_annotations tool."""

    @pytest.mark.asyncio
    async def test_list_annotations_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful annotations listing."""
        register_annotation_tools(mock_mcp, mock_client)

        mock_ann1 = create_mock_annotation(id=1, status="confirmed")
        mock_ann2 = create_mock_annotation(id=2, status="to_review")

        async def async_iter():
            for item in [mock_ann1, mock_ann2]:
                yield item

        mock_client.list_annotations = Mock(side_effect=lambda **kwargs: async_iter())

        list_annotations = mock_mcp._tools["list_annotations"]
        result = await list_annotations(queue_id=100, status="confirmed,to_review")

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2

    @pytest.mark.asyncio
    async def test_list_annotations_no_status_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test annotations listing without status filter."""
        register_annotation_tools(mock_mcp, mock_client)

        async def async_iter():
            return
            yield

        mock_client.list_annotations = Mock(side_effect=lambda **kwargs: async_iter())

        list_annotations = mock_mcp._tools["list_annotations"]
        result = await list_annotations(queue_id=100, status=None)

        assert len(result) == 0
        assert result == []


@pytest.mark.unit
class TestStartAnnotation:
    """Tests for start_annotation tool."""

    @pytest.mark.asyncio
    async def test_start_annotation_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful annotation start."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_annotation_tools(mock_mcp, mock_client)

        start_annotation = mock_mcp._tools["start_annotation"]
        result = await start_annotation(annotation_id=12345)

        assert result["annotation_id"] == 12345
        assert "started successfully" in result["message"]
        mock_client.start_annotation.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_start_annotation_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test start_annotation is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        register_annotation_tools(mock_mcp, mock_client)

        start_annotation = mock_mcp._tools["start_annotation"]
        result = await start_annotation(annotation_id=12345)

        assert result["error"] == "start_annotation is not available in read-only mode"
        mock_client.start_annotation.assert_not_called()


@pytest.mark.unit
class TestBulkUpdateAnnotationFields:
    """Tests for bulk_update_annotation_fields tool."""

    @pytest.mark.asyncio
    async def test_bulk_update_annotation_fields_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful bulk update of annotation fields."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_annotation_tools(mock_mcp, mock_client)

        operations = [
            {"op": "replace", "id": 1, "value": {"content": {"value": "new value"}}},
            {"op": "replace", "id": 2, "value": {"content": {"value": "another value"}}},
        ]

        bulk_update = mock_mcp._tools["bulk_update_annotation_fields"]
        result = await bulk_update(annotation_id=12345, operations=operations)

        assert result["annotation_id"] == 12345
        assert result["operations_count"] == 2
        assert "updated with 2 operations" in result["message"]
        mock_client.bulk_update_annotation_data.assert_called_once_with(12345, operations)

    @pytest.mark.asyncio
    async def test_bulk_update_annotation_fields_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test bulk_update_annotation_fields is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        register_annotation_tools(mock_mcp, mock_client)

        bulk_update = mock_mcp._tools["bulk_update_annotation_fields"]
        result = await bulk_update(annotation_id=12345, operations=[])

        assert result["error"] == "bulk_update_annotation_fields is not available in read-only mode"
        mock_client.bulk_update_annotation_data.assert_not_called()


@pytest.mark.unit
class TestConfirmAnnotation:
    """Tests for confirm_annotation tool."""

    @pytest.mark.asyncio
    async def test_confirm_annotation_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful annotation confirmation."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_annotation_tools(mock_mcp, mock_client)

        confirm_annotation = mock_mcp._tools["confirm_annotation"]
        result = await confirm_annotation(annotation_id=12345)

        assert result["annotation_id"] == 12345
        assert "confirmed successfully" in result["message"]
        mock_client.confirm_annotation.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_confirm_annotation_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test confirm_annotation is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        register_annotation_tools(mock_mcp, mock_client)

        confirm_annotation = mock_mcp._tools["confirm_annotation"]
        result = await confirm_annotation(annotation_id=12345)

        assert result["error"] == "confirm_annotation is not available in read-only mode"
        mock_client.confirm_annotation.assert_not_called()
