from __future__ import annotations

import json
import logging
import tempfile
from typing import TYPE_CHECKING

import anyio
from rossum_api.models.annotation import Annotation

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_annotation_content(client: AsyncRossumAPIClient, annotation_id: int) -> dict:
    logger.debug(f"Retrieving annotation content: annotation_id={annotation_id}")
    annotation: Annotation = await client.retrieve_annotation(annotation_id, sideloads=("content",))
    path = anyio.Path(tempfile.gettempdir()) / f"rossum_annotation_{annotation_id}_content.json"
    await path.write_text(json.dumps(annotation.content, indent=2))
    return {"path": str(path)}


def register_annotation_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Fetch annotation extracted content and save to a local JSON file; returns the path for jq/grep.",
        tags={"annotations"},
        annotations={"readOnlyHint": True},
    )
    async def get_annotation_content(annotation_id: int) -> dict:
        return await _get_annotation_content(client, annotation_id)
