"""Tests for rossum_agent.agent.types module."""

from __future__ import annotations

from rossum_agent.agent.types import (  # noqa: TC002 - needed at runtime for type annotations in tests
    Base64ImageSource,
    ContentBlock,
    ImageContentBlock,
    TextContentBlock,
    UserContent,
)


class TestBase64ImageSource:
    """Test Base64ImageSource TypedDict."""

    def test_create_valid_source(self):
        """Test creating a valid Base64ImageSource."""
        source: Base64ImageSource = {
            "type": "base64",
            "media_type": "image/png",
            "data": "iVBORw0KGgoAAAANSUhEUgAAAAUA",
        }
        assert source["type"] == "base64"
        assert source["media_type"] == "image/png"
        assert source["data"] == "iVBORw0KGgoAAAANSUhEUgAAAAUA"

    def test_source_with_different_media_types(self):
        """Test Base64ImageSource with different media types."""
        for media_type in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
            source: Base64ImageSource = {"type": "base64", "media_type": media_type, "data": "base64data"}
            assert source["media_type"] == media_type


class TestImageContentBlock:
    """Test ImageContentBlock TypedDict."""

    def test_create_valid_image_block(self):
        """Test creating a valid ImageContentBlock."""
        block: ImageContentBlock = {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": "base64data"},
        }
        assert block["type"] == "image"
        assert block["source"]["type"] == "base64"

    def test_image_block_nested_source(self):
        """Test ImageContentBlock contains properly structured source."""
        source: Base64ImageSource = {"type": "base64", "media_type": "image/jpeg", "data": "somedata"}
        block: ImageContentBlock = {"type": "image", "source": source}
        assert block["source"] == source


class TestTextContentBlock:
    """Test TextContentBlock TypedDict."""

    def test_create_valid_text_block(self):
        """Test creating a valid TextContentBlock."""
        block: TextContentBlock = {"type": "text", "text": "Hello, world!"}
        assert block["type"] == "text"
        assert block["text"] == "Hello, world!"

    def test_text_block_with_empty_text(self):
        """Test TextContentBlock with empty text."""
        block: TextContentBlock = {"type": "text", "text": ""}
        assert block["text"] == ""

    def test_text_block_with_multiline_text(self):
        """Test TextContentBlock with multiline text."""
        multiline = "Line 1\nLine 2\nLine 3"
        block: TextContentBlock = {"type": "text", "text": multiline}
        assert block["text"] == multiline


class TestContentBlock:
    """Test ContentBlock union type."""

    def test_content_block_can_be_image(self):
        """Test that ContentBlock can hold ImageContentBlock."""
        block: ContentBlock = {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": "data"},
        }
        assert block["type"] == "image"

    def test_content_block_can_be_text(self):
        """Test that ContentBlock can hold TextContentBlock."""
        block: ContentBlock = {"type": "text", "text": "Hello"}
        assert block["type"] == "text"


class TestUserContent:
    """Test UserContent type alias."""

    def test_user_content_can_be_string(self):
        """Test that UserContent can be a simple string."""
        content: UserContent = "Hello, agent!"
        assert content == "Hello, agent!"

    def test_user_content_can_be_content_blocks_list(self):
        """Test that UserContent can be a list of ContentBlocks."""
        content: UserContent = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "data"}},
            {"type": "text", "text": "Describe this image"},
        ]
        assert len(content) == 2
        assert content[0]["type"] == "image"
        assert content[1]["type"] == "text"

    def test_user_content_mixed_blocks(self):
        """Test UserContent with multiple images and text."""
        content: UserContent = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "img1"}},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "img2"}},
            {"type": "text", "text": "Compare these images"},
        ]
        assert len(content) == 3
        image_blocks = [b for b in content if b["type"] == "image"]
        text_blocks = [b for b in content if b["type"] == "text"]
        assert len(image_blocks) == 2
        assert len(text_blocks) == 1
