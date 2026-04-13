"""Tests for queue template name listing."""

from __future__ import annotations

import pytest
from rossum_mcp.models.queue import QUEUE_TEMPLATE_NAMES
from rossum_mcp.tools.search.queue_templates import _list_queue_template_names


@pytest.mark.unit
class TestListQueueTemplateNames:
    @pytest.mark.asyncio
    async def test_returns_all_names(self) -> None:
        result = await _list_queue_template_names()

        assert result == list(QUEUE_TEMPLATE_NAMES)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_max_items_limits_output(self) -> None:
        result = await _list_queue_template_names(max_items=3)

        assert len(result) == 3
        assert result == list(QUEUE_TEMPLATE_NAMES)[:3]

    @pytest.mark.asyncio
    async def test_max_items_none_returns_all(self) -> None:
        result = await _list_queue_template_names(max_items=None)

        assert len(result) == len(QUEUE_TEMPLATE_NAMES)
