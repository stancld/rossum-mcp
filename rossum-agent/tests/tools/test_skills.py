"""Tests for skills tools."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from rossum_agent.agent.skills import Skill
from rossum_agent.tools.skills import load_skill


class TestLoadSkill:
    """Tests for the load_skill tool."""

    def test_load_skill_not_found_returns_error(self):
        """Test that load_skill returns error JSON when skill is not found."""
        mock_registry = MagicMock()
        mock_registry.get_skill_names.return_value = ["skill-a", "skill-b"]

        with (
            patch("rossum_agent.tools.skills.get_skill", return_value=None),
            patch("rossum_agent.tools.skills.get_skill_registry", return_value=mock_registry),
        ):
            result = load_skill("nonexistent-skill")

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert parsed["message"] == "Skill 'nonexistent-skill' not found."
        assert parsed["available_skills"] == ["skill-a", "skill-b"]

    def test_load_skill_found_returns_success(self):
        """Test that load_skill returns success JSON when skill is found."""
        mock_skill = Skill(
            name="Schema Patching",
            content="# Schema Patching Instructions\n\nFollow these steps...",
            file_path=Path("/fake/path/schema-patching.md"),
        )

        with patch("rossum_agent.tools.skills.get_skill", return_value=mock_skill):
            result = load_skill("schema-patching")

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["skill_name"] == "Schema Patching"
        assert parsed["instructions"] == "# Schema Patching Instructions\n\nFollow these steps..."
        assert "loaded_tools" not in parsed

    def test_load_skill_auto_loads_declared_tools(self):
        """Test that load_skill auto-loads MCP tools declared in skill frontmatter."""
        mock_skill = Skill(
            name="Schema Patching",
            content="# Instructions",
            file_path=Path("/fake/path/schema-patching.md"),
            mcp_tools=["patch_schema", "get_schema_tree_structure"],
        )

        with (
            patch("rossum_agent.tools.skills.get_skill", return_value=mock_skill),
            patch(
                "rossum_agent.tools.skills.load_tool",
                return_value="Loaded tools: patch_schema, get_schema_tree_structure",
            ) as mock_load_tool,
        ):
            result = load_skill("schema-patching")

        mock_load_tool.assert_called_once_with(["patch_schema", "get_schema_tree_structure"])
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["loaded_tools"] == "Loaded tools: patch_schema, get_schema_tree_structure"

    def test_load_skill_succeeds_when_tool_loading_fails(self):
        """Test that skill loading succeeds even if MCP tool loading fails."""
        mock_skill = Skill(
            name="Schema Patching",
            content="# Instructions",
            file_path=Path("/fake/path/schema-patching.md"),
            mcp_tools=["patch_schema"],
        )

        with (
            patch("rossum_agent.tools.skills.get_skill", return_value=mock_skill),
            patch(
                "rossum_agent.tools.skills.load_tool",
                return_value="Error: MCP connection not available",
            ),
        ):
            result = load_skill("schema-patching")

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["instructions"] == "# Instructions"
        assert "loaded_tools" not in parsed

    def test_load_skill_succeeds_when_tool_loading_raises(self):
        """Test that skill loading succeeds even if load_tool raises an exception."""
        mock_skill = Skill(
            name="Hooks",
            content="# Hook Instructions",
            file_path=Path("/fake/path/hooks.md"),
            mcp_tools=["create_hook"],
        )

        with (
            patch("rossum_agent.tools.skills.get_skill", return_value=mock_skill),
            patch(
                "rossum_agent.tools.skills.load_tool",
                side_effect=RuntimeError("connection lost"),
            ),
        ):
            result = load_skill("hooks")

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["skill_name"] == "Hooks"
        assert "loaded_tools" not in parsed

    def test_load_skill_skips_tool_loading_when_no_tools(self):
        """Test that load_skill doesn't call load_tool when skill has no tools."""
        mock_skill = Skill(
            name="TxScript",
            content="# Reference",
            file_path=Path("/fake/path/txscript.md"),
        )

        with (
            patch("rossum_agent.tools.skills.get_skill", return_value=mock_skill),
            patch("rossum_agent.tools.skills.load_tool") as mock_load_tool,
        ):
            result = load_skill("txscript")

        mock_load_tool.assert_not_called()
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert "loaded_tools" not in parsed
