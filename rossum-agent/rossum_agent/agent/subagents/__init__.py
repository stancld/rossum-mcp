"""Subagent system for specialized task delegation.

This module provides a multi-agent orchestration pattern where the lead agent
can spawn specialized subagents for specific tasks.
"""

from __future__ import annotations

from rossum_agent.agent.subagents.registry import (
    SubagentRegistry,
    get_subagent_registry,
)
from rossum_agent.agent.subagents.runner import SubagentRunner, run_subagent
from rossum_agent.agent.subagents.types import (
    SubagentDefinition,
    SubagentResult,
    SubagentType,
)

__all__ = [
    "SubagentDefinition",
    "SubagentRegistry",
    "SubagentResult",
    "SubagentRunner",
    "SubagentType",
    "get_subagent_registry",
    "run_subagent",
]
