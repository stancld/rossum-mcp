"""User tools for Rossum MCP Server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.models.group import Group  # noqa: TC002 - needed at runtime for FastMCP
from rossum_api.models.user import User  # noqa: TC002 - needed at runtime for FastMCP

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def register_user_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(description="Retrieve a single user by ID. Use list_users first to find users by username/email.")
    async def get_user(user_id: int) -> User:
        user: User = await client.retrieve_user(user_id)
        return user

    @mcp.tool(
        description="List users. Filter by username/email to find specific users. Beware that users with 'organization_group_admin' role are special, e.g. cannot be used as token owners; you can filter them out with `is_organization_group_admin=False`."
    )
    async def list_users(
        username: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        is_active: bool | None = None,
        is_organization_group_admin: bool | None = None,
    ) -> list[User]:
        filter_mapping: dict = {
            "username": username,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "is_active": is_active,
        }
        filters = {k: v for k, v in filter_mapping.items() if v is not None}

        users_list: list[User] = [user async for user in client.list_users(**filters)]

        if is_organization_group_admin is not None:
            org_admin_role_urls: set[str] = {
                group.url async for group in client.list_user_roles() if group.name == "organization_group_admin"
            }
            if is_organization_group_admin:
                users_list = [user for user in users_list if set(user.groups) & org_admin_role_urls]
            else:
                users_list = [user for user in users_list if not (set(user.groups) & org_admin_role_urls)]

        return users_list

    @mcp.tool(description="List all user roles (groups of permissions) in the organization.")
    async def list_user_roles() -> list[Group]:
        groups_list: list[Group] = [group async for group in client.list_user_roles()]
        return groups_list
