"""Tests for API Pydantic schemas."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from rossum_agent.api.models.schemas import (
    ChatDetail,
    ChatListResponse,
    ChatResponse,
    ChatSummary,
    CreateChatRequest,
    DeleteResponse,
    ErrorResponse,
    FileInfo,
    HealthResponse,
    ImageContent,
    Message,
    MessageRequest,
    StepEvent,
    StreamDoneEvent,
    TextContent,
)


class TestCreateChatRequest:
    """Tests for CreateChatRequest schema."""

    def test_default_mcp_mode(self):
        """Test default mcp_mode is read-only."""
        request = CreateChatRequest()
        assert request.mcp_mode == "read-only"

    def test_read_only_mode(self):
        """Test read-only mode."""
        request = CreateChatRequest(mcp_mode="read-only")
        assert request.mcp_mode == "read-only"

    def test_read_write_mode(self):
        """Test read-write mode."""
        request = CreateChatRequest(mcp_mode="read-write")
        assert request.mcp_mode == "read-write"

    def test_invalid_mode_rejected(self):
        """Test invalid mcp_mode is rejected."""
        with pytest.raises(ValidationError):
            CreateChatRequest(mcp_mode="invalid")


class TestChatResponse:
    """Tests for ChatResponse schema."""

    def test_valid_response(self):
        """Test valid response creation."""
        now = datetime.now(UTC)
        response = ChatResponse(chat_id="chat_123", created_at=now)
        assert response.chat_id == "chat_123"
        assert response.created_at == now

    def test_required_fields(self):
        """Test required fields validation."""
        with pytest.raises(ValidationError):
            ChatResponse()


class TestChatSummary:
    """Tests for ChatSummary schema."""

    def test_valid_summary(self):
        """Test valid summary creation."""
        summary = ChatSummary(chat_id="chat_123", timestamp=1702132252, message_count=5, first_message="Hello, agent!")
        assert summary.chat_id == "chat_123"
        assert summary.timestamp == 1702132252
        assert summary.message_count == 5
        assert summary.first_message == "Hello, agent!"
        assert summary.preview is None

    def test_summary_with_preview(self):
        """Test summary with preview field."""
        summary = ChatSummary(
            chat_id="chat_123",
            timestamp=1702132252,
            message_count=5,
            first_message="Hello, agent!",
            preview="User request preview text",
        )
        assert summary.preview == "User request preview text"


class TestChatListResponse:
    """Tests for ChatListResponse schema."""

    def test_empty_list(self):
        """Test empty chat list."""
        response = ChatListResponse(chats=[], total=0, limit=50, offset=0)
        assert len(response.chats) == 0
        assert response.total == 0

    def test_populated_list(self):
        """Test populated chat list."""
        chats = [
            ChatSummary(chat_id="chat_1", timestamp=1702132252, message_count=5, first_message="First"),
            ChatSummary(chat_id="chat_2", timestamp=1702132253, message_count=10, first_message="Second"),
        ]
        response = ChatListResponse(chats=chats, total=2, limit=50, offset=0)
        assert len(response.chats) == 2
        assert response.total == 2


class TestMessage:
    """Tests for Message schema."""

    def test_user_message(self):
        """Test user message creation."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_assistant_message(self):
        """Test assistant message creation."""
        msg = Message(role="assistant", content="Hello back!")
        assert msg.role == "assistant"
        assert msg.content == "Hello back!"

    def test_invalid_role_rejected(self):
        """Test invalid role is rejected."""
        with pytest.raises(ValidationError):
            Message(role="system", content="Not allowed")


class TestFileInfo:
    """Tests for FileInfo schema."""

    def test_file_info_without_mime_type(self):
        """Test file info without mime_type."""
        info = FileInfo(filename="chart.html", size=12345, timestamp="2024-12-09T14:35:00Z")
        assert info.filename == "chart.html"
        assert info.size == 12345
        assert info.mime_type is None

    def test_file_info_with_mime_type(self):
        """Test file info with mime_type."""
        info = FileInfo(filename="chart.png", size=5000, timestamp="2024-12-09T14:35:00Z", mime_type="image/png")
        assert info.mime_type == "image/png"


class TestChatDetail:
    """Tests for ChatDetail schema."""

    def test_chat_detail(self):
        """Test chat detail creation."""
        now = datetime.now(UTC)
        detail = ChatDetail(
            chat_id="chat_123", messages=[Message(role="user", content="Hello")], created_at=now, files=[]
        )
        assert detail.chat_id == "chat_123"
        assert len(detail.messages) == 1


class TestDeleteResponse:
    """Tests for DeleteResponse schema."""

    def test_deleted_true(self):
        """Test deleted response."""
        response = DeleteResponse(deleted=True)
        assert response.deleted is True

    def test_deleted_false(self):
        """Test not deleted response."""
        response = DeleteResponse(deleted=False)
        assert response.deleted is False


