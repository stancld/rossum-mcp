"""Create and configure the Rossum agent with custom tools and instructions."""

from __future__ import annotations

import importlib.resources
import os

import yaml
from mcp import StdioServerParameters
from smolagents import CodeAgent, LiteLLMModel, MCPClient

from rossum_agent.file_system_tools import get_file_info, list_files, read_file, write_file
from rossum_agent.hook_analysis_tools import (
    analyze_hook_dependencies,
    explain_hook_execution_order,
    visualize_hook_tree,
)
from rossum_agent.instructions import SYSTEM_PROMPT
from rossum_agent.internal_tools import (
    copy_queue_knowledge,
    get_splitting_and_sorting_hook_code,
    retrieve_queue_status,
)
from rossum_agent.plot_tools import plot_data

DEFAULT_LLM_MODEL = "bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"


def create_agent(stream_outputs: bool = False) -> CodeAgent:
    """Create and configure the Rossum agent with custom tools and instructions.

    This agent uses MCP (Model Context Protocol) to connect directly to the Rossum MCP server,
    which provides tools for document processing via the Rossum API.

    The agent uses AWS Bedrock for LLM capabilities. Set LLM_MODEL_ID environment variable
    to specify a Bedrock model (e.g., "bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0").
    You must be logged into your AWS account with appropriate Bedrock access.

    Args:
        stream_outputs: Whether to stream outputs from the agent

    Returns:
        Configured CodeAgent with Rossum MCP tools and custom tools
    """
    llm = LiteLLMModel(
        model_id=os.environ.get("LLM_MODEL_ID", DEFAULT_LLM_MODEL),
        # Limit the number of requests to avoid being kicked by AWS Bedrock
        requests_per_minute=5.0,
    )

    prompt_templates = yaml.safe_load(
        importlib.resources.files("smolagents.prompts").joinpath("code_agent.yaml").read_text()
    )

    prompt_templates["system_prompt"] += "\n" + "\n".join(
        [SYSTEM_PROMPT, "Proceed step-by-step and show intermediate results after each major step."]
    )

    # Configure MCP server connection to Rossum
    server_params = StdioServerParameters(
        command="rossum-mcp",
        args=[],
        env={
            "ROSSUM_API_BASE_URL": os.environ["ROSSUM_API_BASE_URL"],
            "ROSSUM_API_TOKEN": os.environ["ROSSUM_API_TOKEN"],
            "ROSSUM_MCP_MODE": os.environ.get("ROSSUM_MCP_MODE", "read-write"),
            **os.environ,
        },
    )

    # Connect to MCP server and get tools
    mcp_client = MCPClient(server_params, structured_output=False)
    mcp_tools = mcp_client.get_tools()

    # Combine MCP tools with custom tools
    all_tools = [
        *mcp_tools,  # All Rossum MCP tools from server.py
        list_files,
        read_file,
        write_file,
        get_file_info,
        plot_data,
        # Rossum internal tools
        copy_queue_knowledge,
        retrieve_queue_status,
        get_splitting_and_sorting_hook_code,
        # Hook analysis tools
        analyze_hook_dependencies,
        visualize_hook_tree,
        explain_hook_execution_order,
    ]

    return CodeAgent(
        tools=all_tools,
        model=llm,
        prompt_templates=prompt_templates,
        additional_authorized_imports=[
            "collections",
            "copy",
            "datetime",
            "itertools",
            "json",
            "math",
            "os",
            "pathlib",
            "posixpath",
            "pprint",
            "queue",
            "random",
            "re",
            "rossum_api.*",
            "stat",
            "statistics",
            "time",
            "traceback",
            "unicodedata",
        ],
        stream_outputs=stream_outputs,
        max_steps=50,
    )
