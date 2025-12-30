"""Tests for rossum_agent.agent.core module."""

from __future__ import annotations

import asyncio
import json
from contextvars import copy_context
from functools import partial
from typing import TYPE_CHECKING

import pytest
from rossum_agent.tools import INTERNAL_TOOLS, execute_tool, get_output_dir, set_output_dir

if TYPE_CHECKING:
    from pathlib import Path


class TestContextPropagation:
    """Test that context variables propagate correctly to executor threads.

    The agent uses run_in_executor to run tools in thread pools. Context variables
    must be explicitly propagated using copy_context() to be visible in those threads.
    """

    @pytest.mark.asyncio
    async def test_output_dir_propagates_to_executor(self, tmp_path: Path) -> None:
        """Test that output_dir context var is visible in run_in_executor."""
        set_output_dir(tmp_path)
        try:
            loop = asyncio.get_event_loop()
            ctx = copy_context()
            future = loop.run_in_executor(None, partial(ctx.run, get_output_dir))
            result = await future
            assert result == tmp_path
        finally:
            set_output_dir(None)

    @pytest.mark.asyncio
    async def test_output_dir_not_propagated_without_context(self, tmp_path: Path) -> None:
        """Test that without copy_context, executor doesn't see the context var."""
        set_output_dir(tmp_path)
        try:
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(None, get_output_dir)
            result = await future
            assert result != tmp_path
            assert str(result).endswith("outputs")
        finally:
            set_output_dir(None)

    @pytest.mark.asyncio
    async def test_write_file_uses_propagated_output_dir(self, tmp_path: Path) -> None:
        """Test that write_file tool uses the propagated output_dir in executor."""
        set_output_dir(tmp_path)
        try:
            loop = asyncio.get_event_loop()
            ctx = copy_context()
            future = loop.run_in_executor(
                None,
                partial(
                    ctx.run,
                    execute_tool,
                    "write_file",
                    {"filename": "test.txt", "content": "Hello from executor"},
                    INTERNAL_TOOLS,
                ),
            )
            result_json = await future
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert str(tmp_path) in result["path"]
            assert (tmp_path / "test.txt").read_text() == "Hello from executor"
        finally:
            set_output_dir(None)
