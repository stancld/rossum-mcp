from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rossum_agent.agent.system_prompt import build_skill_catalog, get_system_prompt


class TestSystemPromptPersona:
    def test_includes_default_persona_block(self):
        prompt = get_system_prompt("default")
        assert "# Persona: default" in prompt
        assert "# Persona: cautious" not in prompt

    def test_includes_cautious_persona_block(self):
        prompt = get_system_prompt("cautious")
        assert "# Persona: cautious" in prompt
        assert "# Persona: default" not in prompt


class TestSystemPromptMCPMode:
    def test_read_only_by_default(self):
        prompt = get_system_prompt("default")
        assert "Mode: READ-ONLY" in prompt
        assert "refuse all write operations immediately" in prompt

    def test_read_only_explicit(self):
        prompt = get_system_prompt("default", mcp_mode="read-only")
        assert "Mode: READ-ONLY" in prompt
        assert "refuse all write operations immediately" in prompt

    def test_read_write(self):
        prompt = get_system_prompt("default", mcp_mode="read-write")
        assert "Mode: read-write" in prompt
        assert "write operations are allowed" in prompt
        assert "READ-ONLY" not in prompt


class TestSystemPromptTaskTracking:
    def test_requires_update_task_transitions(self):
        prompt = get_system_prompt("default")
        assert 'update_task(status="in_progress")' in prompt
        assert 'update_task(status="completed")' in prompt

    def test_does_not_forbid_update_task(self):
        prompt = get_system_prompt("default")
        assert "Do not call `update_task`" not in prompt


class TestSystemPromptSchemaInstructions:
    def test_python_execution_skill_mentions_write_file(self):
        prompt = get_system_prompt("default")
        assert "use `execute_python` + `write_file(...)` to save the fetched payload directly" in prompt

    def test_python_execution_is_skill_referenced(self):
        prompt = get_system_prompt("default")
        assert '`load_skill("python-execution")`' in prompt
        assert "schema_content(...)" not in prompt

    def test_run_jq_requires_jq_syntax(self):
        prompt = get_system_prompt("default")
        assert "`run_jq` expects real jq syntax" in prompt
        assert "`?`, `//`, and `tonumber?`" in prompt


class TestBuildSkillCatalog:
    def test_generates_catalog_from_frontmatter(self):
        with TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "alpha.md").write_text("---\nname: Alpha\ndescription: does alpha\n---\n# Alpha\n")
            (Path(tmpdir) / "beta.md").write_text("---\nname: Beta\ndescription: does beta\n---\n# Beta\n")

            with (
                patch("rossum_agent.agent.skills._SKILLS_DIR", Path(tmpdir)),
                patch("rossum_agent.agent.skills._default_registry", None),
            ):
                catalog = build_skill_catalog()

            assert "**Skills**" in catalog
            assert '`load_skill("alpha")` → does alpha' in catalog
            assert '`load_skill("beta")` → does beta' in catalog

    def test_catalog_is_sorted_alphabetically(self):
        with TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "zebra.md").write_text("---\nname: Zebra\ndescription: z-skill\n---\n# Z\n")
            (Path(tmpdir) / "aardvark.md").write_text("---\nname: Aardvark\ndescription: a-skill\n---\n# A\n")

            with (
                patch("rossum_agent.agent.skills._SKILLS_DIR", Path(tmpdir)),
                patch("rossum_agent.agent.skills._default_registry", None),
            ):
                catalog = build_skill_catalog()

            aardvark_pos = catalog.index("aardvark")
            zebra_pos = catalog.index("zebra")
            assert aardvark_pos < zebra_pos

    def test_all_real_skills_appear_in_prompt(self):
        """Every skill file in skills/ must appear in the generated system prompt."""
        prompt = get_system_prompt("default")
        expected_slugs = [
            "automation-setup",
            "document-testing",
            "formula-fields",
            "hooks",
            "lookup-fields",
            "master-data-hub",
            "python-execution",
            "reasoning-fields",
            "rules-and-actions",
            "schema-patching",
            "txscript",
            "ui-settings",
        ]
        for slug in expected_slugs:
            assert f'load_skill("{slug}")' in prompt, f"Skill {slug} missing from prompt"
