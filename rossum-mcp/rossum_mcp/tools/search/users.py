from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.group import Group
from rossum_api.models.user import User

from rossum_mcp.tools.base import build_filters, graceful_list

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _list_users(
    client: AsyncRossumAPIClient,
    username: str | None = None,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    is_active: bool | None = None,
    is_organization_group_admin: bool | None = None,
    max_items: int | None = None,
) -> list[User]:
    logger.debug(f"Listing users: username={username}, email={email}")
    filters = build_filters(
        username=username, email=email, first_name=first_name, last_name=last_name, is_active=is_active
    )
    result = await graceful_list(client, Resource.User, "user", max_items=max_items, **filters)
    users_list = result.items

    if is_organization_group_admin is not None:
        roles_result = await graceful_list(client, Resource.Group, "user_role")
        org_admin_role_urls: set[str] = {
            group.url for group in roles_result.items if group.name == "organization_group_admin"
        }
        if is_organization_group_admin:
            users_list = [user for user in users_list if set(user.groups) & org_admin_role_urls]
        else:
            users_list = [user for user in users_list if not (set(user.groups) & org_admin_role_urls)]

    return users_list


async def _list_user_roles(client: AsyncRossumAPIClient, max_items: int | None = None) -> list[Group]:
    logger.debug("Listing user roles")
    result = await graceful_list(client, Resource.Group, "user_role", max_items=max_items)
    return result.items
