"""Rossum internal tools for not yet publish endpoints."""

import json

import requests

try:
    from smolagents import tool
except ImportError as e:
    raise ImportError(
        "The 'smolagents' package is required to use rossum_mcp.tools. Install it with: pip install rossum-mcp[tools]"
    ) from e

NEIGHBORS_API_HOST: str = "localhost"
NEIGHBORS_API_PORT: int = 5000
DEFAULT_BACKBONE = "240219T122821-great-hawking.135k.tenet"


@tool
def copy_queue_knowledge(
    source_queue_url: str,
    target_queue_url: str,
    created_after: str | None = None,
    created_before: str | None = None,
    confirmed_after: str | None = None,
    confirmed_before: str | None = None,
    backbone_ids: str | None = DEFAULT_BACKBONE,
    delete_existing: bool = False,
) -> str:
    """Copy knowledge from source queue to target queue.

    Args:
        source_queue_url: URL of the source queue to copy knowledge from
        target_queue_url: URL of the target queue to copy knowledge to
        created_after: ISO format datetime string to filter annotations created after this date
        created_before: ISO format datetime string to filter annotations created before this date
        confirmed_after: ISO format datetime string to filter annotations confirmed after this date
        confirmed_before: ISO format datetime string to filter annotations confirmed before this date
        backbone_ids: Comma-separated string of backbone IDs to filter (e.g., "id1,id2,id3")
            Default backbone_ids = 240219T122821-great-hawking.135k.tenet.
        delete_existing: Whether to delete existing knowledge in target queue (default: False)

    Returns:
        JSON string with operation result. Use json.loads() to parse.
        Errors are returned with an "error" field.

    Example:
        # Copy all knowledge from source to target
        result = copy_queue_knowledge(
            source_queue_url="https://api.elis.rossum.ai/v1/queues/12345",
            target_queue_url="https://api.elis.rossum.ai/v1/queues/67890"
        )
        data = json.loads(result)
        if "error" not in data:
            print("Knowledge copied successfully")

        # Copy knowledge with filters
        result = copy_queue_knowledge(
            source_queue_url="https://api.elis.rossum.ai/v1/queues/12345",
            target_queue_url="https://api.elis.rossum.ai/v1/queues/67890",
            created_after="2024-01-01T00:00:00Z",
            delete_existing=True
        )
    """
    try:
        # Build the endpoint URL
        url = f"http://{NEIGHBORS_API_HOST}:{NEIGHBORS_API_PORT}/copy_queue_knowledge"

        # Build the request payload
        payload = {
            "source_queue_url": source_queue_url,
            "target_queue_url": target_queue_url,
            "delete_existing": delete_existing,
        }

        # Add optional datetime filters
        if created_after:
            payload["created_after"] = created_after
        if created_before:
            payload["created_before"] = created_before
        if confirmed_after:
            payload["confirmed_after"] = confirmed_after
        if confirmed_before:
            payload["confirmed_before"] = confirmed_before

        # Parse backbone_ids if provided
        if backbone_ids:
            payload["backbone_ids"] = [bid.strip() for bid in backbone_ids.split(",")]

        # Make the POST request
        response = requests.post(url, json=payload, timeout=300)  # 5 minute timeout
        response.raise_for_status()

        return json.dumps(response.json(), indent=2)

    except requests.exceptions.RequestException as e:
        return json.dumps({"error": f"Request failed: {e!s}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {e!s}"})


@tool
def retrieve_queue_status(queue_url: str) -> str:
    """Retrieve the status of a queue for a specific version.

    Args:
        queue_url: URL of the queue to check status for

    Returns:
        JSON string with queue status information. Use json.loads() to parse.
        Errors are returned with an "error" field.

    Example:
        # Get queue status for a specific version
        result = retrieve_queue_status(
            queue_url="https://api.elis.rossum.ai/v1/queues/12345",
            version="v1.0"
        )
        data = json.loads(result)
        if "error" not in data:
            print(f"Queue status: {data}")
    """
    try:
        # Build the endpoint URL
        url = f"http://{NEIGHBORS_API_HOST}:{NEIGHBORS_API_PORT}/queue/status"

        # Build the request payload
        payload = {"elis_queue_url": queue_url, "version": DEFAULT_BACKBONE}

        # Make the POST request
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        return json.dumps(response.json(), indent=2)

    except requests.exceptions.RequestException as e:
        return json.dumps({"error": f"Request failed: {e!s}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {e!s}"})
