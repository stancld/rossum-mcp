"""Tests for Pydantic models."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from rossum_agent_client.models import (
    ChatDetail,
    ChatListResponse,
    ChatResponse,
    ChatSummary,
    CreateChatRequest,
    DeleteResponse,
    DocumentContent,
    FileCreatedEvent,
    FileInfo,
    FileListResponse,
    HealthResponse,
    ImageContent,
    Message,
    MessageRequest,
    StepEvent,
    StreamDoneEvent,
    SubAgentProgressEvent,
    SubAgentTextEvent,
    SubAgentTokenUsageDetail,
    TextContent,
    TokenUsageBreakdown,
    TokenUsageBySource,
)


class TestCreateChatRequest:
    def test_default_mcp_mode(self) -> None:
        request = CreateChatRequest()
        assert request.mcp_mode == "read-only"

    def test_read_write_mode(self) -> None:
        request = CreateChatRequest(mcp_mode="read-write")
        assert request.mcp_mode == "read-write"

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CreateChatRequest(mcp_mode="invalid")  # type: ignore[arg-type]


class TestImageContent:
    def test_valid_image(self) -> None:
        img = ImageContent(media_type="image/png", data="base64data")
        assert img.type == "image"
        assert img.media_type == "image/png"

    def test_all_media_types(self) -> None:
        for media_type in ["image/jpeg", "image/png", "image/gif", "image/webp"]:
            img = ImageContent(media_type=media_type, data="data")  # type: ignore[arg-type]
            assert img.media_type == media_type

    def test_invalid_media_type(self) -> None:
        with pytest.raises(ValidationError):
            ImageContent(media_type="image/bmp", data="data")  # type: ignore[arg-type]


class TestDocumentContent:
    def test_valid_document(self) -> None:
        doc = DocumentContent(data="base64pdf", filename="invoice.pdf")
        assert doc.type == "document"
        assert doc.media_type == "application/pdf"
        assert doc.filename == "invoice.pdf"


class TestMessageRequest:
    def test_minimal_request(self) -> None:
        req = MessageRequest(content="Hello")
        assert req.content == "Hello"
        assert req.images is None
        assert req.documents is None

    def test_with_images(self) -> None:
        img = ImageContent(media_type="image/png", data="data")
        req = MessageRequest(content="Analyze", images=[img])
        assert req.images is not None and len(req.images) == 1

    def test_with_documents(self) -> None:
        doc = DocumentContent(data="pdf", filename="file.pdf")
        req = MessageRequest(content="Process", documents=[doc])
        assert req.documents is not None and len(req.documents) == 1

    def test_empty_content_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MessageRequest(content="")

    def test_max_content_length(self) -> None:
        long_content = "x" * 50001
        with pytest.raises(ValidationError):
            MessageRequest(content=long_content)


class TestChatResponse:
    def test_valid_response(self) -> None:
        resp = ChatResponse(chat_id="abc-123", created_at=datetime(2024, 1, 15, 10, 0, 0))
        assert resp.chat_id == "abc-123"
        assert resp.created_at.year == 2024


class TestChatSummary:
    def test_valid_summary(self) -> None:
        summary = ChatSummary(
            chat_id="chat-1",
            timestamp=1705312800,
            message_count=5,
            first_message="Hello",
            preview="How can I help?",
        )
        assert summary.chat_id == "chat-1"
        assert summary.preview == "How can I help?"

    def test_optional_preview(self) -> None:
        summary = ChatSummary(chat_id="chat-1", timestamp=1705312800, message_count=1, first_message="Hi")
        assert summary.preview is None


class TestChatListResponse:
    def test_valid_list_response(self) -> None:
        resp = ChatListResponse(
            chats=[ChatSummary(chat_id="c1", timestamp=123, message_count=1, first_message="Hi")],
            total=1,
            limit=50,
            offset=0,
        )
        assert len(resp.chats) == 1
        assert resp.total == 1


class TestMessage:
    def test_string_content(self) -> None:
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_list_content(self) -> None:
        content: list[TextContent | ImageContent] = [TextContent(text="Hello")]
        msg = Message(role="assistant", content=content)
        assert isinstance(msg.content, list)
        assert len(msg.content) == 1


class TestChatDetail:
    def test_valid_detail(self) -> None:
        detail = ChatDetail(
            chat_id="chat-123",
            messages=[Message(role="user", content="Hi")],
            created_at=datetime(2024, 1, 15),
            files=[],
        )
        assert detail.chat_id == "chat-123"
        assert len(detail.messages) == 1


class TestFileInfo:
    def test_valid_file_info(self) -> None:
        info = FileInfo(
            filename="report.csv",
            size=1024,
            timestamp="2024-01-15T10:00:00Z",
            mime_type="text/csv",
        )
        assert info.filename == "report.csv"
        assert info.size == 1024

    def test_optional_mime_type(self) -> None:
        info = FileInfo(filename="file.bin", size=100, timestamp="2024-01-15T10:00:00Z")
        assert info.mime_type is None


class TestStepEvent:
    def test_thinking_event(self) -> None:
        event = StepEvent(type="thinking", step_number=1, content="Analyzing request...")
        assert event.type == "thinking"
        assert event.content == "Analyzing request..."

    def test_tool_start_event(self) -> None:
        event = StepEvent(
            type="tool_start",
            step_number=2,
            tool_name="list_queues",
            tool_arguments={"limit": 10},
        )
        assert event.tool_name == "list_queues"
        assert event.tool_arguments == {"limit": 10}

    def test_tool_result_event(self) -> None:
        event = StepEvent(
            type="tool_result",
            step_number=3,
            result='[{"id": 1}]',
            is_error=False,
        )
        assert event.result == '[{"id": 1}]'
        assert event.is_error is False

    def test_final_answer_event(self) -> None:
        event = StepEvent(
            type="final_answer",
            step_number=4,
            content="Here are the results",
            is_final=True,
        )
        assert event.is_final is True

    def test_error_event(self) -> None:
        event = StepEvent(type="error", step_number=1, content="Something went wrong", is_error=True)
        assert event.type == "error"
        assert event.is_error is True

    def test_tool_progress(self) -> None:
        event = StepEvent(type="tool_start", step_number=1, tool_progress=[3, 10])
        assert event.tool_progress == [3, 10]


class TestSubAgentProgressEvent:
    def test_valid_progress(self) -> None:
        event = SubAgentProgressEvent(
            tool_name="deep_search",
            iteration=2,
            max_iterations=5,
            current_tool="grep",
            tool_calls=["read", "grep"],
            status="searching",
        )
        assert event.type == "sub_agent_progress"
        assert event.iteration == 2
        assert event.status == "searching"

    def test_default_values(self) -> None:
        event = SubAgentProgressEvent(tool_name="search", iteration=1, max_iterations=10)
        assert event.current_tool is None
        assert event.tool_calls == []
        assert event.status == "running"


class TestSubAgentTextEvent:
    def test_valid_text_event(self) -> None:
        event = SubAgentTextEvent(tool_name="analyzer", text="Found 5 matches", is_final=True)
        assert event.type == "sub_agent_text"
        assert event.text == "Found 5 matches"
        assert event.is_final is True


class TestStreamDoneEvent:
    def test_valid_done_event(self) -> None:
        event = StreamDoneEvent(total_steps=5, input_tokens=100, output_tokens=250)
        assert event.total_steps == 5
        assert event.input_tokens == 100
        assert event.output_tokens == 250


class TestFileCreatedEvent:
    def test_valid_file_created(self) -> None:
        event = FileCreatedEvent(filename="output.csv", url="/files/output.csv")
        assert event.type == "file_created"
        assert event.filename == "output.csv"
        assert event.url == "/files/output.csv"


class TestHealthResponse:
    def test_healthy_response(self) -> None:
        resp = HealthResponse(status="healthy", redis_connected=True, version="1.0.0dev")
        assert resp.status == "healthy"

    def test_unhealthy_response(self) -> None:
        resp = HealthResponse(status="unhealthy", redis_connected=False, version="1.0.0dev")
        assert resp.status == "unhealthy"


class TestDeleteResponse:
    def test_deleted_true(self) -> None:
        resp = DeleteResponse(deleted=True)
        assert resp.deleted is True

    def test_deleted_false(self) -> None:
        resp = DeleteResponse(deleted=False)
        assert resp.deleted is False


class TestFileListResponse:
    def test_valid_response(self) -> None:
        resp = FileListResponse(
            files=[FileInfo(filename="a.txt", size=100, timestamp="2024-01-15T10:00:00Z")],
            total=1,
        )
        assert len(resp.files) == 1
        assert resp.total == 1

    def test_empty_response(self) -> None:
        resp = FileListResponse(files=[], total=0)
        assert len(resp.files) == 0


class TestTokenUsageBySource:
    def test_valid_usage(self) -> None:
        usage = TokenUsageBySource(input_tokens=100, output_tokens=50, total_tokens=150)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150

    def test_zero_tokens(self) -> None:
        usage = TokenUsageBySource(input_tokens=0, output_tokens=0, total_tokens=0)
        assert usage.total_tokens == 0


class TestSubAgentTokenUsageDetail:
    def test_valid_detail(self) -> None:
        detail = SubAgentTokenUsageDetail(
            input_tokens=500,
            output_tokens=250,
            total_tokens=750,
            by_tool={"debug_hook": TokenUsageBySource(input_tokens=500, output_tokens=250, total_tokens=750)},
        )
        assert detail.input_tokens == 500
        assert detail.total_tokens == 750
        assert "debug_hook" in detail.by_tool
        assert detail.by_tool["debug_hook"].input_tokens == 500

    def test_empty_by_tool(self) -> None:
        detail = SubAgentTokenUsageDetail(input_tokens=0, output_tokens=0, total_tokens=0, by_tool={})
        assert detail.by_tool == {}

    def test_multiple_tools(self) -> None:
        detail = SubAgentTokenUsageDetail(
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            by_tool={
                "debug_hook": TokenUsageBySource(input_tokens=600, output_tokens=300, total_tokens=900),
                "patch_schema": TokenUsageBySource(input_tokens=400, output_tokens=200, total_tokens=600),
            },
        )
        assert len(detail.by_tool) == 2


class TestTokenUsageBreakdown:
    def test_valid_breakdown(self) -> None:
        breakdown = TokenUsageBreakdown(
            total=TokenUsageBySource(input_tokens=1500, output_tokens=750, total_tokens=2250),
            main_agent=TokenUsageBySource(input_tokens=1000, output_tokens=500, total_tokens=1500),
            sub_agents=SubAgentTokenUsageDetail(
                input_tokens=500,
                output_tokens=250,
                total_tokens=750,
                by_tool={"debug_hook": TokenUsageBySource(input_tokens=500, output_tokens=250, total_tokens=750)},
            ),
        )
        assert breakdown.total.total_tokens == 2250
        assert breakdown.main_agent.total_tokens == 1500
        assert breakdown.sub_agents.total_tokens == 750

    def test_format_summary_lines_includes_header(self) -> None:
        breakdown = TokenUsageBreakdown(
            total=TokenUsageBySource(input_tokens=1000, output_tokens=500, total_tokens=1500),
            main_agent=TokenUsageBySource(input_tokens=1000, output_tokens=500, total_tokens=1500),
            sub_agents=SubAgentTokenUsageDetail(input_tokens=0, output_tokens=0, total_tokens=0, by_tool={}),
        )
        lines = breakdown.format_summary_lines()
        output = "\n".join(lines)

        assert "TOKEN USAGE SUMMARY" in output
        assert "=" * 60 in output

    def test_format_summary_lines_includes_main_agent(self) -> None:
        breakdown = TokenUsageBreakdown(
            total=TokenUsageBySource(input_tokens=1000, output_tokens=500, total_tokens=1500),
            main_agent=TokenUsageBySource(input_tokens=1000, output_tokens=500, total_tokens=1500),
            sub_agents=SubAgentTokenUsageDetail(input_tokens=0, output_tokens=0, total_tokens=0, by_tool={}),
        )
        lines = breakdown.format_summary_lines()
        output = "\n".join(lines)

        assert "Main Agent" in output
        assert "1,000" in output
        assert "1,500" in output

    def test_format_summary_lines_includes_sub_agents(self) -> None:
        breakdown = TokenUsageBreakdown(
            total=TokenUsageBySource(input_tokens=3000, output_tokens=1500, total_tokens=4500),
            main_agent=TokenUsageBySource(input_tokens=1000, output_tokens=500, total_tokens=1500),
            sub_agents=SubAgentTokenUsageDetail(
                input_tokens=2000,
                output_tokens=1000,
                total_tokens=3000,
                by_tool={
                    "debug_hook": TokenUsageBySource(input_tokens=1500, output_tokens=700, total_tokens=2200),
                    "patch_schema": TokenUsageBySource(input_tokens=500, output_tokens=300, total_tokens=800),
                },
            ),
        )
        lines = breakdown.format_summary_lines()
        output = "\n".join(lines)

        assert "Sub-agents (total)" in output
        assert "debug_hook" in output
        assert "patch_schema" in output

    def test_format_summary_lines_includes_total(self) -> None:
        breakdown = TokenUsageBreakdown(
            total=TokenUsageBySource(input_tokens=3000, output_tokens=1500, total_tokens=4500),
            main_agent=TokenUsageBySource(input_tokens=1000, output_tokens=500, total_tokens=1500),
            sub_agents=SubAgentTokenUsageDetail(input_tokens=2000, output_tokens=1000, total_tokens=3000, by_tool={}),
        )
        lines = breakdown.format_summary_lines()
        output = "\n".join(lines)

        assert "TOTAL" in output
        assert "3,000" in output
        assert "4,500" in output


class TestStreamDoneEventWithBreakdown:
    def test_done_event_without_breakdown(self) -> None:
        event = StreamDoneEvent(total_steps=5, input_tokens=100, output_tokens=50)
        assert event.token_usage_breakdown is None

    def test_done_event_with_breakdown(self) -> None:
        breakdown = TokenUsageBreakdown(
            total=TokenUsageBySource(input_tokens=100, output_tokens=50, total_tokens=150),
            main_agent=TokenUsageBySource(input_tokens=100, output_tokens=50, total_tokens=150),
            sub_agents=SubAgentTokenUsageDetail(input_tokens=0, output_tokens=0, total_tokens=0, by_tool={}),
        )
        event = StreamDoneEvent(total_steps=5, input_tokens=100, output_tokens=50, token_usage_breakdown=breakdown)
        assert event.token_usage_breakdown is not None
        assert event.token_usage_breakdown.total.total_tokens == 150
