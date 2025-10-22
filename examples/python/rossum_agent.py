#!/usr/bin/env python3
"""Rossum Document Processing Agent

AI agent that interacts with the Rossum MCP server to upload and process documents.

Usage:
    python rossum_agent.py

Environment Variables:
    ROSSUM_API_TOKEN: Rossum API authentication token
    ROSSUM_API_BASE_URL: Rossum API base URL
    LLM_API_BASE_URL: LLM API endpoint URL
    LLM_MODEL_ID: (Optional) LLM model identifier
"""

import argparse
import importlib.resources
import os
import sys

import yaml
from file_system_tools import get_file_info, list_files, read_file
from instructions import SYSTEM_PROMPT
from internal_tools import copy_queue_knowledge, retrieve_queue_status
from plot_tools import plot_data
from smolagents import CodeAgent, LiteLLMModel

from rossum_mcp.tools import parse_annotation_content, rossum_mcp_tool

# Constants
DEFAULT_LLM_MODEL = "openai/Qwen/Qwen3-Next-80B-A3B-Instruct-FP8"


def create_agent(stream_outputs: bool = False) -> CodeAgent:
    """Create and configure the Rossum agent with custom tools and instructions."""
    llm = LiteLLMModel(
        model_id=os.environ.get("LLM_MODEL_ID", DEFAULT_LLM_MODEL),
        api_base=os.environ["LLM_API_BASE_URL"],
        api_key="not_needed",
    )

    prompt_templates = yaml.safe_load(
        importlib.resources.files("smolagents.prompts").joinpath("code_agent.yaml").read_text()
    )

    prompt_templates["system_prompt"] += "\n" + SYSTEM_PROMPT

    return CodeAgent(
        tools=[
            rossum_mcp_tool,
            parse_annotation_content,
            list_files,
            read_file,
            get_file_info,
            plot_data,
            # Rossum internal tools
            copy_queue_knowledge,
            retrieve_queue_status,
        ],
        model=llm,
        prompt_templates=prompt_templates,
        additional_authorized_imports=[
            "collections",
            "datetime",
            "itertools",
            "json",
            "math",
            "os",
            "pathlib",
            "queue",
            "random",
            "re",
            "rossum_api.models.annotation",
            "stat",
            "statistics",
            "time",
            "unicodedata",
        ],
        stream_outputs=stream_outputs,
    )


def _check_env_vars() -> None:
    """Validate required environment variables are set."""
    required_vars = {
        "ROSSUM_API_TOKEN": "Rossum API authentication token",
        "ROSSUM_API_BASE_URL": "Rossum API base URL",
        "LLM_API_BASE_URL": "LLM API endpoint URL",
    }

    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print("❌ Missing required environment variables:\n")
        for var in missing:
            print(f"  {var}: {required_vars[var]}")
            print(f"  Set with: export {var}=<value>\n")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-hardcoded-prompt", action="store_true")
    parser.add_argument("--stream-outputs", action="store_true")
    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    """Main entry point - run interactive agent CLI."""
    print("🤖 Rossum Invoice Processing Agent")
    print("=" * 50)

    _check_env_vars()

    print("\n🔧 Initializing agent...")
    agent = create_agent(args.stream_outputs)

    print("\n" + "=" * 50)
    print("Agent ready! You can now give instructions.")
    print("Example: 'Upload all invoices from the data folder'")
    print("Type 'quit' to exit")
    print("=" * 50 + "\n")

    if args.use_hardcoded_prompt:
        #         prompt = """1. Upload all invoices from `/Users/daniel.stancl/projects/rossum-mcp/examples/data` folder to Rossum to the queue 3901094.
        #     - Do not include documents from `knowledge` folder.
        # 2. Once you send all annotations, wait for a few seconds.
        # 3. Then, start checking annotation status. Once all are imported, return a list of all annotations_urls
        # 4. Fetch the schema for the target queue.
        # 5. Identify the schema field IDs for:
        #     - Line item description field
        #     - Line item total amount field
        # 6. Retrieve all annotations in 'to_review' state from queue 3901094
        # 7. For each document:
        #     - Extract all line items
        #     - Create a dictionary mapping {item_description: item_amount_total}
        #     - If multiple line items share the same description, sum their amounts
        #     - Print result for each document
        # 8. Aggregate across all documents: sum amounts for each unique description
        # 9. Return the final dictionary: {description: total_amount_across_all_docs}
        # 10. Using the retrieved data, generate bar plot displaying revenue by services. Sort it in descending order. Store it interactive `revenue.html`.

        # Proceed step-by-step and show intermediate results after each major step."""

        prompt = """1. Create a new queue in the same namespace as queue `3904204`.
2. Set up the same schema field as queue `3904204`.
3. Update schema so that everything with confidence > 90% will be automated.
4. Rename the queue to: MCP Air Waybills
5. Copy the queue knowledge from `3904204`.
6. Return the queue status to check the queue status.
7. Upload all documents from `examples/data/splitting_and_sorting/knowledge/air_waybill` to the new queue.
8. Wait until all annotations are processed.
9. Finally, return queue URL and an automation rate (exported documents).

Proceed step-by-step and show intermediate results after each major step."""

        agent.run(prompt)

    while True:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 Goodbye!")
                break

            if not user_input:
                continue

            response = agent.run(user_input)
            print(f"\n🤖 Agent: {response}\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e!s}\n")


if __name__ == "__main__":
    main(parse_args())
