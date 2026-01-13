"""Tests for rossum_agent.agent.types module."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rossum_agent.agent.types import UserContent


class TestUserContent:
    """Test UserContent type alias."""

    def test_user_content_can_be_string(self):
        """Test that UserContent can be a simple string."""
        content: UserContent = "Hello, agent!"
        assert content == "Hello, agent!"

    def test_user_content_can_be_content_blocks_list(self):
        """Test that UserContent can be a list of content blocks."""
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
