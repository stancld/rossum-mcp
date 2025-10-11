from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch

from rossum_mcp.server import RossumMCPServer

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def mock_env_vars(monkeypatch: MonkeyPatch) -> None:
    """Set up environment variables for testing."""
    monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai")
    monkeypatch.setenv("ROSSUM_API_TOKEN", "test-token-123")


@pytest.fixture
def mock_rossum_client() -> Iterator[Mock]:
    """Create a mock Rossum API client."""
    with patch("rossum_mcp.server.SyncRossumAPIClient") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def server(mock_env_vars: None, mock_rossum_client: Mock) -> RossumMCPServer:
    """Create a RossumMCPServer instance for testing."""
    return RossumMCPServer()


@pytest.mark.unit
class TestRossumMCPServerInit:
    """Tests for RossumMCPServer initialization."""

    def test_init_reads_env_vars(self, mock_env_vars: None, mock_rossum_client: Mock) -> None:
        """Test that __init__ reads environment variables correctly."""
        server = RossumMCPServer()
        assert server.base_url == "https://api.test.rossum.ai"
        assert server.api_token == "test-token-123"

    def test_init_creates_client(self, mock_env_vars: None, mock_rossum_client: Mock) -> None:
        """Test that __init__ creates a Rossum API client."""
        server = RossumMCPServer()
        assert server.client == mock_rossum_client

    def test_init_missing_env_vars(self, monkeypatch: MonkeyPatch) -> None:
        """Test that __init__ fails if environment variables are missing."""
        with pytest.raises(KeyError):
            RossumMCPServer()


