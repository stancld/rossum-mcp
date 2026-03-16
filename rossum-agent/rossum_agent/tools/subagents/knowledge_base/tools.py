"""KB tools used by the sub-agent: grep, get_article, python_exec."""

from __future__ import annotations

import ast
import io
import json
import logging
import re
from contextlib import redirect_stdout

from anthropic import beta_tool

from rossum_agent.tools.subagents.knowledge_base.cache import cache
from rossum_agent.tools.subagents.knowledge_base.ranking import (
    article_display_title,
    build_article_payload,
    make_snippet,
    persist_article_payload,
    rank_article,
)

logger = logging.getLogger(__name__)

_GREP_MATCH_LIMIT = 200
_GREP_OUTPUT_LIMIT = 50000
_ARTICLE_OUTPUT_LIMIT = 50000

_MAX_CODE_LENGTH = 8000
_MAX_EXEC_OUTPUT = 30000

_ALLOWED_MODULES = frozenset({"collections", "itertools", "json", "math", "re", "statistics", "textwrap"})

_SAFE_BUILTINS: dict[str, object] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "getattr": getattr,
    "hasattr": hasattr,
    "int": int,
    "isinstance": isinstance,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "ord": ord,
    "print": print,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
}

_DISALLOWED_AST_NODES = (
    ast.AsyncFor,
    ast.AsyncFunctionDef,
    ast.AsyncWith,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.TryStar,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)

spillover: list[dict[str, str]] = []


def _grep_match_articles(
    articles: list[dict[str, str]], compiled: re.Pattern[str], pattern: str
) -> list[tuple[int, dict[str, str]]]:
    matches: list[tuple[int, dict[str, str]]] = []
    for article in articles:
        title = article_display_title(article)
        content = article.get("content", "")
        slug = article.get("slug", "")
        url = article.get("url", "")

        title_match = compiled.search(title)
        content_match = compiled.search(content)

        if title_match or content_match:
            parts = []
            if title_match:
                parts.append(f"[title] {title}")
            if content_match:
                parts.append(f"[content] {make_snippet(content, content_match)}")
            rank_score = rank_article(article, pattern)["score"]
            if title_match:
                rank_score += 50
            matches.append((rank_score, {"slug": slug, "title": title, "url": url, "snippet": "\n".join(parts)}))
    return matches


@beta_tool
def kb_grep(pattern: str, case_insensitive: bool = True) -> str:
    """Search Knowledge Base article titles and content by keyword or regex.

    Use to discover relevant articles when you don't know the exact slug.
    Returns matching articles with short snippets around each match.
    When results are truncated, the full list is saved to spillover -- use
    kb_python_exec to filter with: `[m for m in spillover if 'keyword' in m['snippet']]`

    Examples: "document splitting", "webhook", "email_template", "formula"

    Args:
        pattern: Text pattern to search for (supports regex).
        case_insensitive: Whether to ignore case (default: True).

    Returns:
        Matching articles with snippets showing context around matches.
    """
    global spillover
    logger.debug(f"kb_grep called with pattern: {pattern!r}")

    if not pattern or not pattern.strip():
        return json.dumps({"status": "error", "message": "Empty pattern not allowed"})

    try:
        data = cache.load()
    except (ValueError, OSError) as e:
        logger.exception("Error loading KB data")
        return json.dumps({"status": "error", "message": f"Error loading KB data: {e}"})

    try:
        compiled = re.compile(pattern, re.IGNORECASE if case_insensitive else 0)
    except re.error as e:
        return json.dumps({"status": "error", "message": f"Invalid regex pattern: {e}"})

    articles = data.get("articles", [])
    matches = _grep_match_articles(articles, compiled, pattern)

    if not matches:
        spillover = []
        return json.dumps({"status": "success", "result": "No matches found"})

    matches.sort(key=lambda item: item[0], reverse=True)
    ordered_matches = [match for _, match in matches]
    total_matches = len(matches)

    spillover = ordered_matches

    if total_matches > _GREP_MATCH_LIMIT:
        ordered_matches = ordered_matches[:_GREP_MATCH_LIMIT]

    result = json.dumps({"status": "success", "matches": total_matches, "result": ordered_matches})

    if len(result) > _GREP_OUTPUT_LIMIT:
        while ordered_matches and len(result) > _GREP_OUTPUT_LIMIT:
            ordered_matches.pop()
            result = json.dumps(
                {
                    "status": "success",
                    "matches": total_matches,
                    "showing": len(ordered_matches),
                    "spillover": total_matches,
                    "result": ordered_matches,
                }
            )

    return result


def resolve_article_by_slug(
    articles: list[dict[str, str]], slug: str
) -> tuple[dict[str, str] | None, list[str] | None]:
    """Resolve a slug to a single article, supporting unique partial matches."""
    for article in articles:
        if article.get("slug", "") == slug:
            return article, None

    slug_lower = slug.lower()
    partial_matches = [article for article in articles if slug_lower in article.get("slug", "").lower()]
    if len(partial_matches) == 1:
        return partial_matches[0], None
    if len(partial_matches) > 1:
        return None, [article.get("slug", "") for article in partial_matches[:10]]
    return None, None


