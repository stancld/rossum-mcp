from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence  # noqa: TC003 - needed at runtime for FastMCP
from typing import TYPE_CHECKING

import anyio
from fastmcp.exceptions import ToolError

from rossum_mcp.tools.base import build_resource_url

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _upload_document(client: AsyncRossumAPIClient, file_path: str, queue_id: int) -> dict:
    path = anyio.Path(file_path)

    try:
        task = (await client.upload_document(queue_id, [(str(path), path.name)]))[0]
    except FileNotFoundError as e:
        raise ToolError(f"File not found: {file_path}") from e
    except KeyError as e:
        logger.error(f"Upload failed - unexpected API response format: {e!s}")
        error_msg = (
            f"Document upload failed - API response missing expected key {e!s}. "
            f"This usually means either:\n"
            f"1. The queue_id ({queue_id}) is invalid or you don't have access to it\n"
            f"2. The Rossum API returned an error response\n"
            f"Please verify:\n"
            f"- The queue_id is correct and exists in your workspace\n"
            f"- You have permission to upload documents to this queue\n"
            f"- Your API token has the necessary permissions"
        )
        raise ToolError(error_msg) from e
    except IndexError as e:
        logger.error(f"Upload failed - no tasks returned: {e}")
        raise ToolError(
            f"Document upload failed - no tasks were created. This may indicate the queue_id ({queue_id}) is invalid."
        ) from e
    except Exception as e:
        logger.error(f"Upload failed: {type(e).__name__}: {e}")
        raise ToolError(f"Document upload failed: {type(e).__name__}: {e!s}") from e

    return {
        "task_id": task.id,
        "task_status": task.status,
        "queue_id": queue_id,
        "message": 'Document upload initiated. Use `search(query={"entity": "annotation", "queue_id": ...})` to find the annotation ID for this queue.',
    }


async def _copy_annotations(
    client: AsyncRossumAPIClient,
    base_url: str,
    annotation_ids: Sequence[int],
    target_queue_id: int,
    target_status: str | None = None,
    reimport: bool = False,
) -> dict:
    target_queue_url = build_resource_url(base_url, "queues", target_queue_id)
    params = {"reimport": "true"} if reimport else {}

    async def _copy_one(annotation_id: int) -> dict:
        payload: dict = {"target_queue": target_queue_url}
        if target_status is not None:
            payload["target_status"] = target_status
        return await client._http_client.request_json(
            method="POST",
            url=f"annotations/{annotation_id}/copy",
            json=payload,
            params=params,
        )

    responses = await asyncio.gather(*[_copy_one(aid) for aid in annotation_ids], return_exceptions=True)

    results: list[dict] = []
    errors: list[dict] = []
    for annotation_id, response in zip(annotation_ids, responses, strict=True):
        if isinstance(response, Exception):
            errors.append({"annotation_id": annotation_id, "error": f"{type(response).__name__}: {response!s}"})
        else:
            results.append({"annotation_id": annotation_id, "copied_annotation": response})

    return {"copied": len(results), "failed": len(errors), "results": results, "errors": errors}
