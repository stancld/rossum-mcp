"""Subagent-specific prompts for specialized task execution."""

from __future__ import annotations

from rossum_agent.prompts.subagents.document_analyzer import DOCUMENT_ANALYZER_PROMPT
from rossum_agent.prompts.subagents.hook_debugger import HOOK_DEBUGGER_PROMPT
from rossum_agent.prompts.subagents.rule_optimizer import RULE_OPTIMIZER_PROMPT
from rossum_agent.prompts.subagents.schema_expert import SCHEMA_EXPERT_PROMPT

__all__ = [
    "DOCUMENT_ANALYZER_PROMPT",
    "HOOK_DEBUGGER_PROMPT",
    "RULE_OPTIMIZER_PROMPT",
    "SCHEMA_EXPERT_PROMPT",
]
