"""Create and configure the Rossum agent with custom tools and instructions."""

import importlib.resources
import os

import yaml
from smolagents import CodeAgent, LiteLLMModel

from rossum_agent.file_system_tools import get_file_info, list_files, read_file
from rossum_agent.instructions import SYSTEM_PROMPT
from rossum_agent.internal_tools import copy_queue_knowledge, retrieve_queue_status
from rossum_agent.plot_tools import plot_data
from rossum_mcp.tools import parse_annotation_content, rossum_mcp_tool

DEFAULT_LLM_MODEL = "openai/Qwen/Qwen3-Next-80B-A3B-Instruct-FP8"


def create_agent(
    stream_outputs: bool = False,
) -> CodeAgent:
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
