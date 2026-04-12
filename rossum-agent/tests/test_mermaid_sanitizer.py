from __future__ import annotations

import pytest
from rossum_agent.api.mermaid_sanitizer import (
    sanitize_mermaid_block,
    sanitize_mermaid_in_markdown,
)


class TestQuoteSpecialLabels:
    @pytest.mark.parametrize(
        ("block", "expected"),
        [
            ("    A[Label (main)]\n", '    A["Label (main)"]\n'),
            ("    A[Label {details}]\n", '    A["Label {details}"]\n'),
        ],
        ids=["parentheses", "curly_braces"],
    )
    def test_quotes_label_with_special_chars(self, block: str, expected: str):
        assert sanitize_mermaid_block(block) == expected

    @pytest.mark.parametrize(
        "block",
        [
            '    A["Label (main)"]\n',
            "    A[Simple Label]\n",
            "    A[Label with spaces and numbers 123]\n",
        ],
        ids=["already_quoted", "simple", "spaces_and_numbers"],
    )
    def test_preserves_label(self, block: str):
        assert sanitize_mermaid_block(block) == block

    def test_multiple_labels_on_different_lines(self):
        block = "    A[Label (a)] --> B[Label (b)]\n"
        result = sanitize_mermaid_block(block)
        assert result == '    A["Label (a)"] --> B["Label (b)"]\n'

    def test_does_not_touch_click_directives(self):
        block = '    click A "#anchor"\n'
        result = sanitize_mermaid_block(block)
        assert result == block

    def test_does_not_touch_call_syntax(self):
        block = "    click A call myFunc\n"
        result = sanitize_mermaid_block(block)
        assert result == block


class TestSanitizeMermaidInMarkdown:
    def test_sanitizes_mermaid_block_in_markdown(self):
        text = "Here is the diagram:\n\n```mermaid\ngraph TD\n    A[Label (x)]\n```\n\nAnd some text."
        result = sanitize_mermaid_in_markdown(text)
        assert 'A["Label (x)"]' in result
        assert "And some text." in result

    def test_sanitizes_multiple_blocks(self):
        text = "```mermaid\ngraph TD\n    A[Label (a)]\n```\n\n```mermaid\ngraph LR\n    B[Label (b)]\n```\n"
        result = sanitize_mermaid_in_markdown(text)
        assert 'A["Label (a)"]' in result
        assert 'B["Label (b)"]' in result

    def test_leaves_non_mermaid_code_blocks(self):
        text = "```python\nA[Label (x)]\n```\n"
        result = sanitize_mermaid_in_markdown(text)
        assert result == text

    def test_leaves_text_without_mermaid(self):
        text = "Just plain text."
        result = sanitize_mermaid_in_markdown(text)
        assert result == text

    def test_incomplete_mermaid_block_ignored(self):
        text = "```mermaid\ngraph TD\n    A[Label (x)]\n"
        result = sanitize_mermaid_in_markdown(text)
        assert result == text

    def test_closing_fence_must_be_at_line_start(self):
        text = '```mermaid\ngraph TD\n    A["contains ``` backticks"]\n```\n'
        result = sanitize_mermaid_in_markdown(text)
        assert result == text

    def test_realistic_diagram(self):
        text = (
            "## Workflow\n\n"
            "```mermaid\n"
            "graph TD\n"
            "    Start[Document Upload]\n"
            "    Start --> Event1[annotation_status (2 hooks)]\n"
            "    style Event1 fill:#E8F4F8,stroke:#4A90E2,stroke-width:2px\n"
            '    Event1 --> Hook1["Validation Hook<br/>[function]"]\n'
            "    style Hook1 fill:#4A90E2,stroke:#2E5C8A,color:#fff\n"
            "    Event1 --> Done[Complete]\n"
            "\n"
            '    click Event1 "#annotation_status"\n'
            '    click Hook1 "#validation_hook"\n'
            "```\n"
        )
        result = sanitize_mermaid_in_markdown(text)
        assert 'click Event1 "#annotation_status"' in result
        assert 'click Hook1 "#validation_hook"' in result
        assert 'Event1["annotation_status (2 hooks)"]' in result
        assert 'Hook1["Validation Hook<br/>[function]"]' in result

    def test_idempotent(self):
        text = "```mermaid\ngraph TD\n    B[Label (test)]\n```\n"
        once = sanitize_mermaid_in_markdown(text)
        twice = sanitize_mermaid_in_markdown(once)
        assert once == twice
