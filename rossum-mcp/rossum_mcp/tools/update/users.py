from __future__ import annotations

import logging
from typing import cast

from fastmcp import FastMCP
from rossum_api import AsyncRossumAPIClient
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.user import User

from rossum_mcp.tools.base import build_filters

logger = logging.getLogger(__name__)


async def _update_user(
    client: AsyncRossumAPIClient,
    user_id: int,
    username: str | None = None,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    queues: list[str] | None = None,
    groups: list[str] | None = None,
    is_active: bool | None = None,
    metadata: dict | None = None,
    oidc_id: str | None = None,
    auth_type: str | None = None,
    ui_settings: dict | None = None,
) -> User | dict:
    logger.debug(f"Updating user: user_id={user_id}")

    patch_data = build_filters(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        queues=queues,
        groups=groups,
        is_active=is_active,
        metadata=metadata,
        oidc_id=oidc_id,
        auth_type=auth_type,
        ui_settings=ui_settings,
    )

    updated_user_data = await client._http_client.update(Resource.User, user_id, patch_data)
    return cast("User", client._deserializer(Resource.User, updated_user_data))


def register_user_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Patch a user; only provided fields change. Use list_user_roles for role/group URLs.",
        tags={"users", "write"},
        annotations={"readOnlyHint": False},
    )
    async def update_user(
        user_id: int,
        username: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        queues: list[str] | None = None,
        groups: list[str] | None = None,
        is_active: bool | None = None,
        metadata: dict | None = None,
        oidc_id: str | None = None,
        auth_type: str | None = None,
        ui_settings: dict | None = None,
    ) -> User | dict:
        return await _update_user(
            client,
            user_id,
            username,
            email,
            first_name,
            last_name,
            queues,
            groups,
            is_active,
            metadata,
            oidc_id,
            auth_type,
            ui_settings,
        )
