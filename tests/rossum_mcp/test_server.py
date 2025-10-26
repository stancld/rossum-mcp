from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from rossum_api.domain_logic.resources import Resource

from rossum_mcp.server import RossumMCPServer

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def mock_env_vars(monkeypatch: MonkeyPatch) -> None:
    """Set up environment variables for testing."""
    monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai")
    monkeypatch.setenv("ROSSUM_API_TOKEN", "test-token-123")


@pytest.fixture
def mock_rossum_client() -> Iterator[AsyncMock]:
    """Create a mock Rossum API client."""
    with patch("rossum_mcp.server.AsyncRossumAPIClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def server(mock_env_vars: None, mock_rossum_client: AsyncMock) -> RossumMCPServer:
    """Create a RossumMCPServer instance for testing."""
    return RossumMCPServer()


@pytest.mark.unit
class TestRossumMCPServerInit:
    """Tests for RossumMCPServer initialization."""

    def test_init_reads_env_vars(self, mock_env_vars: None, mock_rossum_client: AsyncMock) -> None:
        """Test that __init__ reads environment variables correctly."""
        server = RossumMCPServer()
        assert server.base_url == "https://api.test.rossum.ai"
        assert server.api_token == "test-token-123"

    def test_init_creates_client(self, mock_env_vars: None, mock_rossum_client: AsyncMock) -> None:
        """Test that __init__ creates a Rossum API client."""
        server = RossumMCPServer()
        assert server.client == mock_rossum_client

    def test_init_missing_env_vars(self, monkeypatch: MonkeyPatch) -> None:
        """Test that __init__ fails if environment variables are missing."""
        # Remove environment variables that might be set by other fixtures
        monkeypatch.delenv("ROSSUM_API_BASE_URL", raising=False)
        monkeypatch.delenv("ROSSUM_API_TOKEN", raising=False)

        with pytest.raises(KeyError):
            RossumMCPServer()


@pytest.mark.unit
class TestUploadDocument:
    """Tests for document upload functionality."""

    @pytest.mark.asyncio
    async def test_upload_document_success(self, server: RossumMCPServer, tmp_path: Path) -> None:
        """Test successful document upload."""
        # Create a test file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        # Mock the upload response
        mock_task = Mock()
        mock_task.id = 12345
        mock_task.status = "importing"
        server.client.upload_document.return_value = [mock_task]

        # Call the async method
        result = await server.upload_document(str(test_file), 100)

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

    @pytest.mark.asyncio
    async def test_upload_document_file_not_found(self, server: RossumMCPServer) -> None:
        """Test upload fails when file doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            await server.upload_document("/nonexistent/file.pdf", 100)
        assert "File not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_document_async(self, server: RossumMCPServer, tmp_path: Path) -> None:
        """Test async document upload."""
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

    @pytest.mark.asyncio
    async def test_get_annotation_success(self, server: RossumMCPServer) -> None:
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

        # Call the async method
        result = await server.get_annotation(67890, sideloads=["content"])

        # Verify the result
        assert result["id"] == 67890
        assert result["status"] == "confirmed"
        assert result["url"] == mock_annotation.url
        assert result["content"] == mock_annotation.content

        # Verify the client was called correctly
        server.client.retrieve_annotation.assert_called_once_with(67890, ["content"])

    @pytest.mark.asyncio
    async def test_get_annotation_no_sideloads(self, server: RossumMCPServer) -> None:
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

        result = await server.get_annotation(67890, sideloads=())

        assert result["id"] == 67890
        assert result["content"] is None
        server.client.retrieve_annotation.assert_called_once_with(67890, ())

    @pytest.mark.asyncio
    async def test_get_annotation_async(self, server: RossumMCPServer) -> None:
        """Test async annotation retrieval."""
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

    @pytest.mark.asyncio
    async def test_list_annotations_success(self, server: RossumMCPServer) -> None:
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

        # Create async iterator factory that returns a new generator each time
        async def async_iter():
            for item in [mock_ann1, mock_ann2]:
                yield item

        # Replace the AsyncMock method with a regular Mock that returns async iter
        server.client.list_annotations = Mock(side_effect=lambda **kwargs: async_iter())

        # Call the async method
        result = await server.list_annotations(100, status="confirmed,to_review")

        # Verify the result
        assert result["count"] == 2
        assert len(result["results"]) == 2
        assert result["results"][0]["id"] == 1
        assert result["results"][0]["status"] == "confirmed"
        assert result["results"][1]["id"] == 2
        assert result["results"][1]["status"] == "to_review"

        # Verify the client was called correctly
        server.client.list_annotations.assert_called_once_with(queue=100, page_size=100, status="confirmed,to_review")

    @pytest.mark.asyncio
    async def test_list_annotations_no_status_filter(self, server: RossumMCPServer) -> None:
        """Test annotations listing without status filter."""

        # Create empty async iterator factory
        async def async_iter():
            return
            yield  # This line never executes but makes this a generator

        # Replace the AsyncMock method with a regular Mock that returns async iter
        server.client.list_annotations = Mock(side_effect=lambda **kwargs: async_iter())

        result = await server.list_annotations(100, status=None)

        assert result["count"] == 0
        assert result["results"] == []
        server.client.list_annotations.assert_called_once_with(queue=100, page_size=100)

    @pytest.mark.asyncio
    async def test_list_annotations_async(self, server: RossumMCPServer) -> None:
        """Test async listing of annotations."""
        mock_ann = Mock()
        mock_ann.id = 1
        mock_ann.status = "confirmed"
        mock_ann.url = "https://api.test.rossum.ai/v1/annotations/1"
        mock_ann.document = "https://api.test.rossum.ai/v1/documents/1"
        mock_ann.created_at = "2025-01-01T00:00:00Z"
        mock_ann.modified_at = "2025-01-02T00:00:00Z"

        # Create async iterator factory
        async def async_iter():
            yield mock_ann

        # Replace the AsyncMock method with a regular Mock that returns async iter
        server.client.list_annotations = Mock(side_effect=lambda **kwargs: async_iter())

        result = await server.list_annotations(100)

        assert result["count"] == 1


@pytest.mark.unit
class TestGetQueue:
    """Tests for queue retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_queue_success(self, server: RossumMCPServer) -> None:
        """Test successful queue retrieval."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.url = "https://api.test.rossum.ai/v1/queues/100"
        mock_queue.schema = "https://api.test.rossum.ai/v1/schemas/50"
        mock_queue.workspace = "https://api.test.rossum.ai/v1/workspaces/1"
        mock_queue.inbox = "https://api.test.rossum.ai/v1/inboxes/10"
        mock_queue.engine = "https://api.test.rossum.ai/v1/engines/15"
        mock_queue.created_at = "2025-01-01T00:00:00Z"
        mock_queue.modified_at = "2025-01-02T00:00:00Z"

        server.client.retrieve_queue.return_value = mock_queue

        result = await server.get_queue(100)

        assert result["id"] == 100
        assert result["name"] == "Test Queue"
        assert result["schema"] == mock_queue.schema
        assert result["workspace"] == mock_queue.workspace

        server.client.retrieve_queue.assert_called_once_with(100)

    @pytest.mark.asyncio
    async def test_get_queue_async(self, server: RossumMCPServer) -> None:
        """Test async queue retrieval."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.url = "https://api.test.rossum.ai/v1/queues/100"
        mock_queue.schema = "https://api.test.rossum.ai/v1/schemas/50"
        mock_queue.workspace = "https://api.test.rossum.ai/v1/workspaces/1"
        mock_queue.inbox = "https://api.test.rossum.ai/v1/inboxes/10"
        mock_queue.engine = "https://api.test.rossum.ai/v1/engines/15"
        mock_queue.created_at = "2025-01-01T00:00:00Z"
        mock_queue.modified_at = "2025-01-02T00:00:00Z"

        server.client.retrieve_queue.return_value = mock_queue

        result = await server.get_queue(100)

        assert result["id"] == 100


@pytest.mark.unit
class TestGetSchema:
    """Tests for schema retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_schema_success(self, server: RossumMCPServer) -> None:
        """Test successful schema retrieval."""
        mock_schema = Mock()
        mock_schema.id = 50
        mock_schema.name = "Test Schema"
        mock_schema.url = "https://api.test.rossum.ai/v1/schemas/50"
        mock_schema.content = [{"id": "field1", "label": "Field 1", "type": "string"}]

        server.client.retrieve_schema.return_value = mock_schema

        result = await server.get_schema(50)

        assert result["id"] == 50
        assert result["name"] == "Test Schema"
        assert result["content"] == mock_schema.content

        server.client.retrieve_schema.assert_called_once_with(50)

    @pytest.mark.asyncio
    async def test_get_schema_async(self, server: RossumMCPServer) -> None:
        """Test async schema retrieval."""
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

    @pytest.mark.asyncio
    async def test_get_queue_schema_success(self, server: RossumMCPServer) -> None:
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

        result = await server.get_queue_schema(100)

        assert result["queue_id"] == 100
        assert result["queue_name"] == "Test Queue"
        assert result["schema_id"] == 50
        assert result["schema_name"] == "Test Schema"
        assert result["schema_content"] == mock_schema.content

        server.client.retrieve_queue.assert_called_once_with(100)
        server.client.retrieve_schema.assert_called_once_with(50)

    @pytest.mark.asyncio
    async def test_get_queue_schema_with_trailing_slash(self, server: RossumMCPServer) -> None:
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

        result = await server.get_queue_schema(100)

        assert result["schema_id"] == 50
        server.client.retrieve_schema.assert_called_once_with(50)

    @pytest.mark.asyncio
    async def test_get_queue_schema_async(self, server: RossumMCPServer) -> None:
        """Test async queue schema retrieval."""
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
class TestGetQueueEngine:
    """Tests for combined queue and engine retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_queue_engine_success(self, server: RossumMCPServer) -> None:
        """Test successful queue engine retrieval."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.engine = "https://api.test.rossum.ai/v1/engines/15"
        mock_queue.dedicated_engine = None
        mock_queue.generic_engine = None

        mock_engine = Mock()
        mock_engine.id = 15
        mock_engine.name = "Test Engine"
        mock_engine.url = "https://api.test.rossum.ai/v1/engines/15"

        server.client.retrieve_queue.return_value = mock_queue
        server.client.retrieve_engine.return_value = mock_engine

        result = await server.get_queue_engine(100)

        assert result["queue_id"] == 100
        assert result["queue_name"] == "Test Queue"
        assert result["engine_id"] == 15
        assert result["engine_name"] == "Test Engine"
        assert result["engine_type"] == "standard"

        server.client.retrieve_queue.assert_called_once_with(100)
        server.client.retrieve_engine.assert_called_once_with(15)

    @pytest.mark.asyncio
    async def test_get_queue_engine_dedicated_engine(self, server: RossumMCPServer) -> None:
        """Test queue engine retrieval with dedicated engine."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.engine = None
        mock_queue.dedicated_engine = "https://api.test.rossum.ai/v1/engines/20"
        mock_queue.generic_engine = None

        mock_engine = Mock()
        mock_engine.id = 20
        mock_engine.name = "Dedicated Engine"
        mock_engine.url = "https://api.test.rossum.ai/v1/engines/20"

        server.client.retrieve_queue.return_value = mock_queue
        server.client.retrieve_engine.return_value = mock_engine

        result = await server.get_queue_engine(100)

        assert result["engine_id"] == 20
        assert result["engine_type"] == "dedicated"
        server.client.retrieve_engine.assert_called_once_with(20)

    @pytest.mark.asyncio
    async def test_get_queue_engine_generic_engine(self, server: RossumMCPServer) -> None:
        """Test queue engine retrieval with generic engine."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.engine = None
        mock_queue.dedicated_engine = None
        mock_queue.generic_engine = "https://api.test.rossum.ai/v1/engines/25"

        mock_engine = Mock()
        mock_engine.id = 25
        mock_engine.name = "Generic Engine"
        mock_engine.url = "https://api.test.rossum.ai/v1/engines/25"

        server.client.retrieve_queue.return_value = mock_queue
        server.client.retrieve_engine.return_value = mock_engine

        result = await server.get_queue_engine(100)

        assert result["engine_id"] == 25
        assert result["engine_type"] == "generic"
        server.client.retrieve_engine.assert_called_once_with(25)

    @pytest.mark.asyncio
    async def test_get_queue_engine_no_engine(self, server: RossumMCPServer) -> None:
        """Test queue engine retrieval when no engine is assigned."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.engine = None
        mock_queue.dedicated_engine = None
        mock_queue.generic_engine = None

        server.client.retrieve_queue.return_value = mock_queue

        result = await server.get_queue_engine(100)

        assert result["queue_id"] == 100
        assert result["queue_name"] == "Test Queue"
        assert result["engine_id"] is None
        assert result["engine_name"] is None
        assert result["engine_url"] is None
        assert result["engine_type"] is None
        assert "No engine assigned" in result["message"]

        server.client.retrieve_queue.assert_called_once_with(100)
        server.client.retrieve_engine.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_queue_engine_with_trailing_slash(self, server: RossumMCPServer) -> None:
        """Test queue engine retrieval with trailing slash in engine URL."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.engine = "https://api.test.rossum.ai/v1/engines/15/"
        mock_queue.dedicated_engine = None
        mock_queue.generic_engine = None

        mock_engine = Mock()
        mock_engine.id = 15
        mock_engine.name = "Test Engine"
        mock_engine.url = "https://api.test.rossum.ai/v1/engines/15"

        server.client.retrieve_queue.return_value = mock_queue
        server.client.retrieve_engine.return_value = mock_engine

        result = await server.get_queue_engine(100)

        assert result["engine_id"] == 15
        server.client.retrieve_engine.assert_called_once_with(15)

    @pytest.mark.asyncio
    async def test_get_queue_engine_with_embedded_dict(self, server: RossumMCPServer) -> None:
        """Test queue engine retrieval when engine is embedded as a dict."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        # Engine is embedded as a dict with all required fields - no need to make additional API call
        mock_queue.engine = {
            "id": 18,
            "name": "Embedded Engine",
            "url": "https://api.test.rossum.ai/v1/engines/18",
            "type": "custom",
            "learning_enabled": True,
            "training_queues": ["https://api.test.rossum.ai/v1/queues/666"],
            "description": "Test embedded engine",
            "agenda_id": "test-agenda",
        }
        mock_queue.dedicated_engine = None
        mock_queue.generic_engine = None

        server.client.retrieve_queue.return_value = mock_queue

        result = await server.get_queue_engine(100)

        assert result["queue_id"] == 100
        assert result["queue_name"] == "Test Queue"
        assert result["engine_id"] == 18
        assert result["engine_name"] == "Embedded Engine"
        assert result["engine_url"] == "https://api.test.rossum.ai/v1/engines/18"
        assert result["engine_type"] == "standard"

        server.client.retrieve_queue.assert_called_once_with(100)
        # Should NOT call retrieve_engine since engine is embedded
        server.client.retrieve_engine.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_queue_engine_async(self, server: RossumMCPServer) -> None:
        """Test async wrapper for queue engine retrieval."""
        mock_queue = Mock()
        mock_queue.id = 100
        mock_queue.name = "Test Queue"
        mock_queue.engine = "https://api.test.rossum.ai/v1/engines/15"
        mock_queue.dedicated_engine = None
        mock_queue.generic_engine = None

        mock_engine = Mock()
        mock_engine.id = 15
        mock_engine.name = "Test Engine"
        mock_engine.url = "https://api.test.rossum.ai/v1/engines/15"

        server.client.retrieve_queue.return_value = mock_queue
        server.client.retrieve_engine.return_value = mock_engine

        result = await server.get_queue_engine(100)

        assert result["queue_id"] == 100
        assert result["engine_id"] == 15


@pytest.mark.unit
class TestCreateQueue:
    """Tests for queue creation functionality."""

    @pytest.mark.asyncio
    async def test_create_queue_success(self, server: RossumMCPServer) -> None:
        """Test successful queue creation with schema and engine."""
        # Mock the queue creation response
        mock_queue = Mock()
        mock_queue.id = 200
        mock_queue.name = "New Test Queue"
        mock_queue.url = "https://api.test.rossum.ai/v1/queues/200"
        mock_queue.workspace = "https://api.test.rossum.ai/v1/workspaces/1"
        mock_queue.schema = "https://api.test.rossum.ai/v1/schemas/50"
        mock_queue.engine = "https://api.test.rossum.ai/v1/engines/10"
        mock_queue.inbox = None
        mock_queue.connector = None
        mock_queue.locale = "en_GB"
        mock_queue.automation_enabled = True
        mock_queue.automation_level = "always"
        mock_queue.training_enabled = True

        server.client.create_new_queue.return_value = mock_queue

        # Call the async method
        result = await server.create_queue(
            name="New Test Queue",
            workspace_id=1,
            schema_id=50,
            engine_id=10,
            automation_enabled=True,
            automation_level="always",
        )

        # Verify the result
        assert result["id"] == 200
        assert result["name"] == "New Test Queue"
        assert result["schema"] == mock_queue.schema
        assert result["engine"] == mock_queue.engine
        assert result["automation_enabled"] is True
        assert result["automation_level"] == "always"
        assert "created successfully" in result["message"]

        # Verify the client was called correctly
        server.client.create_new_queue.assert_called_once()
        call_args = server.client.create_new_queue.call_args[0][0]
        assert call_args["name"] == "New Test Queue"
        assert call_args["workspace"] == "https://api.test.rossum.ai/workspaces/1"
        assert call_args["schema"] == "https://api.test.rossum.ai/schemas/50"
        assert call_args["engine"] == "https://api.test.rossum.ai/engines/10"
        assert call_args["automation_enabled"] is True
        assert call_args["automation_level"] == "always"

    @pytest.mark.asyncio
    async def test_create_queue_minimal_params(self, server: RossumMCPServer) -> None:
        """Test queue creation with minimal required parameters."""
        mock_queue = Mock()
        mock_queue.id = 201
        mock_queue.name = "Minimal Queue"
        mock_queue.url = "https://api.test.rossum.ai/v1/queues/201"
        mock_queue.workspace = "https://api.test.rossum.ai/v1/workspaces/2"
        mock_queue.schema = "https://api.test.rossum.ai/v1/schemas/60"
        mock_queue.engine = None
        mock_queue.inbox = None
        mock_queue.connector = None
        mock_queue.locale = "en_GB"
        mock_queue.automation_enabled = False
        mock_queue.automation_level = "never"
        mock_queue.training_enabled = True

        server.client.create_new_queue.return_value = mock_queue

        result = await server.create_queue(
            name="Minimal Queue",
            workspace_id=2,
            schema_id=60,
        )

        assert result["id"] == 201
        assert result["name"] == "Minimal Queue"
        assert result["engine"] is None

        call_args = server.client.create_new_queue.call_args[0][0]
        assert "engine" not in call_args  # Optional field should not be included if None
        assert call_args["automation_enabled"] is False
        assert call_args["training_enabled"] is True

    @pytest.mark.asyncio
    async def test_create_queue_with_all_options(self, server: RossumMCPServer) -> None:
        """Test queue creation with all optional parameters."""
        mock_queue = Mock()
        mock_queue.id = 202
        mock_queue.name = "Full Queue"
        mock_queue.url = "https://api.test.rossum.ai/v1/queues/202"
        mock_queue.workspace = "https://api.test.rossum.ai/v1/workspaces/3"
        mock_queue.schema = "https://api.test.rossum.ai/v1/schemas/70"
        mock_queue.engine = "https://api.test.rossum.ai/v1/engines/20"
        mock_queue.inbox = "https://api.test.rossum.ai/v1/inboxes/5"
        mock_queue.connector = "https://api.test.rossum.ai/v1/connectors/8"
        mock_queue.locale = "en_US"
        mock_queue.automation_enabled = True
        mock_queue.automation_level = "always"
        mock_queue.training_enabled = False

        server.client.create_new_queue.return_value = mock_queue

        result = await server.create_queue(
            name="Full Queue",
            workspace_id=3,
            schema_id=70,
            engine_id=20,
            inbox_id=5,
            connector_id=8,
            locale="en_US",
            automation_enabled=True,
            automation_level="always",
            training_enabled=False,
        )

        assert result["id"] == 202
        assert result["inbox"] == mock_queue.inbox
        assert result["connector"] == mock_queue.connector
        assert result["locale"] == "en_US"
        assert result["training_enabled"] is False

        call_args = server.client.create_new_queue.call_args[0][0]
        assert call_args["inbox"] == "https://api.test.rossum.ai/inboxes/5"
        assert call_args["connector"] == "https://api.test.rossum.ai/connectors/8"
        assert call_args["locale"] == "en_US"

    @pytest.mark.asyncio
    async def test_create_queue_async(self, server: RossumMCPServer) -> None:
        """Test async wrapper for queue creation."""
        mock_queue = Mock()
        mock_queue.id = 203
        mock_queue.name = "Async Queue"
        mock_queue.url = "https://api.test.rossum.ai/v1/queues/203"
        mock_queue.workspace = "https://api.test.rossum.ai/v1/workspaces/4"
        mock_queue.schema = "https://api.test.rossum.ai/v1/schemas/80"
        mock_queue.engine = "https://api.test.rossum.ai/v1/engines/30"
        mock_queue.inbox = None
        mock_queue.connector = None
        mock_queue.locale = "en_GB"
        mock_queue.automation_enabled = False
        mock_queue.automation_level = "never"
        mock_queue.training_enabled = True

        server.client.create_new_queue.return_value = mock_queue

        result = await server.create_queue(
            name="Async Queue",
            workspace_id=4,
            schema_id=80,
            engine_id=30,
        )

        assert result["id"] == 203
        assert result["name"] == "Async Queue"


@pytest.mark.unit
class TestUpdateEngine:
    """Tests for engine update functionality."""

    @pytest.mark.asyncio
    async def test_update_engine_training_queues(self, server: RossumMCPServer) -> None:
        """Test updating engine training queues."""
        # Mock the internal client update method
        mock_updated_engine_data = {
            "id": 36032,
            "url": "https://api.test.rossum.ai/v1/engines/36032",
            "name": "Test Engine",
            "type": "extractor",
            "learning_enabled": True,
            "training_queues": [
                "https://api.test.rossum.ai/v1/queues/12345",
                "https://api.test.rossum.ai/v1/queues/67890",
            ],
            "description": "Updated training queues",
            "agenda_id": "test_agenda",
        }

        mock_updated_engine = Mock()
        mock_updated_engine.id = 36032
        mock_updated_engine.name = "Test Engine"
        mock_updated_engine.url = "https://api.test.rossum.ai/v1/engines/36032"
        mock_updated_engine.type = "extractor"
        mock_updated_engine.learning_enabled = True
        mock_updated_engine.training_queues = [
            "https://api.test.rossum.ai/v1/queues/12345",
            "https://api.test.rossum.ai/v1/queues/67890",
        ]
        mock_updated_engine.description = "Updated training queues"

        # Use AsyncMock for async methods, Mock for sync methods
        server.client._http_client = AsyncMock()
        server.client._http_client.update = AsyncMock(return_value=mock_updated_engine_data)
        server.client._deserializer = Mock(return_value=mock_updated_engine)

        engine_data = {
            "training_queues": [
                "https://api.test.rossum.ai/v1/queues/12345",
                "https://api.test.rossum.ai/v1/queues/67890",
            ]
        }

        result = await server.update_engine(engine_id=36032, engine_data=engine_data)

        assert result["id"] == 36032
        assert result["name"] == "Test Engine"
        assert len(result["training_queues"]) == 2
        assert "https://api.test.rossum.ai/v1/queues/12345" in result["training_queues"]
        assert "updated successfully" in result["message"].lower()

        # Verify the http client was called correctly
        server.client._http_client.update.assert_called_once_with(Resource.Engine, 36032, engine_data)

    @pytest.mark.asyncio
    async def test_update_engine_learning_enabled(self, server: RossumMCPServer) -> None:
        """Test updating engine learning_enabled flag."""
        mock_updated_engine_data = {
            "id": 36032,
            "url": "https://api.test.rossum.ai/v1/engines/36032",
            "name": "Test Engine",
            "type": "extractor",
            "learning_enabled": False,
            "training_queues": [],
            "description": "",
            "agenda_id": "test_agenda",
        }

        mock_updated_engine = Mock()
        mock_updated_engine.id = 36032
        mock_updated_engine.name = "Test Engine"
        mock_updated_engine.url = "https://api.test.rossum.ai/v1/engines/36032"
        mock_updated_engine.type = "extractor"
        mock_updated_engine.learning_enabled = False
        mock_updated_engine.training_queues = []
        mock_updated_engine.description = ""

        # Use AsyncMock for async methods, Mock for sync methods
        server.client._http_client = AsyncMock()
        server.client._http_client.update = AsyncMock(return_value=mock_updated_engine_data)
        server.client._deserializer = Mock(return_value=mock_updated_engine)

        engine_data = {"learning_enabled": False}

        result = await server.update_engine(engine_id=36032, engine_data=engine_data)

        assert result["id"] == 36032
        assert result["learning_enabled"] is False
        assert "updated successfully" in result["message"].lower()


@pytest.mark.unit
class TestCreateEngine:
    """Tests for engine creation functionality."""

    @pytest.mark.asyncio
    async def test_create_engine_extractor(self, server: RossumMCPServer) -> None:
        """Test successful extractor engine creation."""
        # Mock the internal client create method
        mock_created_engine_data = {
            "id": 100,
            "url": "https://api.test.rossum.ai/v1/engines/100",
            "name": "Test Extractor Engine",
            "type": "extractor",
            "organization": "https://api.test.rossum.ai/v1/organizations/1",
            "learning_enabled": True,
            "training_queues": [],
            "description": "",
        }

        mock_created_engine = Mock()
        mock_created_engine.id = 100
        mock_created_engine.name = "Test Extractor Engine"
        mock_created_engine.url = "https://api.test.rossum.ai/v1/engines/100"
        mock_created_engine.type = "extractor"
        mock_created_engine.organization = "https://api.test.rossum.ai/v1/organizations/1"

        # Use AsyncMock for async methods, Mock for sync methods
        server.client._http_client = AsyncMock()
        server.client._http_client.create = AsyncMock(return_value=mock_created_engine_data)
        server.client._deserializer = Mock(return_value=mock_created_engine)

        result = await server.create_engine(name="Test Extractor Engine", organization_id=1, engine_type="extractor")

        # Verify the result
        assert result["id"] == 100
        assert result["name"] == "Test Extractor Engine"
        assert result["type"] == "extractor"
        # The organization URL comes from base_url which doesn't include /v1
        assert result["organization"] == "https://api.test.rossum.ai/organizations/1"
        assert "created successfully" in result["message"].lower()

        # Verify the http client was called correctly
        server.client._http_client.create.assert_called_once()
        call_args = server.client._http_client.create.call_args
        assert call_args[0][0] == Resource.Engine
        engine_data = call_args[0][1]
        assert engine_data["name"] == "Test Extractor Engine"
        assert engine_data["organization"] == "https://api.test.rossum.ai/organizations/1"
        assert engine_data["type"] == "extractor"

    @pytest.mark.asyncio
    async def test_create_engine_splitter(self, server: RossumMCPServer) -> None:
        """Test successful splitter engine creation."""
        # Mock the internal client create method
        mock_created_engine_data = {
            "id": 101,
            "url": "https://api.test.rossum.ai/v1/engines/101",
            "name": "Test Splitter Engine",
            "type": "splitter",
            "organization": "https://api.test.rossum.ai/v1/organizations/2",
            "learning_enabled": False,
            "training_queues": [],
            "description": "",
        }

        mock_created_engine = Mock()
        mock_created_engine.id = 101
        mock_created_engine.name = "Test Splitter Engine"
        mock_created_engine.url = "https://api.test.rossum.ai/v1/engines/101"
        mock_created_engine.type = "splitter"
        mock_created_engine.organization = "https://api.test.rossum.ai/v1/organizations/2"

        # Use AsyncMock for async methods, Mock for sync methods
        server.client._http_client = AsyncMock()
        server.client._http_client.create = AsyncMock(return_value=mock_created_engine_data)
        server.client._deserializer = Mock(return_value=mock_created_engine)

        result = await server.create_engine(name="Test Splitter Engine", organization_id=2, engine_type="splitter")

        # Verify the result
        assert result["id"] == 101
        assert result["name"] == "Test Splitter Engine"
        assert result["type"] == "splitter"
        assert "created successfully" in result["message"].lower()

        # Verify the http client was called correctly
        server.client._http_client.create.assert_called_once()
        call_args = server.client._http_client.create.call_args
        engine_data = call_args[0][1]
        assert engine_data["type"] == "splitter"

    @pytest.mark.asyncio
    async def test_create_engine_invalid_type(self, server: RossumMCPServer) -> None:
        """Test that invalid engine type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await server.create_engine(name="Invalid Engine", organization_id=1, engine_type="invalid_type")

        assert "Invalid engine_type 'invalid_type'" in str(exc_info.value)
        assert "Must be 'extractor' or 'splitter'" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_engine_api_error(self, server: RossumMCPServer) -> None:
        """Test that API errors are properly propagated."""
        # Mock the http client to raise an exception
        server.client._http_client = AsyncMock()
        server.client._http_client.create = AsyncMock(side_effect=Exception("API Error: Permission denied"))

        with pytest.raises(Exception) as exc_info:
            await server.create_engine(name="Test Engine", organization_id=1, engine_type="extractor")

        assert "API Error: Permission denied" in str(exc_info.value)


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