@beta_tool
def kb_get_article(slug: str) -> str:
    """Persist a Knowledge Base article by slug so the sub-agent can inspect it with run_jq.

    Use after kb_grep to retrieve a specific article. On success, the full article JSON is
    written to the output directory and the response includes `article_path` for `run_jq`.
    If persistence fails, returns inline content as a fallback.

    Args:
        slug: Article slug (e.g. "document-splitting-extension"). Partial match supported.

    Returns:
        Persisted article metadata and path, or error if not found.
    """
    logger.debug(f"kb_get_article called with slug: {slug!r}")
    try:
        data = cache.load()
    except (ValueError, OSError) as e:
        logger.exception("Error loading KB data")
        return json.dumps({"status": "error", "message": f"Error loading KB data: {e}"})

    articles = data.get("articles", [])

    def _serialize(article: dict[str, str]) -> str:
        article_payload = build_article_payload(article)
        persisted = persist_article_payload(article.get("slug", ""), article_payload)
        if persisted["status"] == "success":
            return json.dumps(
                {
                    "status": "success",
                    "slug": article.get("slug", ""),
                    "title": article_display_title(article),
                    "url": article.get("url", ""),
                    "article_path": persisted["path"],
                    "article_jq_hint": persisted["jq_hint"],
                    "result": (
                        "Article persisted for follow-up jq queries. "
                        "Use `run_jq(article_jq_hint, article_path)` to inspect the content."
                    ),
                }
            )

        content = article.get("content", "")
        if len(content) > _ARTICLE_OUTPUT_LIMIT:
            content = content[:_ARTICLE_OUTPUT_LIMIT] + "\n... (truncated)"
        return json.dumps(
            {
                "status": "success",
                "slug": article["slug"],
                "title": article_display_title(article),
                "url": article.get("url", ""),
                "message": "Article persistence failed, returning inline content fallback",
                "article_error": persisted["error"],
                "content": content,
            }
        )

    article, candidates = resolve_article_by_slug(articles, slug)
    if article is not None:
        return _serialize(article)
    if candidates:
        return json.dumps({"status": "error", "message": f"Ambiguous slug '{slug}', candidates: {candidates}"})

    return json.dumps({"status": "error", "message": f"No article found matching slug: {slug}"})


def _validate_kb_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                if not all(alias.name in _ALLOWED_MODULES for alias in node.names):
                    raise ValueError(f"Import not allowed: {ast.dump(node)}")
            elif node.level != 0 or node.module not in _ALLOWED_MODULES:
                raise ValueError(f"Import not allowed: {node.module}")
            continue
        if isinstance(node, _DISALLOWED_AST_NODES):
            raise ValueError(f"{type(node).__name__} is not allowed")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("Names starting with '__' are not allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Attributes starting with '__' are not allowed")


def kb_python_exec(code: str) -> str:
    """Execute Python code with access to KB articles and grep spillover.

    Pre-loaded variables:
    - `articles`: list of all KB articles (each has slug, title, url, content)
    - `spillover`: list of last kb_grep matches (each has slug, title, url, snippet)
    - `re`, `json`, `collections`, `itertools` modules

    Assign result to `result` or leave as last expression.
    """
    if len(code) > _MAX_CODE_LENGTH:
        return json.dumps({"status": "error", "error": f"Code exceeds {_MAX_CODE_LENGTH} characters"})

    try:
        tree = ast.parse(code, mode="exec")
        _validate_kb_ast(tree)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})

    try:
        kb_data = cache.load()
        kb_articles = kb_data.get("articles", [])
    except (ValueError, OSError):
        kb_articles = []

    allowed_modules: dict[str, object] = {name: __import__(name) for name in _ALLOWED_MODULES}

    def _safe_import(name: str, *_args: object, **_kwargs: object) -> object:
        if name in allowed_modules:
            return allowed_modules[name]
        raise ImportError(f"Import not allowed: {name}")

    builtins = {**_SAFE_BUILTINS, "__import__": _safe_import}
    globals_dict: dict[str, object] = {"__builtins__": builtins}
    locals_dict: dict[str, object] = {
        "articles": kb_articles,
        "spillover": list(spillover),
        **allowed_modules,
    }

    stdout = io.StringIO()
    result_value: object = None

    try:
        with redirect_stdout(stdout):
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                prefix = ast.fix_missing_locations(ast.Module(body=tree.body[:-1], type_ignores=[]))
                suffix = ast.fix_missing_locations(ast.Expression(tree.body[-1].value))
                exec(compile(prefix, "<kb_python_exec>", "exec"), globals_dict, locals_dict)
                result_value = eval(compile(suffix, "<kb_python_exec>", "eval"), globals_dict, locals_dict)
            else:
                exec(compile(tree, "<kb_python_exec>", "exec"), globals_dict, locals_dict)
                result_value = locals_dict.get("result")
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": f"{type(e).__name__}: {e}", "stdout": stdout.getvalue() or None}
        )

    output = json.dumps(
        {"status": "success", "result": result_value, "stdout": stdout.getvalue() or None},
        default=str,
    )
    if len(output) > _MAX_EXEC_OUTPUT:
        output = output[:_MAX_EXEC_OUTPUT] + "\n... (truncated)"
    return output


KB_PYTHON_EXEC_TOOL: dict[str, object] = {
    "name": "kb_python_exec",
    "description": (
        "Run Python to analyze KB data. Pre-loaded: `articles` (all KB articles with slug/title/url/content), "
        "`spillover` (last kb_grep matches with slug/title/url/snippet), `re`, `json`, `collections`, `itertools`. "
        "Assign to `result` or use as last expression. "
        "Use to filter spillover after large grep, count matches, extract sections, or do multi-pattern analysis."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Max 8000 characters.",
            },
        },
        "required": ["code"],
    },
}
