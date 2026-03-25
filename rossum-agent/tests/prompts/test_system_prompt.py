from __future__ import annotations

from rossum_agent.system_prompt import get_system_prompt


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
