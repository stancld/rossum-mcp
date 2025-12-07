"""Create and configure the Rossum agent with custom tools and instructions."""

from __future__ import annotations

import importlib.resources
import os
from typing import TYPE_CHECKING

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
    is_neighbors_api_available,
    retrieve_queue_status,
)
from rossum_agent.plot_tools import plot_data

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Any, Literal

    from smolagents.models import ChatMessage, ChatMessageStreamDelta
    from smolagents.tools import Tool

DEFAULT_LLM_MODEL = "bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"


class LiteLLMBedrockModel(LiteLLMModel):
    """Use LiteLLM Python SDK with a convenient processing of AWS bedrock client kwargs.

    Smolagents AWSBedrockModel handles generation differently, which leads to unexpected errors.
    """

    def __init__(
        self,
        model_id: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        custom_role_conversions: dict[str, str] | None = None,
        flatten_messages_as_text: bool | None = None,
        client_kwargs: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model_id=model_id,
            api_base=api_base,
            api_key=api_key,
            custom_role_conversions=custom_role_conversions,
            flatten_messages_as_text=flatten_messages_as_text,
            **kwargs,
        )
        self.client_kwargs = client_kwargs or {}

    def generate(
        self,
        messages: list[ChatMessage | dict],
        stop_sequences: list[str] | None = None,
        response_format: dict[str, str] | None = None,
        tools_to_call_from: list[Tool] | None = None,
        **kwargs: Any,
    ) -> ChatMessage:
        # Hack: Drop incompatible model_id, which is passed inside from self.model_id
        kwargs.pop("model_id", None)
        return super().generate(
            messages=messages,
            stop_sequences=stop_sequences,
            response_format=response_format,
            tools_to_call_from=tools_to_call_from,
            **self.client_kwargs,
            **kwargs,
        )

    def generate_stream(
        self,
        messages: list[ChatMessage | dict],
        stop_sequences: list[str] | None = None,
        response_format: dict[str, str] | None = None,
        tools_to_call_from: list[Tool] | None = None,
        **kwargs: Any,
    ) -> Generator[ChatMessageStreamDelta]:
        # Hack: Drop incompatible model_id, which is passed inside from self.model_id
        kwargs.pop("model_id", None)
        yield from super().generate(
            messages=messages,
            stop_sequences=stop_sequences,
            response_format=response_format,
            tools_to_call_from=tools_to_call_from,
            **self.client_kwargs,
            **kwargs,
        )


def create_agent(
    rossum_api_token: str,
    rossum_api_base_url: str,
    mcp_mode: Literal["read-only", "read-write"] = "read-only",
    stream_outputs: bool = False,
) -> CodeAgent:
    """Create and configure the Rossum agent with custom tools and instructions.

    This agent uses MCP (Model Context Protocol) to connect directly to the Rossum MCP server,
    which provides tools for document processing via the Rossum API.

    The agent uses AWS Bedrock for LLM capabilities. Set LLM_MODEL_ID environment variable
    to specify a Bedrock model (e.g., "bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0").
    You must be logged into your AWS account with appropriate Bedrock access.

    Args:
        rossum_api_token: Rossum API token for authentication
        rossum_api_base_url: Rossum API base URL
        mcp_mode: MCP mod
        stream_outputs: Whether to stream outputs from the agent

    Returns:
        Configured CodeAgent with Rossum MCP tools and custom tools
    """
    bedrock_client_kwargs: dict[str, str] = {}
    if bedrock_model_arn := os.environ.get("AWS_BEDROCK_MODEL_ARN"):
        bedrock_client_kwargs["model_id"] = bedrock_model_arn

    llm = LiteLLMBedrockModel(
        model_id=os.environ.get("LLM_MODEL_ID", DEFAULT_LLM_MODEL),
        # Limit the number of requests to avoid being kicked by AWS Bedrock
        requests_per_minute=5.0,
        client_kwargs=bedrock_client_kwargs,
    )

    prompt_templates = yaml.safe_load(
        importlib.resources.files("smolagents.prompts").joinpath("code_agent.yaml").read_text()
    )
    prompt_templates["system_prompt"] = SYSTEM_PROMPT

    # Configure MCP server connection to Rossum
    server_params = StdioServerParameters(
        command="rossum-mcp",
        args=[],
        env={
            "ROSSUM_API_BASE_URL": rossum_api_base_url,
            "ROSSUM_API_TOKEN": rossum_api_token,
            "ROSSUM_MCP_MODE": mcp_mode,
            **os.environ,
        },
    )

    # Connect to MCP server and get tools
    mcp_client = MCPClient(server_params, structured_output=True)
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
        get_splitting_and_sorting_hook_code,
        # Hook analysis tools
        analyze_hook_dependencies,
        visualize_hook_tree,
        explain_hook_execution_order,
    ]

    # Add NEIGHBORS API tools only if the API is available
    if is_neighbors_api_available():
        all_tools.extend([copy_queue_knowledge, retrieve_queue_status])

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
