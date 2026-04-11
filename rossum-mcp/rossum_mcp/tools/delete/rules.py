from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_mcp.tools.base import delete_resource

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient


async def _delete_rule(client: AsyncRossumAPIClient, rule_id: int) -> dict:
    return await delete_resource("rule", rule_id, client.delete_rule)
