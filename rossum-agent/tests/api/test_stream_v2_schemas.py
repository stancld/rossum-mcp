"""Tests for AI SDK-compatible v2 streaming schemas."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError
from rossum_agent.api.models.schemas import TokenUsageBreakdown
from rossum_agent.api.models.stream_v2 import (
    V2AgentQuestionData,
    V2AgentQuestionPart,
    V2AssistantMessage,
    V2CommitInfoPart,
    V2FileCreatedPart,
    V2MessageMetadata,
    V2MessageMetadataChunk,
    V2MessagePart,
    V2ReasoningPart,
    V2StreamChunk,
    V2SubAgentProgressPart,
    V2TaskSnapshotPart,
    V2TextPart,
    V2ToolCallPart,
    V2ToolResultPart,
)


class TestV2MessageMetadata:
    def test_total_tokens_is_derived_from_input_and_output(self):
        metadata = V2MessageMetadata(input_tokens=120, output_tokens=30)

        assert metadata.total_tokens == 150

    def test_total_tokens_is_preserved_when_explicit(self):
        metadata = V2MessageMetadata(input_tokens=120, output_tokens=30, total_tokens=999)

        assert metadata.total_tokens == 999

    def test_metadata_serializes_all_fields(self):
        breakdown = TokenUsageBreakdown.from_raw_counts(
            total_input=120,
            total_output=30,
            main_input=80,
            main_output=20,
            sub_input=40,
            sub_output=10,
            sub_by_tool={"search_knowledge_base": (40, 10)},
        )
        metadata = V2MessageMetadata(
            model="claude-opus",
            finish_reason="stop",
            started_at=datetime(2026, 3, 18, 10, 0, tzinfo=UTC),
            completed_at=datetime(2026, 3, 18, 10, 1, tzinfo=UTC),
            input_tokens=120,
            output_tokens=30,
            cache_creation_input_tokens=5,
            cache_read_input_tokens=40,
            token_usage_breakdown=breakdown,
            max_input_tokens=200_000,
            context_usage_fraction=0.42,
        )

        dumped = metadata.model_dump()

        assert dumped["model"] == "claude-opus"
        assert dumped["finish_reason"] == "stop"
        assert dumped["total_tokens"] == 150
        assert dumped["cache_creation_input_tokens"] == 5
        assert dumped["cache_read_input_tokens"] == 40
        assert dumped["token_usage_breakdown"]["total"]["total_tokens"] == 150


class TestV2MessageParts:
    def test_message_part_union_parses_tool_call_part(self):
        adapter = TypeAdapter(V2MessagePart)
        part = adapter.validate_python(
            {
                "type": "tool-call",
                "tool_call_id": "toolu_123",
                "tool_name": "list_annotations",
                "input": {"queue": "invoices"},
            }
        )

        assert isinstance(part, V2ToolCallPart)
        assert part.input == {"queue": "invoices"}

    def test_stream_chunk_union_parses_message_part(self):
        adapter = TypeAdapter(V2StreamChunk)
        chunk = adapter.validate_python(
            {
                "type": "text",
                "text": "Queued the deployment.",
            }
        )

        assert isinstance(chunk, V2TextPart)
        assert chunk.text == "Queued the deployment."

    def test_stream_chunk_union_parses_metadata_chunk(self):
        adapter = TypeAdapter(V2StreamChunk)
        chunk = adapter.validate_python(
            {
                "type": "message-metadata",
                "metadata": {
                    "model": "claude-opus",
                    "input_tokens": 10,
                    "output_tokens": 5,
                },
            }
        )

        assert isinstance(chunk, V2MessageMetadataChunk)
        assert chunk.metadata.total_tokens == 15

    def test_custom_data_parts_serialize_with_explicit_type(self):
        progress = V2SubAgentProgressPart(
            data={
                "tool_name": "patch_schema_with_subagent",
                "iteration": 2,
                "max_iterations": 5,
                "current_tool": "search_knowledge_base",
                "tool_calls": ["search_knowledge_base"],
                "status": "searching",
            }
        )
        task_snapshot = V2TaskSnapshotPart(
            data={"tasks": [{"id": "1", "subject": "Inspect queue", "status": "pending", "description": ""}]}
        )
        question = V2AgentQuestionPart(
            data=V2AgentQuestionData(
                questions=[
                    {
                        "question": "Proceed with the deployment?",
                        "options": [{"value": "yes", "label": "Yes", "description": "Continue"}],
                        "multi_select": False,
                    }
                ]
            )
        )
        file_created = V2FileCreatedPart(data={"filename": "report.md", "url": "/api/v1/chats/chat-1/files/report.md"})
        commit_info = V2CommitInfoPart(data={"hash": "abc123", "message": "Update rules", "changes_count": 2})

        assert progress.model_dump()["type"] == "data-sub-agent-progress"
        assert task_snapshot.model_dump()["type"] == "data-task-snapshot"
        assert question.model_dump()["type"] == "data-agent-question"
        assert file_created.model_dump()["type"] == "data-file-created"
        assert commit_info.model_dump()["type"] == "data-commit-info"

    def test_task_snapshot_part_preserves_typed_tasks(self):
        part = V2TaskSnapshotPart(
            data={
                "tasks": [
                    {
                        "id": "1",
                        "subject": "Inspect queue",
                        "status": "in_progress",
                        "description": "Verify settings",
                    }
                ]
            }
        )

        dumped = part.model_dump()

        assert dumped["data"]["tasks"][0] == {
            "id": "1",
            "subject": "Inspect queue",
            "status": "in_progress",
            "description": "Verify settings",
        }

    def test_task_snapshot_part_rejects_unknown_status(self):
        with pytest.raises(ValidationError):
            V2TaskSnapshotPart(
                data={
                    "tasks": [
                        {
                            "id": "1",
                            "subject": "Inspect queue",
                            "status": "blocked",
                            "description": "",
                        }
                    ]
                }
            )

    def test_tool_result_supports_non_string_json_payloads(self):
        part = V2ToolResultPart(
            tool_call_id="toolu_123",
            output={"annotations": [{"id": "ann_1"}]},
        )

        assert part.output == {"annotations": [{"id": "ann_1"}]}

    def test_tool_result_is_keyed_by_tool_call_id_only(self):
        part = V2ToolResultPart(tool_call_id="toolu_123", output={"annotations": []})

        assert "tool_name" not in part.model_dump()
        assert "toolName" not in part.model_dump(by_alias=True)

    def test_wire_serialization_uses_camel_case(self):
        tool_call = V2ToolCallPart(
            tool_call_id="toolu_123",
            tool_name="list_annotations",
            input={"queue": "invoices"},
        )
        tool_result = V2ToolResultPart(
            tool_call_id="toolu_123",
            output={"count": 42},
            is_error=False,
        )
        metadata = V2MessageMetadata(input_tokens=100, output_tokens=20)

        tc_wire = tool_call.model_dump(by_alias=True)
        tr_wire = tool_result.model_dump(by_alias=True)
        md_wire = metadata.model_dump(by_alias=True)

        assert tc_wire["toolCallId"] == "toolu_123"
        assert tc_wire["toolName"] == "list_annotations"
        assert tr_wire["toolCallId"] == "toolu_123"
        assert tr_wire["isError"] is False
        assert md_wire["inputTokens"] == 100
        assert md_wire["outputTokens"] == 20
        assert md_wire["totalTokens"] == 120

    def test_custom_data_part_supports_reconciliation_id(self):
        part = V2TaskSnapshotPart(
            id="tasks-main",
            data={"tasks": [{"id": "1", "subject": "Check queue", "status": "pending"}]},
        )

        assert part.id == "tasks-main"
        assert part.model_dump()["id"] == "tasks-main"

    def test_custom_data_part_id_defaults_to_none(self):
        part = V2FileCreatedPart(data={"filename": "report.md", "url": "/files/report.md"})

        assert part.id is None

    def test_tool_result_is_error_flag(self):
        part = V2ToolResultPart(
            tool_call_id="toolu_err",
            output="Tool execution failed: permission denied",
            is_error=True,
        )

        assert part.is_error is True
        dumped = part.model_dump(by_alias=True)
        assert dumped["isError"] is True

    def test_sub_agent_progress_rejects_unknown_status(self):
        with pytest.raises(ValidationError):
            V2SubAgentProgressPart(
                data={
                    "tool_name": "some_tool",
                    "iteration": 1,
                    "max_iterations": 3,
                    "status": "invalid_status",
                }
            )


class TestV2AssistantMessage:
    def test_assistant_message_groups_parts_and_metadata(self):
        message = V2AssistantMessage(
            parts=[
                V2ReasoningPart(text="Looking up the queue."),
                V2TextPart(text="I found 3 matching annotations."),
                V2FileCreatedPart(data={"filename": "summary.txt", "url": "/api/v1/chats/chat-1/files/summary.txt"}),
            ],
            metadata=V2MessageMetadata(model="claude-opus", input_tokens=100, output_tokens=20),
        )

        dumped = message.model_dump()

        assert dumped["role"] == "assistant"
        assert len(dumped["parts"]) == 3
        assert dumped["metadata"]["total_tokens"] == 120
