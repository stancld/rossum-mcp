"""Create and configure the Rossum agent with custom tools and instructions."""

import importlib.resources
import os

import yaml
from mcp import StdioServerParameters
from smolagents import CodeAgent, LiteLLMModel, MCPClient

from rossum_agent.file_system_tools import get_file_info, list_files, read_file
from rossum_agent.instructions import SYSTEM_PROMPT
from rossum_agent.internal_tools import copy_queue_knowledge, retrieve_queue_status
from rossum_agent.plot_tools import plot_data

DEFAULT_LLM_MODEL = "openai/Qwen/Qwen3-Next-80B-A3B-Instruct-FP8"


def create_agent(stream_outputs: bool = False) -> CodeAgent:
    """Create and configure the Rossum agent with custom tools and instructions.

    This agent uses MCP (Model Context Protocol) to connect directly to the Rossum MCP server,
    which provides tools for document processing via the Rossum API.

    Args:
        stream_outputs: Whether to stream outputs from the agent

    Returns:
        Configured CodeAgent with Rossum MCP tools and custom tools
    """
    llm = LiteLLMModel(
        model_id="bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
        # model_id=os.environ.get("LLM_MODEL_ID", DEFAULT_LLM_MODEL),
        # api_base=os.environ["LLM_API_BASE_URL"],
        # api_key="not_needed",
    )

    prompt_templates = yaml.safe_load(
        importlib.resources.files("smolagents.prompts").joinpath("code_agent.yaml").read_text()
    )

    prompt_templates["system_prompt"] += "\n" + SYSTEM_PROMPT

    # Configure MCP server connection to Rossum
    server_params = StdioServerParameters(
        command="rossum-mcp",
        args=[],
        env={
            "ROSSUM_API_BASE_URL": os.environ["ROSSUM_API_BASE_URL"],
            "ROSSUM_API_TOKEN": os.environ["ROSSUM_API_TOKEN"],
            **os.environ,
        },
    )

    # Connect to MCP server and get tools
    mcp_client = MCPClient(server_params)
    mcp_tools = mcp_client.get_tools()

    # Combine MCP tools with custom tools
    all_tools = [
        *mcp_tools,  # All Rossum MCP tools from server.py
        list_files,
        read_file,
        get_file_info,
        plot_data,
        # Rossum internal tools
        copy_queue_knowledge,
        retrieve_queue_status,
    ]

    return CodeAgent(
        tools=all_tools,
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
            "posixpath",
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
