"""Pre-commit hook to detect dead module-level functions in production code."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PRODUCTION_PACKAGES = [
    REPO_ROOT / "rossum-mcp" / "rossum_mcp",
    REPO_ROOT / "rossum-agent" / "rossum_agent",
    REPO_ROOT / "rossum-agent-client" / "rossum_agent_client",
]

EXCLUDED_DIRS = {"tests", "__pycache__", ".venv", "regression_tests", "scripts", "alembic"}

# Decorators that register functions externally (framework callbacks, tools, routes)
REGISTRATION_DECORATORS = {
    "mcp.tool",
    "beta_tool",
    "router.post",
    "router.get",
    "router.put",
    "router.patch",
    "router.delete",
    "limiter.limit",
    "app.post",
    "app.get",
    "app.put",
    "app.patch",
    "app.delete",
    "app.on_event",
    "pytest.fixture",
}


def collect_production_files() -> dict[Path, str]:
    """Return {path: source_text} for all production .py files."""
    files: dict[Path, str] = {}
    for package_dir in PRODUCTION_PACKAGES:
        if not package_dir.is_dir():
            continue
        for py_file in package_dir.rglob("*.py"):
            if any(part in EXCLUDED_DIRS for part in py_file.parts):
                continue
            try:
                files[py_file] = py_file.read_text()
            except OSError:
                continue
    return files


def _decorator_name(node: ast.expr) -> str:
    """Extract dotted name from a decorator node."""
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    if isinstance(node, ast.Attribute):
        prefix = _decorator_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _has_registration_decorator(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in func_node.decorator_list:
        name = _decorator_name(dec)
        if name in REGISTRATION_DECORATORS:
            return True
    return False


def _get_all_exports(source: str) -> set[str]:
    """Parse __all__ from source if present."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, ast.List | ast.Tuple)
                ):
                    return {
                        elt.value
                        for elt in node.value.elts
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    }
    return set()


def _parse_entry_points() -> set[str]:
    """Collect function names referenced in [project.scripts] across all pyproject.toml files."""
    entry_funcs: set[str] = set()
    for toml_path in REPO_ROOT.rglob("pyproject.toml"):
        if any(part in EXCLUDED_DIRS for part in toml_path.parts):
            continue
        try:
            content = toml_path.read_text()
        except OSError:
            continue
        # Simple regex to extract "module.path:func_name" values
        in_scripts = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "[project.scripts]":
                in_scripts = True
                continue
            if in_scripts:
                if stripped.startswith("["):
                    break
                match = re.search(r'=\s*"[^"]*:(\w+)"', stripped)
                if match:
                    entry_funcs.add(match.group(1))
    return entry_funcs


def collect_definitions(files: dict[Path, str], entry_points: set[str]) -> list[tuple[Path, int, str]]:
    """Return [(file, lineno, func_name)] for candidate functions."""
    definitions: list[tuple[Path, int, str]] = []
    for path, source in files.items():
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue

        all_exports = _get_all_exports(source)

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue

            name = node.name

            # Skip dunders
            if name.startswith("__") and name.endswith("__"):
                continue

            # Skip registration-decorated functions
            if _has_registration_decorator(node):
                continue

            # Skip __all__ exports
            if name in all_exports:
                continue

            # Skip entry points
            if name in entry_points:
                continue

            definitions.append((path, node.lineno, name))

    return definitions


def find_dead_functions(
    files: dict[Path, str], definitions: list[tuple[Path, int, str]]
) -> list[tuple[Path, int, str]]:
    """Return [(file, lineno, name)] for functions with no detected usage."""
    dead: list[tuple[Path, int, str]] = []

    for def_path, lineno, name in definitions:
        pattern = re.compile(rf"\b{re.escape(name)}\b")
        found = False

        for path, source in files.items():
            if path == def_path:
                # In the defining file, skip the def line itself
                for i, line in enumerate(source.splitlines(), 1):
                    if i == lineno:
                        continue
                    if pattern.search(line):
                        found = True
                        break
            else:
                if pattern.search(source):
                    found = True
            if found:
                break

        if not found:
            dead.append((def_path, lineno, name))

    return dead


def main() -> int:
    files = collect_production_files()
    entry_points = _parse_entry_points()
    definitions = collect_definitions(files, entry_points)

    if not (dead := find_dead_functions(files, definitions)):
        return 0

    dead.sort(key=lambda t: (str(t[0]), t[1]))

    print("\nDead function(s) detected:\n")
    for path, lineno, name in dead:
        rel = path.relative_to(REPO_ROOT)
        print(f"  {rel}:{lineno}  {name}")

    print(f"\nFound {len(dead)} dead function(s). Remove them.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
