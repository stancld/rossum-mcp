"""CLI for testing API SSE events."""

from __future__ import annotations

import argparse
import os
import sys

import httpx


def main() -> None:
    """Send a prompt to the API and print SSE events."""
    parser = argparse.ArgumentParser(description="Test Rossum Agent API SSE events")
    parser.add_argument("prompt", nargs="?", help="Prompt to send")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="API base URL")
    args = parser.parse_args()

    token = os.environ.get("ROSSUM_API_TOKEN")
    rossum_url = os.environ.get("ROSSUM_API_BASE_URL")

    if not token or not rossum_url:
        print("Error: ROSSUM_API_TOKEN and ROSSUM_API_BASE_URL required")
        sys.exit(1)

    prompt = args.prompt or input("Prompt: ")
    headers = {"X-Rossum-Token": token, "X-Rossum-Api-Url": rossum_url}

    with httpx.Client(timeout=300) as client:
        resp = client.post(f"{args.api_url}/api/v1/chats", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        chat_id = data.get("id") or data.get("chat_id")
        print(f"Created chat: {chat_id} (response: {data})\n")

        print(f"{'=' * 60}\nSSE EVENTS:\n{'=' * 60}")
        with client.stream(
            "POST", f"{args.api_url}/api/v1/chats/{chat_id}/messages", headers=headers, json={"content": prompt}
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    print(line)


if __name__ == "__main__":
    main()
