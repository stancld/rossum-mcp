"""Rossum internal tools for not yet publish endpoints."""

import json
import os

import requests
from smolagents import tool

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
            "username": f"rossum-agent:{os.environ.get('USER', '')}",
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
        result = retrieve_queue_status(
            queue_url="https://api.elis.rossum.ai/v1/queues/12345",
            version="v1.0"
        )
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


@tool
def get_splitting_and_sorting_hook_code() -> str:
    """Return the python hook code for splitting & sorting inbox queue.

    Returns:
    String contaitning python hook code,
    """
    return """from __future__ import annotations

import itertools
import json

from rossum_api import ElisAPIClientSync
from txscript import TxScript


def rossum_hook_request_handler(payload: dict) -> dict:
    t = TxScript.from_payload(payload)
    client = get_rossum_client(payload)

    splits: list[tuple[list[str], int | None]] = get_splits(
        t,
        payload["annotation"]["pages"],
        payload["settings"].get("sorting_queues", {}),
        payload["settings"].get("max_blank_page_words"),
    )

    if not splits or (len(splits) == 1 and splits[0][1] is None):
        splits = [(payload["annotation"]["pages"], None)]

    event = payload["action"]
    if event in {"confirm", "export"}:
        split_document(
            client,
            payload["base_url"],
            payload["annotation"]["id"],
            splits,
        )
    elif event == "initialize":
        suggest_split(
            client,
            payload["base_url"],
            payload["annotation"]["url"],
            splits,
        )

    return t.hook_response()


def get_splits(
    t: TxScript,
    pages: list[str],
    queue_id_from_document_type: dict[str, int],
    max_blank_page_words: int | None,
) -> list[tuple[list[str], int | None]]:
    subdocuments = sorted(t.field.doc_split_subdocument.all_values, key=lambda v: v.attr.page)
    if max_blank_page_words is None:
        blank_page_indices = set()
    else:
        # NOTE: constant 10 must match BlankPageClassifier.MAX_WORDS from RIR codebase
        score_threshold = 10 / (10 + max_blank_page_words)
        blank_page_indices = {
            v.attr.page - 1
            for v in t.field.doc_split_blank_page.all_values
            if v.attr.rir_confidence >= score_threshold
        }

    indices = [subdocument.attr.page - 1 for subdocument in subdocuments]
    indices.append(len(pages))
    split_boundaries = list(itertools.pairwise(indices))

    splits: list[tuple[list[str], int | None]] = [
        (
            [pages[page_i] for page_i in range(begin, end) if page_i not in blank_page_indices],
            queue_id_from_document_type.get(subdocument),
        )
        for (begin, end), subdocument in zip(split_boundaries, subdocuments)
    ]
    # NOTE: filter out all-blank splits
    return [split for split in splits if split[0]]


def split_document(
    client: ElisAPIClientSync,
    base_url: str,
    annotation_id: int,
    splits: list[tuple[list[str], int | None]],
) -> None:
    documents = []

    for pages, target_queue in splits:
        document: dict = {
            "parent_pages": [{"page": page} for page in pages],
        }
        if target_queue:
            document["target_queue"] = f"{base_url}/api/v1/queues/{target_queue}"
        documents.append(document)

    body = {"edit": documents}
    # NOTE: shows up in extension logs for convenience
    print(json.dumps(body, indent=2))
    client.request_json("POST", f"annotations/{annotation_id}/edit_pages", json=body)


def suggest_split(
    client: ElisAPIClientSync,
    base_url: str,
    annotation_url: str,
    splits: list[tuple[list[str], int | None]],
) -> None:
    documents = []

    for pages, target_queue in splits:
        document: dict[str, list[dict[str, str]] | str] = {
            "pages": [{"page": page} for page in pages],
        }
        if target_queue:
            document["target_queue"] = f"{base_url}/api/v1/queues/{target_queue}"
        documents.append(document)

    body = {
        "annotation": annotation_url,
        "documents": documents,
    }
    # NOTE: shows up in extension logs for convenience
    print(json.dumps(body, indent=2))
    response = client.request_json("POST", "suggested_edits", json=body)
    print(response)


def get_rossum_client(payload: dict) -> ElisAPIClientSync:
    return ElisAPIClientSync(
        token=get_auth_token_from_payload(payload),
        base_url=payload["base_url"] + "/api/v1",
    )


def get_auth_token_from_payload(payload: dict) -> str:
    auth_token = payload.get("rossum_authorization_token")
    if not auth_token:
        raise RuntimeError(
            "Authorization token not found in the payload. "
            f"Configure Rossum API access at {payload['hook']}."
        )
    return auth_token"""
