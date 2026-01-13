"""Rule tools for Rossum MCP Server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.models.rule import Rule

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_rule(client: AsyncRossumAPIClient, rule_id: int) -> Rule:
    logger.debug(f"Retrieving rule: rule_id={rule_id}")
    rule: Rule = await client.retrieve_rule(rule_id)
    return rule


async def _list_rules(
    client: AsyncRossumAPIClient,
    schema_id: int | None = None,
    organization_id: int | None = None,
    enabled: bool | None = None,
) -> list[Rule]:
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


def register_rule_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register rule-related tools with the FastMCP server."""

    @mcp.tool(description="Retrieve rule details.")
    async def get_rule(rule_id: int) -> Rule:
        return await _get_rule(client, rule_id)

    @mcp.tool(description="List all rules.")
    async def list_rules(
        schema_id: int | None = None, organization_id: int | None = None, enabled: bool | None = None
    ) -> list[Rule]:
        return await _list_rules(client, schema_id, organization_id, enabled)
