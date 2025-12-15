"""Rule tools for Rossum MCP Server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.models.rule import Rule  # noqa: TC002 - needed at runtime for FastMCP

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def register_rule_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register rule-related tools with the FastMCP server."""

    @mcp.tool(description="Retrieve rule details.")
    async def get_rule(rule_id: int) -> Rule:
        """Retrieve rule details."""
        logger.debug(f"Retrieving rule: rule_id={rule_id}")
        rule: Rule = await client.retrieve_rule(rule_id)
        return rule

    @mcp.tool(description="List all rules.")
    async def list_rules(
        schema_id: int | None = None, organization_id: int | None = None, enabled: bool | None = None
    ) -> list[Rule]:
        """List all rules, optionally filtered by schema, organization, and enabled status."""
        logger.debug(f"Listing rules: schema_id={schema_id}, organization_id={organization_id}, enabled={enabled}")
        filters: dict = {}
        if schema_id is not None:
            filters["schema"] = schema_id
        if organization_id is not None:
            filters["organization"] = organization_id
        if enabled is not None:
            filters["enabled"] = enabled

        rules_list: list[Rule] = [rule async for rule in client.list_rules(**filters)]
        return rules_list
