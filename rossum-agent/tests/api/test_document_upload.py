"""Tests for document upload functionality."""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError
from rossum_agent.api.models.schemas import DocumentContent, MessageRequest
from rossum_agent.api.services.agent_service import AgentService


class TestDocumentContent:
    """Tests for DocumentContent model."""

    def test_valid_document(self) -> None:
        """Test creating a valid document content."""
        data = base64.b64encode(b"PDF content here").decode()
        doc = DocumentContent(
            media_type="application/pdf",
            data=data,
            filename="test.pdf",
        )
        assert doc.type == "document"
        assert doc.media_type == "application/pdf"
        assert doc.filename == "test.pdf"
        assert doc.data == data

    def test_invalid_media_type(self) -> None:
        """Test that non-PDF media types are rejected."""
        data = base64.b64encode(b"Not a PDF").decode()
        with pytest.raises(ValidationError) as exc_info:
            DocumentContent(
                media_type="text/plain",  # type: ignore[arg-type]
                data=data,
                filename="test.txt",
            )
        assert "media_type" in str(exc_info.value)

    def test_size_limit_exceeded(self) -> None:
        """Test that documents exceeding 20MB are rejected."""
        large_data = base64.b64encode(b"x" * (21 * 1024 * 1024)).decode()
        with pytest.raises(ValidationError) as exc_info:
            DocumentContent(
                media_type="application/pdf",
                data=large_data,
                filename="large.pdf",
            )
        assert "20 MB" in str(exc_info.value)

    def test_size_within_limit(self) -> None:
        """Test that documents within 20MB are accepted."""
        data = base64.b64encode(b"x" * (19 * 1024 * 1024)).decode()
        doc = DocumentContent(
            media_type="application/pdf",
            data=data,
            filename="normal.pdf",
        )
        assert doc.filename == "normal.pdf"


class TestMessageRequestWithDocuments:
    """Tests for MessageRequest with documents field."""

    def test_message_with_documents(self) -> None:
        """Test creating a message with documents."""
        data = base64.b64encode(b"PDF content").decode()
        msg = MessageRequest(
            content="Please process this document",
            documents=[
                DocumentContent(
                    media_type="application/pdf",
                    data=data,
                    filename="invoice.pdf",
                )
            ],
        )
        assert msg.content == "Please process this document"
        assert len(msg.documents) == 1
        assert msg.documents[0].filename == "invoice.pdf"

    def test_message_with_images_and_documents(self) -> None:
        """Test creating a message with both images and documents."""
        from rossum_agent.api.models.schemas import ImageContent

        img_data = base64.b64encode(b"fake image").decode()
        doc_data = base64.b64encode(b"PDF content").decode()
        msg = MessageRequest(
            content="Process these files",
            images=[
                ImageContent(
                    media_type="image/png",
                    data=img_data,
                )
            ],
            documents=[
                DocumentContent(
                    media_type="application/pdf",
                    data=doc_data,
                    filename="document.pdf",
                )
            ],
        )
        assert len(msg.images) == 1
        assert len(msg.documents) == 1

    def test_max_documents_limit(self) -> None:
        """Test that more than 5 documents are rejected."""
        data = base64.b64encode(b"PDF").decode()
        docs = [DocumentContent(media_type="application/pdf", data=data, filename=f"doc{i}.pdf") for i in range(6)]
        with pytest.raises(ValidationError) as exc_info:
            MessageRequest(content="Too many docs", documents=docs)
        assert "documents" in str(exc_info.value).lower() or "5" in str(exc_info.value)

    def test_message_without_documents(self) -> None:
        """Test that documents field is optional."""
        msg = MessageRequest(content="Just text")
        assert msg.documents is None


class TestAgentServiceDocumentStorage:
    """Tests for document storage in AgentService."""

    def test_save_documents_to_output_dir(self) -> None:
        """Test that documents are saved correctly to output directory."""
        service = AgentService()

        with tempfile.TemporaryDirectory() as tmpdir:
            service._output_dir = Path(tmpdir)

            pdf_content = b"%PDF-1.4 test content"
            data = base64.b64encode(pdf_content).decode()
            docs = [
                DocumentContent(
                    media_type="application/pdf",
                    data=data,
                    filename="test_invoice.pdf",
                )
            ]

            service._save_documents_to_output_dir(docs)

            saved_file = Path(tmpdir) / "test_invoice.pdf"
            assert saved_file.exists()
            assert saved_file.read_bytes() == pdf_content

    def test_save_multiple_documents(self) -> None:
        """Test saving multiple documents."""
        service = AgentService()

        with tempfile.TemporaryDirectory() as tmpdir:
            service._output_dir = Path(tmpdir)

            docs = []
            for i in range(3):
                content = f"PDF content {i}".encode()
                data = base64.b64encode(content).decode()
                docs.append(
                    DocumentContent(
                        media_type="application/pdf",
                        data=data,
                        filename=f"doc{i}.pdf",
                    )
                )

            service._save_documents_to_output_dir(docs)

            for i in range(3):
                saved_file = Path(tmpdir) / f"doc{i}.pdf"
                assert saved_file.exists()
                assert saved_file.read_bytes() == f"PDF content {i}".encode()

    def test_save_documents_no_output_dir(self) -> None:
        """Test that saving documents without output dir logs warning."""
        service = AgentService()
        service._output_dir = None

        data = base64.b64encode(b"PDF").decode()
        docs = [
            DocumentContent(
                media_type="application/pdf",
                data=data,
                filename="test.pdf",
            )
        ]

        service._save_documents_to_output_dir(docs)


class TestBuildUpdatedHistoryWithDocuments:
    """Tests for build_updated_history with documents."""

    def test_history_includes_document_info(self) -> None:
        """Test that document filenames are included in history."""
        service = AgentService()
        service._last_memory = None

        data = base64.b64encode(b"PDF").decode()
        docs = [
            DocumentContent(media_type="application/pdf", data=data, filename="invoice.pdf"),
            DocumentContent(media_type="application/pdf", data=data, filename="receipt.pdf"),
        ]

        history = service.build_updated_history(
            existing_history=[],
            user_prompt="Process these documents",
            final_response="Done processing",
            documents=docs,
        )

        assert len(history) == 2
        user_content = history[0]["content"]
        assert "[Uploaded documents: invoice.pdf, receipt.pdf]" in user_content
        assert "Process these documents" in user_content
