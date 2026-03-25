"""Sanitize mermaid diagram syntax in markdown.

LLMs occasionally produce unquoted node labels containing parentheses or
curly braces, which mermaid.js interprets as shape modifiers and rejects.
See https://github.com/mermaid-js/mermaid/issues/7002.
"""

from __future__ import annotations

import re

_MERMAID_BLOCK_RE = re.compile(r"(```mermaid\s*\n)(.*?)(^```)", re.DOTALL | re.MULTILINE)

# NodeId[unquoted label with shape-conflict chars] → NodeId["quoted label"]
# Parentheses and curly braces inside [...] labels are ambiguous — mermaid
# tries to parse them as nested shape modifiers, causing syntax errors.
_UNQUOTED_BRACKET_LABEL_RE = re.compile(
    r'(\b[\w-]+)\[(?!")([^\]]*[(){}][^\]]*)\]',
)


def _quote_special_labels(block: str) -> str:
    """Quote node labels that contain shape-conflict characters."""
    return _UNQUOTED_BRACKET_LABEL_RE.sub(r'\1["\2"]', block)


def sanitize_mermaid_block(block: str) -> str:
    """Sanitize a single mermaid diagram block."""
    return _quote_special_labels(block)


def sanitize_mermaid_in_markdown(text: str) -> str:
    """Find and sanitize all mermaid code blocks in markdown text."""

    def _replace_block(match: re.Match) -> str:
        return f"{match.group(1)}{sanitize_mermaid_block(match.group(2))}{match.group(3)}"

    return _MERMAID_BLOCK_RE.sub(_replace_block, text)
