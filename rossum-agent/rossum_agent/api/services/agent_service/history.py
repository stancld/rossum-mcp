from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rossum_agent.agent.memory import AgentMemory
from rossum_agent.api.services.agent_service.file_intake import build_user_content

if TYPE_CHECKING:
    from anthropic.types import ImageBlockParam, TextBlockParam

    from rossum_agent.agent.core import RossumAgent
    from rossum_agent.agent.types import UserContent
    from rossum_agent.api.models.schemas import DocumentContent, ImageContent


def parse_stored_content(content: str | list[dict[str, Any]]) -> UserContent:
    if isinstance(content, str):
        return content

    result: list[ImageBlockParam | TextBlockParam] = []
    for block in content:
        block_type = block.get("type")
        if block_type == "image":
            source = block.get("source", {})
            result.append(
                {
                    "type": "image",
                    "source": {
                        "type": source.get("type", "base64"),
                        "media_type": source.get("media_type", "image/png"),
                        "data": source.get("data", ""),
                    },
                }
            )
        elif block_type == "text":
            result.append({"type": "text", "text": block.get("text", "")})

    return result or ""


def restore_conversation_history(agent: RossumAgent, history: list[dict[str, Any]]) -> None:
    if not history:
        return

    first_item = history[0]
    if "type" in first_item and first_item["type"] in ("task_step", "memory_step"):
        agent.memory = AgentMemory.from_dict(history)
    else:
        for msg in history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                user_content = parse_stored_content(content)
                agent.add_user_message(user_content)
            elif role == "assistant":
                agent.add_assistant_message(content)


def build_updated_history(
    existing_history: list[dict[str, Any]],
    user_prompt: str,
    final_response: str | None,
    images: list[ImageContent] | None = None,
    documents: list[DocumentContent] | None = None,
    memory: AgentMemory | None = None,
) -> list[dict[str, Any]]:
    if memory is not None:
        lean_history: list[dict[str, Any]] = []
        for step_dict in memory.to_dict():
            if step_dict.get("type") == "task_step":
                lean_history.append(step_dict)
            elif step_dict.get("type") == "memory_step":
                text = step_dict.get("text")
                thinking_blocks = step_dict.get("thinking_blocks", [])
                tool_calls = step_dict.get("tool_calls", [])
                tool_results = step_dict.get("tool_results", [])
                if text or thinking_blocks or tool_calls or tool_results:
                    lean_history.append(
                        {
                            "type": "memory_step",
                            "step_number": step_dict.get("step_number", 0),
                            "text": text,
                            "tool_calls": tool_calls,
                            "tool_results": tool_results,
                            "thinking_blocks": thinking_blocks,
                        }
                    )
        return lean_history

    updated = list(existing_history)
    user_content = build_user_content(user_prompt, images)
    if documents:
        doc_names = ", ".join(doc.filename for doc in documents)
        if isinstance(user_content, str):
            user_content = f"[Uploaded documents: {doc_names}]\n\n{user_content}"
        else:
            user_content.insert(0, {"type": "text", "text": f"[Uploaded documents: {doc_names}]"})
    updated.append({"role": "user", "content": user_content})
    if final_response:
        updated.append({"role": "assistant", "content": final_response})
    return updated
