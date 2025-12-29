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
            name="Rossum Deployment",
            content="# Deployment Instructions\n\nFollow these steps...",
            file_path=Path("/fake/path/rossum-deployment.md"),
        )

        with patch("rossum_agent.tools.skills.get_skill", return_value=mock_skill):
            result = load_skill("rossum-deployment")

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["skill_name"] == "Rossum Deployment"
        assert parsed["instructions"] == "# Deployment Instructions\n\nFollow these steps..."
