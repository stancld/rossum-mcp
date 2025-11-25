"""Rule operations handler for Rossum MCP Server"""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from mcp.types import Tool

from rossum_mcp.handlers.base import BaseHandler

if TYPE_CHECKING:
    from rossum_api.models.rule import Rule

logger = logging.getLogger(__name__)


class RulesHandler(BaseHandler):
    """Handler for rule-related operations"""

    @classmethod
    def get_tool_definitions(cls) -> list[Tool]:
        """Get list of tool definitions for rule operations."""
        return [
            Tool(
                name="list_rules",
                description="List all rules. Returns: count, results array with rule details (id, name, url, enabled, organization, schema, trigger_condition, created_by, created_at, modified_by, modified_at, rule_template, synchronized_from_template, actions).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema_id": {
                            "type": ["integer", "null"],
                            "description": "Optional schema ID to filter rules by schema",
                        },
                        "organization_id": {
                            "type": ["integer", "null"],
                            "description": "Optional organization ID to filter rules by organization",
                        },
                        "enabled": {
                            "type": ["boolean", "null"],
                            "description": "Optional filter by enabled status (true/false)",
                        },
                    },
                },
            ),
        ]

    async def list_rules(
        self, schema_id: int | None = None, organization_id: int | None = None, enabled: bool | None = None
    ) -> dict:
        """List all rules, optionally filtered by schema, organization, and enabled status.

        Args:
            schema_id: Optional schema ID to filter rules by schema
            organization_id: Optional organization ID to filter rules by organization
            enabled: Optional boolean to filter by enabled status

        Returns:
            Dictionary containing count and results list of rules
        """
        logger.debug(f"Listing rules: schema_id={schema_id}, organization_id={organization_id}, enabled={enabled}")

        # Build filter parameters
        filters: dict = {}
        if schema_id is not None:
            filters["schema"] = schema_id
        if organization_id is not None:
            filters["organization"] = organization_id
        if enabled is not None:
            filters["enabled"] = enabled

        rules_list: list[Rule] = [rule async for rule in self.client.list_rules(**filters)]

        return {
            "count": len(rules_list),
            "results": [dataclasses.asdict(rule) for rule in rules_list],
        }