class TestMessageRequest:
    """Tests for MessageRequest schema."""

    def test_valid_content(self):
        """Test valid message content."""
        request = MessageRequest(content="Hello, agent!")
        assert request.content == "Hello, agent!"

    def test_empty_content_rejected(self):
        """Test empty content is rejected."""
        with pytest.raises(ValidationError):
            MessageRequest(content="")

    def test_max_length_validation(self):
        """Test content exceeding max length is rejected."""
        with pytest.raises(ValidationError):
            MessageRequest(content="x" * 50001)

    def test_message_with_images(self):
        """Test message request with images."""
        image = ImageContent(media_type="image/png", data="aGVsbG8=")
        request = MessageRequest(content="Analyze this image", images=[image])
        assert request.content == "Analyze this image"
        assert request.images is not None
        assert len(request.images) == 1
        assert request.images[0].media_type == "image/png"

    def test_message_without_images(self):
        """Test message request without images."""
        request = MessageRequest(content="Hello")
        assert request.images is None

    def test_message_with_multiple_images(self):
        """Test message request with multiple images."""
        images = [
            ImageContent(media_type="image/png", data="aGVsbG8="),
            ImageContent(media_type="image/jpeg", data="d29ybGQ="),
        ]
        request = MessageRequest(content="Compare these images", images=images)
        assert len(request.images) == 2

    def test_message_max_images_exceeded(self):
        """Test that more than 5 images is rejected."""
        images = [ImageContent(media_type="image/png", data="aGVsbG8=")] * 6
        with pytest.raises(ValidationError):
            MessageRequest(content="Too many images", images=images)


class TestImageContent:
    """Tests for ImageContent schema."""

    def test_valid_image_content(self):
        """Test valid image content."""
        image = ImageContent(media_type="image/png", data="aGVsbG8=")
        assert image.type == "image"
        assert image.media_type == "image/png"
        assert image.data == "aGVsbG8="

    def test_all_supported_media_types(self):
        """Test all supported media types."""
        for media_type in ["image/jpeg", "image/png", "image/gif", "image/webp"]:
            image = ImageContent(media_type=media_type, data="aGVsbG8=")
            assert image.media_type == media_type

    def test_invalid_media_type_rejected(self):
        """Test invalid media type is rejected."""
        with pytest.raises(ValidationError):
            ImageContent(media_type="image/bmp", data="aGVsbG8=")

    def test_image_data_too_large(self):
        """Test that oversized image data is rejected."""
        large_data = "x" * (7 * 1024 * 1024)  # ~7MB base64
        with pytest.raises(ValidationError):
            ImageContent(media_type="image/png", data=large_data)


class TestTextContent:
    """Tests for TextContent schema."""

    def test_valid_text_content(self):
        """Test valid text content."""
        text = TextContent(text="Hello, world!")
        assert text.type == "text"
        assert text.text == "Hello, world!"


class TestMessageMultimodal:
    """Tests for multimodal Message schema."""

    def test_message_with_string_content(self):
        """Test message with simple string content."""
        msg = Message(role="user", content="Hello")
        assert msg.content == "Hello"

    def test_message_with_multimodal_content(self):
        """Test message with multimodal content list."""
        content = [
            TextContent(text="Analyze this image"),
            ImageContent(media_type="image/png", data="aGVsbG8="),
        ]
        msg = Message(role="user", content=content)
        assert len(msg.content) == 2


class TestStepEvent:
    """Tests for StepEvent schema."""

    def test_thinking_event(self):
        """Test thinking event."""
        event = StepEvent(type="thinking", step_number=1, content="I'll help you with that...", is_streaming=True)
        assert event.type == "thinking"
        assert event.is_streaming is True

    def test_tool_start_event(self):
        """Test tool_start event."""
        event = StepEvent(type="tool_start", step_number=1, tool_name="list_annotations", tool_progress=(1, 3))
        assert event.type == "tool_start"
        assert event.tool_name == "list_annotations"
        assert event.tool_progress == (1, 3)

    def test_tool_result_event(self):
        """Test tool_result event."""
        event = StepEvent(
            type="tool_result",
            step_number=1,
            tool_name="list_annotations",
            result='{"annotations": []}',
            is_error=False,
        )
        assert event.type == "tool_result"
        assert event.is_error is False

    def test_final_answer_event(self):
        """Test final_answer event."""
        event = StepEvent(type="final_answer", step_number=2, content="Here is your answer", is_final=True)
        assert event.type == "final_answer"
        assert event.is_final is True

    def test_error_event(self):
        """Test error event."""
        event = StepEvent(type="error", step_number=0, content="Something went wrong", is_final=True)
        assert event.type == "error"


class TestStreamDoneEvent:
    """Tests for StreamDoneEvent schema."""

    def test_valid_event(self):
        """Test valid stream done event."""
        event = StreamDoneEvent(total_steps=3, input_tokens=1500, output_tokens=350)
        assert event.total_steps == 3
        assert event.input_tokens == 1500
        assert event.output_tokens == 350


class TestHealthResponse:
    """Tests for HealthResponse schema."""

    def test_healthy_response(self):
        """Test healthy response."""
        response = HealthResponse(status="healthy", redis_connected=True, version="0.2.0")
        assert response.status == "healthy"
        assert response.redis_connected is True

    def test_unhealthy_response(self):
        """Test unhealthy response."""
        response = HealthResponse(status="unhealthy", redis_connected=False, version="0.2.0")
        assert response.status == "unhealthy"
        assert response.redis_connected is False


class TestErrorResponse:
    """Tests for ErrorResponse schema."""

    def test_error_with_code(self):
        """Test error with code."""
        error = ErrorResponse(detail="Something went wrong", error_code="ERR_001")
        assert error.detail == "Something went wrong"
        assert error.error_code == "ERR_001"

    def test_error_without_code(self):
        """Test error without code."""
        error = ErrorResponse(detail="Something went wrong")
        assert error.error_code is None
