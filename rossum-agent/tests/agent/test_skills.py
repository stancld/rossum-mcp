"""Tests for rossum_agent.agent.skills module."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rossum_agent.agent.skills import (
    Skill,
    SkillRegistry,
    _parse_frontmatter,
    get_skill,
    get_skill_registry,
)
from rossum_agent.tools import INTERNAL_TOOLS, execute_tool, get_internal_tool_names
from rossum_agent.tools.skills import load_skill


class TestParseFrontmatter:
    """Test YAML frontmatter parsing."""

    def test_parses_valid_frontmatter(self):
        text = "---\nname: My Skill\ndescription: does things\n---\n# Body\n"
        meta, body = _parse_frontmatter(text)
        assert meta == {"name": "My Skill", "description": "does things"}
        assert body == "# Body\n"

    def test_returns_empty_meta_when_no_frontmatter(self):
        text = "# Just a heading\n\nSome content."
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_handles_values_with_colons(self):
        text = "---\ndescription: list datasets, search entries, debug matching\n---\nBody\n"
        meta, _body = _parse_frontmatter(text)
        assert meta["description"] == "list datasets, search entries, debug matching"

    def test_handles_backticks_in_values(self):
        text = "---\ndescription: use `execute_python` + `write_file(...)` to save\n---\nBody\n"
        meta, _body = _parse_frontmatter(text)
        assert "`execute_python`" in meta["description"]

    def test_strips_whitespace_from_keys_and_values(self):
        text = "---\n  name  :  Spaced Skill  \n---\nBody\n"
        meta, _body = _parse_frontmatter(text)
        assert meta["name"] == "Spaced Skill"

    def test_parses_yaml_list_values(self):
        text = "---\nname: My Skill\ntools:\n  - get\n  - patch_schema\n  - search\n---\nBody\n"
        meta, body = _parse_frontmatter(text)
        assert meta["name"] == "My Skill"
        assert meta["tools"] == ["get", "patch_schema", "search"]
        assert body == "Body\n"

    def test_parses_yaml_list_at_end_of_frontmatter(self):
        text = "---\nname: My Skill\ndescription: test\ntools:\n  - alpha\n  - beta\n---\nBody\n"
        meta, _body = _parse_frontmatter(text)
        assert meta["tools"] == ["alpha", "beta"]
        assert meta["name"] == "My Skill"
        assert meta["description"] == "test"


class TestSkill:
    """Test Skill dataclass."""

    def test_skill_creation(self):
        skill = Skill(
            name="Test Skill",
            content="# Test Content",
            file_path=Path("/test/test-skill.md"),
        )
        assert skill.name == "Test Skill"
        assert skill.content == "# Test Content"
        assert skill.slug == "test-skill"

    def test_slug_removes_extension(self):
        skill = Skill(
            name="My Skill",
            content="content",
            file_path=Path("/path/to/my-skill.md"),
        )
        assert skill.slug == "my-skill"

    def test_description_defaults_to_empty(self):
        skill = Skill(name="X", content="Y", file_path=Path("/x.md"))
        assert skill.description == ""

    def test_description_from_constructor(self):
        skill = Skill(name="X", content="Y", file_path=Path("/x.md"), description="does X")
        assert skill.description == "does X"

    def test_mcp_tools_defaults_to_empty_list(self):
        skill = Skill(name="X", content="Y", file_path=Path("/x.md"))
        assert skill.mcp_tools == []

    def test_mcp_tools_from_constructor(self):
        skill = Skill(name="X", content="Y", file_path=Path("/x.md"), mcp_tools=["patch_schema", "get"])
        assert skill.mcp_tools == ["patch_schema", "get"]


class TestSkillRegistry:
    """Test SkillRegistry class."""

    def test_loads_skills_from_directory(self):
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "test-skill.md"
            skill_file.write_text("# Test Skill\n\nThis is a test.")

            registry = SkillRegistry(Path(tmpdir))
            skills = registry.get_all_skills()

            assert len(skills) == 1
            assert skills[0].slug == "test-skill"
            assert "This is a test" in skills[0].content

    def test_loads_frontmatter_metadata(self):
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text("---\nname: Custom Name\ndescription: does custom things\n---\n# Body\n")

            registry = SkillRegistry(Path(tmpdir))
            skill = registry.get_skill("my-skill")

            assert skill is not None
            assert skill.name == "Custom Name"
            assert skill.description == "does custom things"
            assert skill.content == "# Body\n"
            assert skill.mcp_tools == []

    def test_loads_mcp_tools_from_frontmatter_inline(self):
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text("---\nname: My Skill\nmcp_tools: patch_schema, get, search\n---\n# Body\n")

            registry = SkillRegistry(Path(tmpdir))
            skill = registry.get_skill("my-skill")

            assert skill is not None
            assert skill.mcp_tools == ["patch_schema", "get", "search"]

    def test_loads_mcp_tools_from_frontmatter_bullet_list(self):
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text(
                "---\nname: My Skill\nmcp_tools:\n  - get\n  - patch_schema\n  - search\n---\n# Body\n"
            )

            registry = SkillRegistry(Path(tmpdir))
            skill = registry.get_skill("my-skill")

            assert skill is not None
            assert skill.mcp_tools == ["get", "patch_schema", "search"]

    def test_loads_single_mcp_tool_from_frontmatter(self):
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text("---\nname: My Skill\nmcp_tools: patch_schema\n---\n# Body\n")

            registry = SkillRegistry(Path(tmpdir))
            skill = registry.get_skill("my-skill")

            assert skill is not None
            assert skill.mcp_tools == ["patch_schema"]

    def test_falls_back_to_filename_when_no_frontmatter(self):
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-cool-skill.md"
            skill_file.write_text("# No frontmatter here")

            registry = SkillRegistry(Path(tmpdir))
            skill = registry.get_skill("my-cool-skill")

            assert skill is not None
            assert skill.name == "My Cool Skill"
            assert skill.description == ""
            assert skill.content == "# No frontmatter here"

    def test_get_skill_by_slug(self):
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text("# My Skill")

            registry = SkillRegistry(Path(tmpdir))
            skill = registry.get_skill("my-skill")

            assert skill is not None
            assert skill.slug == "my-skill"

    def test_get_skill_returns_none_for_unknown(self):
        with TemporaryDirectory() as tmpdir:
            registry = SkillRegistry(Path(tmpdir))
            skill = registry.get_skill("nonexistent")
            assert skill is None

    def test_get_skill_names(self):
        with TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "skill-a.md").write_text("A")
            (Path(tmpdir) / "skill-b.md").write_text("B")

            registry = SkillRegistry(Path(tmpdir))
            names = registry.get_skill_names()

            assert set(names) == {"skill-a", "skill-b"}

    def test_handles_missing_directory(self):
        registry = SkillRegistry(Path("/nonexistent/path"))
        skills = registry.get_all_skills()
        assert skills == []

    def test_skills_are_cached(self):
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "cached.md"
            skill_file.write_text("content")

            registry = SkillRegistry(Path(tmpdir))
            registry.get_all_skills()

            (Path(tmpdir) / "new-file.md").write_text("new")

            assert len(registry.get_all_skills()) == 1


class TestLoadSkillTool:
    """Test load_skill internal tool."""

    def test_load_skill_is_registered(self):
        assert "load_skill" in get_internal_tool_names()

    def test_load_skill_returns_skill_content(self):
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "test-skill.md"
            skill_file.write_text("# Test Instructions\n\nDo this.")

            with (
                patch(
                    "rossum_agent.agent.skills._SKILLS_DIR",
                    Path(tmpdir),
                ),
                patch(
                    "rossum_agent.agent.skills._default_registry",
                    None,
                ),
            ):
                result = load_skill(name="test-skill")

                assert "success" in result
                assert "Test Instructions" in result

    def test_load_skill_strips_frontmatter_from_content(self):
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "fm-skill.md"
            skill_file.write_text("---\nname: FM Skill\ndescription: test\n---\n# Instructions\n\nBody here.")

            with (
                patch("rossum_agent.agent.skills._SKILLS_DIR", Path(tmpdir)),
                patch("rossum_agent.agent.skills._default_registry", None),
            ):
                result = load_skill(name="fm-skill")

                assert "success" in result
                assert "Instructions" in result
                assert "Body here" in result
                # Frontmatter should not appear in the instructions
                assert "description: test" not in result

    def test_load_skill_returns_error_for_unknown(self):
        with (
            TemporaryDirectory() as tmpdir,
            patch(
                "rossum_agent.agent.skills._SKILLS_DIR",
                Path(tmpdir),
            ),
            patch(
                "rossum_agent.agent.skills._default_registry",
                None,
            ),
        ):
            result = load_skill(name="nonexistent")

            assert "error" in result
            assert "not found" in result

    def test_execute_tool_integration(self):
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "deploy.md"
            skill_file.write_text("# Deploy Guide")

            with (
                patch(
                    "rossum_agent.agent.skills._SKILLS_DIR",
                    Path(tmpdir),
                ),
                patch(
                    "rossum_agent.agent.skills._default_registry",
                    None,
                ),
            ):
                result = execute_tool("load_skill", {"name": "deploy"}, INTERNAL_TOOLS)

                assert "success" in result
                assert "Deploy Guide" in result


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_get_skill_returns_skill(self):
        with TemporaryDirectory() as tmpdir:
            skill_file = Path(tmpdir) / "my-skill.md"
            skill_file.write_text("Content")

            with (
                patch(
                    "rossum_agent.agent.skills._SKILLS_DIR",
                    Path(tmpdir),
                ),
                patch(
                    "rossum_agent.agent.skills._default_registry",
                    None,
                ),
            ):
                skill = get_skill("my-skill")
                assert skill is not None
                assert skill.content == "Content"

    def test_get_skill_registry_creates_default(self):
        with patch(
            "rossum_agent.agent.skills._default_registry",
            None,
        ):
            registry = get_skill_registry()
            assert isinstance(registry, SkillRegistry)


class TestSkillRegistryErrorHandling:
    """Test SkillRegistry error handling."""

    def test_handles_corrupted_skill_file(self, tmp_path, caplog):
        import logging

        skill_file = tmp_path / "broken-skill.md"
        skill_file.write_text("Valid content")
        Path(skill_file).chmod(0o000)

        try:
            with caplog.at_level(logging.ERROR):
                registry = SkillRegistry(tmp_path)
                skills = registry.get_all_skills()

            assert len(skills) == 0
            assert "Failed to load skill" in caplog.text
        finally:
            Path(skill_file).chmod(0o644)
