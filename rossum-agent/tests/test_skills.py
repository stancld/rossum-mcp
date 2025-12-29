"""Tests for rossum_agent.agent.skills module."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rossum_agent.agent.skills import (
    Skill,
    SkillRegistry,
    format_skills_for_prompt,
    get_skill,
    get_skill_content,
    get_skill_registry,
)
from rossum_agent.tools import INTERNAL_TOOLS, execute_tool, get_internal_tool_names, load_skill


class TestSkill:
    """Test Skill dataclass."""

    def test_skill_creation(self):
        """Test Skill dataclass creation."""
        skill = Skill(
            name="Test Skill",
            content="# Test Content",
            file_path=Path("/test/test-skill.md"),
        )
        assert skill.name == "Test Skill"
        assert skill.content == "# Test Content"
        assert skill.slug == "test-skill"

    def test_slug_removes_extension(self):
        """Test that slug is filename without extension."""
        skill = Skill(
            name="My Skill",
            content="content",
            file_path=Path("/path/to/my-skill.md"),
        )
        assert skill.slug == "my-skill"


class TestSkillRegistry:
    """Test SkillRegistry class."""

    def test_loads_skills_from_directory(self):
        """Test that registry loads skills from directory."""
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "test-skill.md"
            skill_file.write_text("# Test Skill\n\nThis is a test.")

            registry = SkillRegistry(Path(tmpdir))
            skills = registry.get_all_skills()

            assert len(skills) == 1
            assert skills[0].slug == "test-skill"
            assert "This is a test" in skills[0].content

    def test_get_skill_by_slug(self):
        """Test getting a skill by its slug."""
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text("# My Skill")

            registry = SkillRegistry(Path(tmpdir))
            skill = registry.get_skill("my-skill")

            assert skill is not None
            assert skill.slug == "my-skill"

    def test_get_skill_returns_none_for_unknown(self):
        """Test that get_skill returns None for unknown skills."""
        with TemporaryDirectory() as tmpdir:
            registry = SkillRegistry(Path(tmpdir))
            skill = registry.get_skill("nonexistent")
            assert skill is None

    def test_get_skill_names(self):
        """Test getting list of skill names."""
        with TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "skill-a.md").write_text("A")
            (Path(tmpdir) / "skill-b.md").write_text("B")

            registry = SkillRegistry(Path(tmpdir))
            names = registry.get_skill_names()

            assert set(names) == {"skill-a", "skill-b"}

    def test_reload_clears_cache(self):
        """Test that reload clears and reloads skills."""
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "original.md"
            skill_file.write_text("Original")

            registry = SkillRegistry(Path(tmpdir))
            assert len(registry.get_all_skills()) == 1

            skill_file.unlink()
            (Path(tmpdir) / "new.md").write_text("New")

            registry.reload()
            names = registry.get_skill_names()

            assert "new" in names
            assert "original" not in names

    def test_handles_missing_directory(self):
        """Test that registry handles missing directory gracefully."""
        registry = SkillRegistry(Path("/nonexistent/path"))
        skills = registry.get_all_skills()
        assert skills == []


class TestFormatSkillsForPrompt:
    """Test format_skills_for_prompt function."""

    def test_formats_skills_with_separators(self):
        """Test that skills are formatted with separators."""
        skills = [
            Skill(name="Skill A", content="Content A", file_path=Path("a.md")),
            Skill(name="Skill B", content="Content B", file_path=Path("b.md")),
        ]

        result = format_skills_for_prompt(skills)

        assert "Available Skills" in result
        assert "Content A" in result
        assert "Content B" in result
        assert "=" in result

    def test_returns_empty_string_for_no_skills(self):
        """Test that empty list returns empty string."""
        result = format_skills_for_prompt([])
        assert result == ""


class TestLoadSkillTool:
    """Test load_skill internal tool."""

    def test_load_skill_is_registered(self):
        """Test that load_skill is in internal tools."""
        assert "load_skill" in get_internal_tool_names()

    def test_load_skill_returns_skill_content(self):
        """Test loading an existing skill."""
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "test-skill.md"
            skill_file.write_text("# Test Instructions\n\nDo this.")

            with patch(
                "rossum_agent.agent.skills._SKILLS_DIR",
                Path(tmpdir),
            ):
                with patch(
                    "rossum_agent.agent.skills._default_registry",
                    None,
                ):
                    result = load_skill(name="test-skill")

                    assert "success" in result
                    assert "Test Instructions" in result

    def test_load_skill_returns_error_for_unknown(self):
        """Test loading a nonexistent skill returns error."""
        with TemporaryDirectory() as tmpdir:
            with patch(
                "rossum_agent.agent.skills._SKILLS_DIR",
                Path(tmpdir),
            ):
                with patch(
                    "rossum_agent.agent.skills._default_registry",
                    None,
                ):
                    result = load_skill(name="nonexistent")

                    assert "error" in result
                    assert "not found" in result

    def test_execute_tool_integration(self):
        """Test load_skill via execute_tool."""
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "deploy.md"
            skill_file.write_text("# Deploy Guide")

            with patch(
                "rossum_agent.agent.skills._SKILLS_DIR",
                Path(tmpdir),
            ):
                with patch(
                    "rossum_agent.agent.skills._default_registry",
                    None,
                ):
                    result = execute_tool("load_skill", {"name": "deploy"}, INTERNAL_TOOLS)

                    assert "success" in result
                    assert "Deploy Guide" in result


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_get_skill_returns_skill(self):
        """Test get_skill module function."""
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text("Content")

            with patch(
                "rossum_agent.agent.skills._SKILLS_DIR",
                Path(tmpdir),
            ):
                with patch(
                    "rossum_agent.agent.skills._default_registry",
                    None,
                ):
                    skill = get_skill("my-skill")
                    assert skill is not None
                    assert skill.content == "Content"

    def test_get_skill_content_returns_content(self):
        """Test get_skill_content module function."""
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text("Skill Content Here")

            with patch(
                "rossum_agent.agent.skills._SKILLS_DIR",
                Path(tmpdir),
            ):
                with patch(
                    "rossum_agent.agent.skills._default_registry",
                    None,
                ):
                    content = get_skill_content("my-skill")
                    assert content == "Skill Content Here"

    def test_get_skill_content_returns_none_for_unknown(self):
        """Test get_skill_content returns None for unknown skill."""
        with TemporaryDirectory() as tmpdir:
            with patch(
                "rossum_agent.agent.skills._SKILLS_DIR",
                Path(tmpdir),
            ):
                with patch(
                    "rossum_agent.agent.skills._default_registry",
                    None,
                ):
                    content = get_skill_content("nonexistent")
                    assert content is None

    def test_get_skill_registry_creates_default(self):
        """Test get_skill_registry creates default registry."""
        with patch(
            "rossum_agent.agent.skills._default_registry",
            None,
        ):
            registry = get_skill_registry()
            assert isinstance(registry, SkillRegistry)