@pytest.mark.unit
class TestUploadDocument:
    """Tests for document upload functionality."""

    def test_upload_document_sync_success(self, server: RossumMCPServer, tmp_path: Path) -> None:
        """Test successful document upload."""
        # Create a test file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        # Mock the upload response
        mock_task = Mock()
        mock_task.id = 12345
        mock_task.status = "importing"
        server.client.upload_document.return_value = [mock_task]

        # Call the sync method
        result = server._upload_document_sync(str(test_file), 100)

        # Verify the result
        assert result["task_id"] == 12345
        assert result["task_status"] == "importing"
        assert result["queue_id"] == 100
        assert "list_annotations" in result["message"]

        # Verify the client was called correctly
        server.client.upload_document.assert_called_once()
        call_args = server.client.upload_document.call_args
        assert call_args[0][0] == 100
        assert len(call_args[0][1]) == 1
        assert call_args[0][1][0][0] == str(test_file)
        assert call_args[0][1][0][1] == "test.pdf"

    def test_upload_document_sync_file_not_found(self, server: RossumMCPServer) -> None:
        """Test upload fails when file doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            server._upload_document_sync("/nonexistent/file.pdf", 100)
        assert "File not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_document_async(self, server: RossumMCPServer, tmp_path: Path) -> None:
        """Test async wrapper for document upload."""
        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        mock_task = Mock()
        mock_task.id = 12345
        mock_task.status = "importing"
        server.client.upload_document.return_value = [mock_task]

        result = await server.upload_document(str(test_file), 100)

        assert result["task_id"] == 12345
        assert result["queue_id"] == 100


@pytest.mark.unit
class TestGetAnnotation:
    """Tests for annotation retrieval functionality."""

    def test_get_annotation_sync_success(self, server: RossumMCPServer) -> None:
        """Test successful annotation retrieval."""
        # Mock the annotation response
        mock_annotation = Mock()
        mock_annotation.id = 67890
        mock_annotation.status = "confirmed"
        mock_annotation.url = "https://api.test.rossum.ai/v1/annotations/67890"
        mock_annotation.schema = "https://api.test.rossum.ai/v1/schemas/1"
        mock_annotation.modifier = "https://api.test.rossum.ai/v1/users/1"
        mock_annotation.document = "https://api.test.rossum.ai/v1/documents/1"
        mock_annotation.content = [{"schema_id": "field1", "value": "test"}]
        mock_annotation.created_at = "2025-01-01T00:00:00Z"
        mock_annotation.modified_at = "2025-01-02T00:00:00Z"

        server.client.retrieve_annotation.return_value = mock_annotation

        # Call the sync method
        result = server._get_annotation_sync(67890, sideloads=["content"])

        # Verify the result
        assert result["id"] == 67890
        assert result["status"] == "confirmed"
        assert result["url"] == mock_annotation.url
        assert result["content"] == mock_annotation.content

        # Verify the client was called correctly
        server.client.retrieve_annotation.assert_called_once_with(67890, ["content"])

    def test_get_annotation_sync_no_sideloads(self, server: RossumMCPServer) -> None:
        """Test annotation retrieval without sideloads."""
        mock_annotation = Mock()
        mock_annotation.id = 67890
        mock_annotation.status = "to_review"
        mock_annotation.url = "https://api.test.rossum.ai/v1/annotations/67890"
        mock_annotation.schema = "https://api.test.rossum.ai/v1/schemas/1"
        mock_annotation.modifier = None
        mock_annotation.document = "https://api.test.rossum.ai/v1/documents/1"
        mock_annotation.content = None
        mock_annotation.created_at = "2025-01-01T00:00:00Z"
        mock_annotation.modified_at = "2025-01-02T00:00:00Z"

        server.client.retrieve_annotation.return_value = mock_annotation

        result = server._get_annotation_sync(67890, sideloads=())

        assert result["id"] == 67890
        assert result["content"] is None
        server.client.retrieve_annotation.assert_called_once_with(67890, ())

    @pytest.mark.asyncio
    async def test_get_annotation_async(self, server: RossumMCPServer) -> None:
        """Test async wrapper for annotation retrieval."""
        mock_annotation = Mock()
        mock_annotation.id = 67890
        mock_annotation.status = "confirmed"
        mock_annotation.url = "https://api.test.rossum.ai/v1/annotations/67890"
        mock_annotation.schema = "https://api.test.rossum.ai/v1/schemas/1"
        mock_annotation.modifier = None
        mock_annotation.document = "https://api.test.rossum.ai/v1/documents/1"
        mock_annotation.content = []
        mock_annotation.created_at = "2025-01-01T00:00:00Z"
        mock_annotation.modified_at = "2025-01-02T00:00:00Z"

        server.client.retrieve_annotation.return_value = mock_annotation

        result = await server.get_annotation(67890, sideloads=["content"])

        assert result["id"] == 67890


@pytest.mark.unit
class TestListAnnotations:
    """Tests for listing annotations functionality."""

    def test_list_annotations_sync_success(self, server: RossumMCPServer) -> None:
        """Test successful annotations listing."""
        # Mock the annotations response
        mock_ann1 = Mock()
        mock_ann1.id = 1
        mock_ann1.status = "confirmed"
        mock_ann1.url = "https://api.test.rossum.ai/v1/annotations/1"
        mock_ann1.document = "https://api.test.rossum.ai/v1/documents/1"
        mock_ann1.created_at = "2025-01-01T00:00:00Z"
        mock_ann1.modified_at = "2025-01-02T00:00:00Z"

        mock_ann2 = Mock()
        mock_ann2.id = 2
        mock_ann2.status = "to_review"
        mock_ann2.url = "https://api.test.rossum.ai/v1/annotations/2"
        mock_ann2.document = "https://api.test.rossum.ai/v1/documents/2"
        mock_ann2.created_at = "2025-01-03T00:00:00Z"
        mock_ann2.modified_at = "2025-01-04T00:00:00Z"

        server.client.list_annotations.return_value = iter([mock_ann1, mock_ann2])

        # Call the sync method
        result = server._list_annotations_sync(100, status="confirmed,to_review")

        # Verify the result
        assert result["count"] == 2
        assert len(result["results"]) == 2
        assert result["results"][0]["id"] == 1
        assert result["results"][0]["status"] == "confirmed"
        assert result["results"][1]["id"] == 2
        assert result["results"][1]["status"] == "to_review"

        # Verify the client was called correctly
        server.client.list_annotations.assert_called_once_with(queue=100, page_size=100, status="confirmed,to_review")

    def test_list_annotations_sync_no_status_filter(self, server: RossumMCPServer) -> None:
        """Test annotations listing without status filter."""
        server.client.list_annotations.return_value = iter([])

        result = server._list_annotations_sync(100, status=None)

        assert result["count"] == 0
        assert result["results"] == []
        server.client.list_annotations.assert_called_once_with(queue=100, page_size=100)

    @pytest.mark.asyncio
    async def test_list_annotations_async(self, server: RossumMCPServer) -> None:
        """Test async wrapper for listing annotations."""
        mock_ann = Mock()
        mock_ann.id = 1
        mock_ann.status = "confirmed"
        mock_ann.url = "https://api.test.rossum.ai/v1/annotations/1"
        mock_ann.document = "https://api.test.rossum.ai/v1/documents/1"
        mock_ann.created_at = "2025-01-01T00:00:00Z"
        mock_ann.modified_at = "2025-01-02T00:00:00Z"

        server.client.list_annotations.return_value = iter([mock_ann])

        result = await server.list_annotations(100)

        assert result["count"] == 1


@pytest.mark.unit
class TestGetQueue:
    """Tests for queue retrieval functionality."""

    def test_get_queue_sync_success(self, server: RossumMCPServer) -> None:
        """Test successful queue retrieval."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.url = "https://api.test.rossum.ai/v1/queues/100"
        mock_queue.schema = "https://api.test.rossum.ai/v1/schemas/50"
        mock_queue.workspace = "https://api.test.rossum.ai/v1/workspaces/1"
        mock_queue.inbox = "https://api.test.rossum.ai/v1/inboxes/10"
        mock_queue.created_at = "2025-01-01T00:00:00Z"
        mock_queue.modified_at = "2025-01-02T00:00:00Z"

        server.client.retrieve_queue.return_value = mock_queue

        result = server._get_queue_sync(100)

        assert result["id"] == 100
        assert result["name"] == "Test Queue"
        assert result["schema_id"] == mock_queue.schema
        assert result["workspace"] == mock_queue.workspace

        server.client.retrieve_queue.assert_called_once_with(100)

    @pytest.mark.asyncio
    async def test_get_queue_async(self, server: RossumMCPServer) -> None:
        """Test async wrapper for queue retrieval."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.url = "https://api.test.rossum.ai/v1/queues/100"
        mock_queue.schema = "https://api.test.rossum.ai/v1/schemas/50"
        mock_queue.workspace = "https://api.test.rossum.ai/v1/workspaces/1"
        mock_queue.inbox = "https://api.test.rossum.ai/v1/inboxes/10"
        mock_queue.created_at = "2025-01-01T00:00:00Z"
        mock_queue.modified_at = "2025-01-02T00:00:00Z"

        server.client.retrieve_queue.return_value = mock_queue

        result = await server.get_queue(100)

        assert result["id"] == 100


@pytest.mark.unit
class TestGetSchema:
    """Tests for schema retrieval functionality."""

    def test_get_schema_sync_success(self, server: RossumMCPServer) -> None:
        """Test successful schema retrieval."""
        mock_schema = Mock()
        mock_schema.id = 50
        mock_schema.name = "Test Schema"
        mock_schema.url = "https://api.test.rossum.ai/v1/schemas/50"
        mock_schema.content = [{"id": "field1", "label": "Field 1", "type": "string"}]

        server.client.retrieve_schema.return_value = mock_schema

        result = server._get_schema_sync(50)

        assert result["id"] == 50
        assert result["name"] == "Test Schema"
        assert result["content"] == mock_schema.content

        server.client.retrieve_schema.assert_called_once_with(50)

    @pytest.mark.asyncio
    async def test_get_schema_async(self, server: RossumMCPServer) -> None:
        """Test async wrapper for schema retrieval."""
        mock_schema = Mock()
        mock_schema.id = 50
        mock_schema.name = "Test Schema"
        mock_schema.url = "https://api.test.rossum.ai/v1/schemas/50"
        mock_schema.content = []

        server.client.retrieve_schema.return_value = mock_schema

        result = await server.get_schema(50)

        assert result["id"] == 50


@pytest.mark.unit
class TestGetQueueSchema:
    """Tests for combined queue and schema retrieval functionality."""

    def test_get_queue_schema_sync_success(self, server: RossumMCPServer) -> None:
        """Test successful queue schema retrieval."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.schema = "https://api.test.rossum.ai/v1/schemas/50"

        mock_schema = Mock()
        mock_schema.id = 50
        mock_schema.name = "Test Schema"
        mock_schema.url = "https://api.test.rossum.ai/v1/schemas/50"
        mock_schema.content = [{"id": "field1", "label": "Field 1"}]

        server.client.retrieve_queue.return_value = mock_queue
        server.client.retrieve_schema.return_value = mock_schema

        result = server._get_queue_schema_sync(100)

        assert result["queue_id"] == 100
        assert result["queue_name"] == "Test Queue"
        assert result["schema_id"] == 50
        assert result["schema_name"] == "Test Schema"
        assert result["schema_content"] == mock_schema.content

        server.client.retrieve_queue.assert_called_once_with(100)
        server.client.retrieve_schema.assert_called_once_with(50)

    def test_get_queue_schema_sync_with_trailing_slash(self, server: RossumMCPServer) -> None:
        """Test queue schema retrieval with trailing slash in schema URL."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.schema = "https://api.test.rossum.ai/v1/schemas/50/"

        mock_schema = Mock()
        mock_schema.id = 50
        mock_schema.name = "Test Schema"
        mock_schema.url = "https://api.test.rossum.ai/v1/schemas/50"
        mock_schema.content = []

        server.client.retrieve_queue.return_value = mock_queue
        server.client.retrieve_schema.return_value = mock_schema

        result = server._get_queue_schema_sync(100)

        assert result["schema_id"] == 50
        server.client.retrieve_schema.assert_called_once_with(50)

    @pytest.mark.asyncio
    async def test_get_queue_schema_async(self, server: RossumMCPServer) -> None:
        """Test async wrapper for queue schema retrieval."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.schema = "https://api.test.rossum.ai/v1/schemas/50"

        mock_schema = Mock()
        mock_schema.id = 50
        mock_schema.name = "Test Schema"
        mock_schema.url = "https://api.test.rossum.ai/v1/schemas/50"
        mock_schema.content = []

        server.client.retrieve_queue.return_value = mock_queue
        server.client.retrieve_schema.return_value = mock_schema

        result = await server.get_queue_schema(100)

        assert result["queue_id"] == 100
        assert result["schema_id"] == 50


@pytest.mark.unit
class TestMCPHandlers:
    """Tests for MCP protocol handlers."""

    def test_server_initialization(self, server: RossumMCPServer) -> None:
        """Test that the MCP server is properly initialized."""
        assert server.server is not None
        assert server.server.name == "rossum-mcp-server"

    def test_handlers_registered(self, server: RossumMCPServer) -> None:
        """Test that handlers are registered with the server."""
        # Verify the server has request handlers registered
        assert hasattr(server.server, "request_handlers")
        assert len(server.server.request_handlers) > 0
