"""Tests for the execute_python tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from rossum_agent.tools.core import AgentContext, set_context
from rossum_agent.tools.python_exec import execute_python, get_execute_python_definition


class TestGetExecPythonDefinition:
    def test_contains_expected_fields(self) -> None:
        definition = get_execute_python_definition()

        assert definition["name"] == "execute_python"
        assert "description" in definition
        assert definition["input_schema"]["required"] == ["code"]

    def test_does_not_list_helper_functions(self) -> None:
        definition = get_execute_python_definition()

        assert "schema_content(value)" not in definition["description"]
        assert "suggest_formula_field" not in definition["description"]
        assert "prefer `write_file(...)` inside the snippet" in definition["description"]
        assert "Load the relevant skill first" in definition["description"]


class TestExecPython:
    def test_returns_last_expression(self) -> None:
        result = execute_python(code="1 + 2")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == 3

    def test_prefers_result_variable_when_no_last_expression(self) -> None:
        result = execute_python(code="x = 2\nresult = x + 5")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == 7

    def test_captures_stdout(self) -> None:
        result = execute_python(code='print("hello")\nresult = "ok"')
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == "ok"
        assert parsed["stdout"] == "hello\n"

    @patch("rossum_agent.python_tools.copilot.rule.suggest_rule")
    def test_exposes_rule_helper(self, mock_suggest_rule) -> None:
        mock_suggest_rule.return_value = json.dumps(
            {"status": "success", "name": "Rule", "trigger_condition": "field.amount_total > 0", "actions": []}
        )

        result = execute_python(
            code='result = suggest_rule(user_query="Check total", queue_id=123)',
            operation_name="suggest rule",
        )
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["operation_name"] == "suggest rule"
        assert parsed["result"]["name"] == "Rule"
        mock_suggest_rule.assert_called_once_with(user_query="Check total", queue_id=123)

    @patch("rossum_agent.python_tools.copilot.formula.suggest_formula_field")
    def test_exposes_copilot_namespace(self, mock_suggest_formula_field) -> None:
        mock_suggest_formula_field.return_value = json.dumps({"status": "success", "formula": "field.amount_total"})

        result = execute_python(
            code=(
                "result = copilot.suggest_formula_field("
                'label="Amount Copy", hint="Copy amount", schema_id=1, section_id="header"'
                ")"
            )
        )
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"]["formula"] == "field.amount_total"

    @patch("rossum_agent.tools.python_exec._call_mcp_tool")
    def test_exposes_api_get_helper(self, mock_call_mcp_tool) -> None:
        mock_call_mcp_tool.return_value = {"content": [{"id": "header"}]}

        result = execute_python(code='result = api_get("schema", 123)')
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == {"content": [{"id": "header"}]}
        mock_call_mcp_tool.assert_called_once_with("get", {"entity": "schema", "entity_id": 123})

    def test_open_reads_relative_file_inside_workspace(self, tmp_path: Path) -> None:
        file_path = tmp_path / "example.txt"
        file_path.write_text("hello", encoding="utf-8")

        set_context(AgentContext(output_dir=tmp_path))
        try:
            result = execute_python(code='f = open("example.txt")\ndata = f.read()\nf.close()\ndata')
            parsed = json.loads(result)
        finally:
            set_context(AgentContext())

        assert parsed["status"] == "success"
        assert parsed["result"] == "hello"

    def test_open_rejects_path_outside_workspace(self, tmp_path: Path) -> None:
        outside_file = tmp_path.parent / "outside.txt"
        outside_file.write_text("secret", encoding="utf-8")

        set_context(AgentContext(output_dir=tmp_path))
        try:
            result = execute_python(code=f'result = open("{outside_file}").read()')
            parsed = json.loads(result)
        finally:
            set_context(AgentContext())

        assert parsed["status"] == "error"
        assert "inside workspace or /var" in parsed["error"]

    def test_open_allows_read_only_var_paths(self, tmp_path: Path) -> None:
        actual_path = tmp_path.resolve() / "var-allowed.txt"
        actual_path.write_text("from-var", encoding="utf-8")
        var_path = Path(str(actual_path).replace("/private/var/", "/var/", 1))

        set_context(AgentContext(output_dir=tmp_path))
        try:
            result = execute_python(code=f'result = open("{var_path}").read()')
            parsed = json.loads(result)
        finally:
            set_context(AgentContext())

        assert parsed["status"] == "success"
        assert parsed["result"] == "from-var"

    def test_allows_try_except(self) -> None:
        result = execute_python(code="try:\n  x = 1 / 0\nexcept ZeroDivisionError:\n  x = 42\nx")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == 42

    def test_rejects_try_star(self) -> None:
        result = execute_python(code="try:\n  pass\nexcept* ValueError:\n  pass")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "TryStar" in parsed["error"]

    def test_rejects_imports(self) -> None:
        result = execute_python(code="import os\nresult = 1")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "Import" in parsed["error"]

    def test_allows_import_json(self) -> None:
        result = execute_python(code="import json\nresult = json.loads('{\"ok\": true}')")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == {"ok": True}

    def test_allows_from_json_import(self) -> None:
        result = execute_python(code='from json import dumps\nresult = dumps({"value": 1})')
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == '{"value": 1}'

    def test_allows_stdlib_imports(self) -> None:
        result = execute_python(code="from collections import Counter\nresult = dict(Counter(['a', 'b', 'a']))")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == {"a": 2, "b": 1}

    def test_allows_import_re(self) -> None:
        result = execute_python(code='import re\nresult = bool(re.match(r"\\d+", "123"))')
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] is True

    def test_allows_import_pathlib(self) -> None:
        result = execute_python(code='from pathlib import Path\nresult = str(Path("/home") / "test.txt")')
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == "/home/test.txt"

    def test_rejects_non_allowed_from_import(self) -> None:
        result = execute_python(code="from os import path\nresult = 1")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "ImportFrom" in parsed["error"]

    def test_rejects_dunder_attribute_access(self) -> None:
        result = execute_python(code="result = copilot.__class__")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "Attributes starting with '__'" in parsed["error"]

    def test_schema_content_accepts_full_schema_object(self) -> None:
        result = execute_python(
            code=(
                'schema = {"id": 123, "content": [{"id": "header", "category": "section", "children": []}]}\n'
                "result = schema_content(schema)"
            )
        )
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == [{"id": "header", "category": "section", "children": []}]

    def test_schema_content_accepts_unified_get_response(self) -> None:
        result = execute_python(
            code=(
                'schema = {"entity": "schema", "id": 123, "data": {"content": [{"id": "header"}]}}\n'
                "result = schema_content(schema)"
            )
        )
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == [{"id": "header"}]

    def test_schema_content_accepts_bare_content_array(self) -> None:
        result = execute_python(code='result = schema_content([{"id": "header"}])')
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == [{"id": "header"}]

    def test_schema_content_rejects_non_schema_payload(self) -> None:
        result = execute_python(code='result = schema_content({"id": 123})')
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "schema_content()" in parsed["error"]

    def test_ord_builtin_available(self) -> None:
        result = execute_python(code="ord('A')")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == 65

    def test_allows_with_statement(self, tmp_path: Path) -> None:
        file_path = tmp_path / "example.txt"
        file_path.write_text("hello", encoding="utf-8")

        set_context(AgentContext(output_dir=tmp_path))
        try:
            result = execute_python(code='with open("example.txt") as f:\n    data = f.read()\ndata')
            parsed = json.loads(result)
        finally:
            set_context(AgentContext())

        assert parsed["status"] == "success"
        assert parsed["result"] == "hello"

    def test_execute_python_alias_matches_execute_python(self) -> None:
        assert json.loads(execute_python(code="1 + 2"))["result"] == 3
