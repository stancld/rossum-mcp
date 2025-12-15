"""Subagent registry for managing specialized agent definitions.

This module provides the registry that holds all available subagent definitions
and their configurations.
"""

from __future__ import annotations

from rossum_agent.agent.subagents.types import SubagentDefinition, SubagentType
from rossum_agent.prompts.subagents import (
    DOCUMENT_ANALYZER_PROMPT,
    HOOK_DEBUGGER_PROMPT,
    RULE_OPTIMIZER_PROMPT,
    SCHEMA_EXPERT_PROMPT,
)

DOCUMENT_ANALYZER_TOOLS = [
    "get_annotation",
    "get_annotation_content",
    "list_annotations",
    "get_queue",
]

HOOK_DEBUGGER_TOOLS = [
    "get_hook",
    "list_hooks",
    "get_queue",
    "visualize_hook_tree",
]

SCHEMA_EXPERT_TOOLS = [
    "get_schema",
    "list_schemas",
    "get_queue",
]

RULE_OPTIMIZER_TOOLS = [
    "list_rules",
    "get_schema",
    "get_queue",
]


class SubagentRegistry:
    """Registry for managing subagent definitions.

    Provides access to predefined specialized subagents and their configurations.
    """

    def __init__(self) -> None:
        """Initialize the registry with default subagent definitions."""
        self._definitions: dict[SubagentType, SubagentDefinition] = {
            SubagentType.DOCUMENT_ANALYZER: SubagentDefinition(
                type=SubagentType.DOCUMENT_ANALYZER,
                description="Specializes in analyzing document annotations, extraction results, and data quality.",
                tools=DOCUMENT_ANALYZER_TOOLS,
                system_prompt=DOCUMENT_ANALYZER_PROMPT,
                max_steps=10,
            ),
            SubagentType.HOOK_DEBUGGER: SubagentDefinition(
                type=SubagentType.HOOK_DEBUGGER,
                description="Expert at debugging extensions, webhooks, and hook configurations.",
                tools=HOOK_DEBUGGER_TOOLS,
                system_prompt=HOOK_DEBUGGER_PROMPT,
                max_steps=15,
            ),
            SubagentType.SCHEMA_EXPERT: SubagentDefinition(
                type=SubagentType.SCHEMA_EXPERT,
                description="Specializes in schema configuration, field analysis, and formula field dependencies.",
                tools=SCHEMA_EXPERT_TOOLS,
                system_prompt=SCHEMA_EXPERT_PROMPT,
                max_steps=10,
            ),
            SubagentType.RULE_OPTIMIZER: SubagentDefinition(
                type=SubagentType.RULE_OPTIMIZER,
                description="Expert at analyzing and optimizing business rules and validation logic.",
                tools=RULE_OPTIMIZER_TOOLS,
                system_prompt=RULE_OPTIMIZER_PROMPT,
                max_steps=10,
            ),
        }

    def get(self, subagent_type: SubagentType) -> SubagentDefinition:
        """Get a subagent definition by type.

        Args:
            subagent_type: The type of subagent to retrieve.

        Returns:
            The SubagentDefinition for the specified type.

        Raises:
            KeyError: If the subagent type is not registered.
        """
        if subagent_type not in self._definitions:
            raise KeyError(f"Unknown subagent type: {subagent_type}")
        return self._definitions[subagent_type]

    def get_by_name(self, name: str) -> SubagentDefinition:
        """Get a subagent definition by name string.

        Args:
            name: The string name of the subagent type (e.g., "document_analyzer").

        Returns:
            The SubagentDefinition for the specified type.

        Raises:
            ValueError: If the name doesn't match any subagent type.
        """
        try:
            subagent_type = SubagentType(name)
        except ValueError as e:
            valid_types = [t.value for t in SubagentType]
            raise ValueError(f"Unknown subagent type: '{name}'. Valid types: {valid_types}") from e
        return self.get(subagent_type)

    def list_all(self) -> list[SubagentDefinition]:
        """Get all registered subagent definitions.

        Returns:
            List of all SubagentDefinition objects.
        """
        return list(self._definitions.values())

    def list_types(self) -> list[SubagentType]:
        """Get all registered subagent types.

        Returns:
            List of all SubagentType enum values.
        """
        return list(self._definitions.keys())


_registry: SubagentRegistry | None = None


def get_subagent_registry() -> SubagentRegistry:
    """Get the global subagent registry instance.

    Returns:
        The singleton SubagentRegistry instance.
    """
    global _registry
    if _registry is None:
        _registry = SubagentRegistry()
    return _registry
