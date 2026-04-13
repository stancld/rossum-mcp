"""Tests for rossum_agent.chat_models module."""

from __future__ import annotations

import tempfile
from pathlib import Path

from rossum_agent.chat_models import ChatData, ChatMetadata


class TestChatMetadata:
    """Test ChatMetadata dataclass."""

    def test_default_values(self):
        metadata = ChatMetadata()
        assert metadata.commit_sha is None
        assert metadata.total_input_tokens == 0
        assert metadata.total_output_tokens == 0
        assert metadata.total_tool_calls == 0
        assert metadata.total_steps == 0
        assert metadata.persona == "default"

    def test_custom_values(self):
        metadata = ChatMetadata(
            commit_sha="abc123",
            total_input_tokens=100,
            total_output_tokens=50,
            total_tool_calls=5,
            total_steps=3,
        )
        assert metadata.commit_sha == "abc123"
        assert metadata.total_input_tokens == 100
        assert metadata.total_output_tokens == 50
        assert metadata.total_tool_calls == 5
        assert metadata.total_steps == 3

    def test_to_dict(self):
        metadata = ChatMetadata(
            commit_sha="abc123",
            total_input_tokens=100,
            total_output_tokens=50,
            total_tool_calls=5,
            total_steps=3,
        )
        result = metadata.to_dict()
        assert result == {
            "commit_sha": "abc123",
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "total_tool_calls": 5,
            "total_steps": 3,
            "mcp_mode": "read-only",
            "persona": "default",
            "config_commits": [],
            "summary": None,
        }

    def test_from_dict(self):
        data = {
            "commit_sha": "def456",
            "total_input_tokens": 200,
            "total_output_tokens": 100,
            "total_tool_calls": 10,
            "total_steps": 5,
            "config_commits": ["abc123", "def456"],
        }
        metadata = ChatMetadata.from_dict(data)
        assert metadata.commit_sha == "def456"
        assert metadata.total_input_tokens == 200
        assert metadata.total_output_tokens == 100
        assert metadata.total_tool_calls == 10
        assert metadata.total_steps == 5
        assert metadata.config_commits == ["abc123", "def456"]
        assert metadata.persona == "default"

    def test_from_dict_with_missing_keys(self):
        data = {"commit_sha": "abc123"}
        metadata = ChatMetadata.from_dict(data)
        assert metadata.commit_sha == "abc123"
        assert metadata.total_input_tokens == 0
        assert metadata.total_output_tokens == 0
        assert metadata.total_tool_calls == 0
        assert metadata.total_steps == 0
        assert metadata.config_commits == []
        assert metadata.persona == "default"

    def test_from_dict_with_persona(self):
        data = {"persona": "cautious"}
        metadata = ChatMetadata.from_dict(data)
        assert metadata.persona == "cautious"

    def test_from_dict_empty(self):
        metadata = ChatMetadata.from_dict({})
        assert metadata.commit_sha is None
        assert metadata.total_input_tokens == 0


class TestChatData:
    """Test ChatData dataclass."""

    def test_default_values(self):
        data = ChatData()
        assert data.messages == []
        assert data.output_dir is None
        assert isinstance(data.metadata, ChatMetadata)

    def test_custom_values(self):
        messages = [{"role": "user", "content": "Hello"}]
        metadata = ChatMetadata(commit_sha="abc")
        output_dir = str(Path(tempfile.gettempdir()) / "output")
        data = ChatData(messages=messages, output_dir=output_dir, metadata=metadata)
        assert data.messages == messages
        assert data.output_dir == output_dir
        assert data.metadata.commit_sha == "abc"
