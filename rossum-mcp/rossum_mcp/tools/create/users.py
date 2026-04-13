from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rossum_api.models.user import User

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient


async def _create_user(
    client: AsyncRossumAPIClient,
    username: str,
    email: str,
    queues: list[str] | None = None,
    groups: list[str] | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    is_active: bool = True,
    metadata: dict | None = None,
    oidc_id: str | None = None,
    auth_type: str = "password",
) -> User | dict:
    organization = await anext(client.list_organizations())

    user_data: dict[str, Any] = {
        "username": username,
        "email": email,
        "organization": organization.url,
        "is_active": is_active,
        "auth_type": auth_type,
    }
    if queues is not None:
        user_data["queues"] = queues
    if groups is not None:
        user_data["groups"] = groups
    if first_name is not None:
        user_data["first_name"] = first_name
    if last_name is not None:
        user_data["last_name"] = last_name
    if metadata is not None:
        user_data["metadata"] = metadata
    if oidc_id is not None:
        user_data["oidc_id"] = oidc_id

    user: User = await client.create_new_user(user_data)
    return user


def register_user_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Create a user (requires username + email). Use list_user_roles for role/group URLs; queue/group fields take full API URLs.",
        tags={"users", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_user(
        username: str,
        email: str,
        queues: list[str] | None = None,
        groups: list[str] | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        is_active: bool = True,
        metadata: dict | None = None,
        oidc_id: str | None = None,
        auth_type: str = "password",
    ) -> User | dict:
        return await _create_user(
            client, username, email, queues, groups, first_name, last_name, is_active, metadata, oidc_id, auth_type
        )
