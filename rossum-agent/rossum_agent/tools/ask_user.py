"""Tool for the agent to ask the user a structured question."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rossum_agent.tools.core import AgentQuestion, AgentQuestionItem, QuestionOption, get_context

if TYPE_CHECKING:
    from anthropic.types import ToolParam

MAX_DESCRIPTION_LENGTH = 90

_OPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {
            "type": "string",
            "description": "Machine-readable identifier for this option.",
        },
        "label": {
            "type": "string",
            "description": "Short display label shown to the user.",
        },
        "description": {
            "type": "string",
            "description": "Optional explanation (max 90 chars).",
        },
    },
    "required": ["value", "label"],
}


def get_ask_user_question_definition() -> ToolParam:
    """Get the tool definition for ask_user_question."""
    return {
        "name": "ask_user_question",
        "description": (
            "Ask the user one or more questions, optionally with multiple-choice options. "
            "Use when you need required information that you cannot determine on your own "
            "(e.g. queue name, template choice, workspace). "
            "Also use when the user explicitly asks you to confirm before proceeding. "
            "After calling this tool, STOP — do not call other tools or produce text in the same turn."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Single question to ask. For multiple questions, use `questions` instead.",
                },
                "options": {
                    "type": "array",
                    "items": _OPTION_SCHEMA,
                    "description": "Optional list of choices for the single question. Omit for free-text.",
                },
                "multi_select": {
                    "type": "boolean",
                    "description": "If true, user can select multiple options. Default false. Only with single `question`.",
                },
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The question text.",
                            },
                            "options": {
                                "type": "array",
                                "items": _OPTION_SCHEMA,
                                "description": "Optional list of choices. Omit for free-text.",
                            },
                            "multi_select": {
                                "type": "boolean",
                                "description": "If true, user can select multiple options. Default false.",
                            },
                        },
                        "required": ["question"],
                    },
                    "description": (
                        "Multiple questions presented one at a time with individual input controls. "
                        "Use instead of `question` when you need several pieces of information."
                    ),
                },
            },
        },
    }


def _parse_options(raw_options: list[dict[str, str]] | None) -> list[QuestionOption]:
    return [
        QuestionOption(
            value=opt["value"],
            label=opt["label"],
            description=opt.get("description", "")[:MAX_DESCRIPTION_LENGTH],
        )
        for opt in (raw_options or [])
    ]


def _build_question_items(
    question: str | None,
    options: list[dict[str, str]] | None,
    multi_select: bool,
    questions: list[dict[str, object]] | None,
) -> list[AgentQuestionItem]:
    if questions:
        return [
            AgentQuestionItem(
                question=str(q["question"]),
                options=_parse_options(q.get("options")),  # ty:ignore[invalid-argument-type]
                multi_select=bool(q.get("multi_select", False)),
            )
            for q in questions
        ]
    return [
        AgentQuestionItem(
            question=question or "",
            options=_parse_options(options),
            multi_select=multi_select,
        )
    ]


def ask_user_question(
    question: str | None = None,
    options: list[dict[str, str]] | None = None,
    multi_select: bool = False,
    questions: list[dict[str, object]] | None = None,
) -> str:
    items = _build_question_items(question, options, multi_select, questions)

    agent_question = AgentQuestion(questions=items)
    ctx = get_context()
    ctx.report_question(agent_question)

    result: dict[str, str | int] = {
        "status": "question_sent",
        "question_count": len(items),
    }
    if len(items) == 1:
        result["question"] = items[0].question
        if items[0].options:
            result["option_count"] = len(items[0].options)
    return json.dumps(result)
