"""Prompt templates for the Rossum Agent.

This package contains shared prompt content and specialized prompt builders
for different agent paradigms (tool-use, code-execution).
"""

from __future__ import annotations

from rossum_agent.prompts.base_prompt import (
    CONFIGURATION_WORKFLOWS,
    CORE_CAPABILITIES,
    CRITICAL_REQUIREMENTS,
    DOCUMENTATION_WORKFLOWS,
    OUTPUT_FORMATTING,
    ROSSUM_EXPERT_INTRO,
    get_shared_prompt_sections,
)
from rossum_agent.prompts.system_prompt import (
    get_system_prompt,
    get_system_prompt_with_tools_summary,
)

__all__ = [
    "CONFIGURATION_WORKFLOWS",
    "CORE_CAPABILITIES",
    "CRITICAL_REQUIREMENTS",
    "DOCUMENTATION_WORKFLOWS",
    "OUTPUT_FORMATTING",
    "ROSSUM_EXPERT_INTRO",
    "get_shared_prompt_sections",
    "get_system_prompt",
    "get_system_prompt_with_tools_summary",
]
