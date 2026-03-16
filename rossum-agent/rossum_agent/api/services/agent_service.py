"""Agent service for running the Rossum Agent."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import contextvars
import dataclasses
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from rossum_agent.agent.core import RossumAgent, create_agent
from rossum_agent.agent.memory import AgentMemory
from rossum_agent.agent.models import (
    AgentConfig,
    AgentStep,
    ErrorStep,
    FinalAnswerStep,
    StepType,
    TextDeltaStep,
    ThinkingStep,
    ToolCall,
    ToolResult,
    ToolResultStep,
    ToolStartStep,
)
from rossum_agent.api.models.schemas import (
    AgentQuestionEvent,
    AgentQuestionItemSchema,
    DocumentContent,
    ImageContent,
    Persona,
    QuestionOptionSchema,
    StepEvent,
    StreamDoneEvent,
    SubAgentProgressEvent,
    SubAgentTextEvent,
    TaskSnapshotEvent,
)
from rossum_agent.bedrock_client import MAX_INPUT_TOKENS
from rossum_agent.change_tracking.commit_service import CommitService
from rossum_agent.change_tracking.store import CommitStore, SnapshotStore
from rossum_agent.prompts import get_system_prompt
from rossum_agent.redis_storage import RedisStorage
from rossum_agent.rossum_mcp_integration import MCPConnection, connect_mcp_server
from rossum_agent.tools.core import (
    CAUTIOUS_APPROVAL_LABEL,
    AgentContext,
    AgentQuestion,
    SubAgentProgress,
    SubAgentText,
    reset_context,
    set_context,
)
from rossum_agent.tools.dynamic_tools import get_write_tools_async
from rossum_agent.tools.task_tracker import TaskTracker
from rossum_agent.url_context import extract_url_context, format_context_for_prompt
from rossum_agent.utils import create_session_output_dir

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from anthropic.types import ImageBlockParam, TextBlockParam

    from rossum_agent.agent.types import UserContent
    from rossum_agent.change_tracking.models import ConfigCommit

logger = logging.getLogger(__name__)


async def _log_commit_hook(commit: ConfigCommit) -> str | None:
    """Built-in hook: show a commit summary after the agent turn."""
    _op_icon = {"create": "+", "update": "~", "delete": "-"}
    lines = [f"✓ {commit.hash[:8]} — {commit.message}"]
    for change in commit.changes:
        icon = _op_icon.get(change.operation, "?")
        lines.append(f'  [{icon}] {change.entity_type} "{change.entity_name}"')
    return "\n".join(lines)


@dataclass
class _RequestContext:
    """Per-request context for agent execution."""

    event_queue: asyncio.Queue[QueuedAgentEvent] | None = None
    event_loop: asyncio.AbstractEventLoop | None = None


@dataclass
class _ChatRunState:
    """Per-chat run tracking for cancellation support."""

    lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)
    active_task: asyncio.Task | None = None
    run_id: int = 0
    output_dir: Path | None = None
    last_memory: AgentMemory | None = None
    last_main_input_tokens: int = 0
    # Cautious persona: write tools blocked last turn, pre-approved next turn
    cautious_blocked_last_turn: set[str] = dataclasses.field(default_factory=set)


_request_context: contextvars.ContextVar[_RequestContext] = contextvars.ContextVar("request_context")

type QueuedAgentEvent = SubAgentProgressEvent | SubAgentTextEvent | TaskSnapshotEvent | AgentQuestionEvent
type StreamEvent = StepEvent | StreamDoneEvent | QueuedAgentEvent


def convert_sub_agent_progress_to_event(progress: SubAgentProgress) -> SubAgentProgressEvent:
    return SubAgentProgressEvent(
        tool_name=progress.tool_name,
        iteration=progress.iteration,
        max_iterations=progress.max_iterations,
        current_tool=progress.current_tool,
        tool_calls=progress.tool_calls,
        status=progress.status,
    )


def _resolve_tool_call(
    step: ToolStartStep,
    tool_call: ToolCall | None = None,
    current_tool: str | None = None,
) -> ToolCall | None:
    if tool_call is not None:
        return tool_call
    if step.current_tool_call_id is not None:
        for candidate in step.tool_calls:
            if candidate.id == step.current_tool_call_id:
                return candidate
    if current_tool is None:
        return None
    for candidate in step.tool_calls:
        if candidate.name == current_tool:
            return candidate
    return None


def _create_tool_start_event(
    step: ToolStartStep, tool_call: ToolCall | None = None, current_tool: str | None = None
) -> StepEvent:
    resolved_tool_call = _resolve_tool_call(step, tool_call, current_tool)
    resolved_tool_name = resolved_tool_call.name if resolved_tool_call is not None else current_tool or ""
    tool_arguments = resolved_tool_call.arguments if resolved_tool_call is not None else None

    return StepEvent(
        type="tool_start",
        step_number=step.step_number,
        tool_name=resolved_tool_name,
        tool_arguments=tool_arguments,
        tool_progress=step.tool_progress,
        tool_call_id=resolved_tool_call.id if resolved_tool_call is not None else None,
    )


def _create_tool_result_event(step_number: int, result: ToolResult) -> StepEvent:
    return StepEvent(
        type="tool_result",
        step_number=step_number,
        tool_name=result.name,
        result=result.content,
        is_error=result.is_error,
        tool_call_id=result.tool_call_id,
    )


def _log_events(events: list[StepEvent]) -> None:
    for e in events:
        logger.info(
            f"StepEvent: type={e.type}, step={e.step_number}, "
            f"tool_call_id={e.tool_call_id}, is_streaming={e.is_streaming}"
        )


def convert_step_to_events(step: AgentStep) -> list[StepEvent]:
    """Convert an agent step to SSE events."""
    match step:
        case ErrorStep():
            events = [StepEvent(type="error", step_number=step.step_number, content=step.error, is_final=True)]

        case FinalAnswerStep():
            events = [
                StepEvent(type="final_answer", step_number=step.step_number, content=step.final_answer, is_final=True)
            ]

        case TextDeltaStep(step_type=StepType.INTERMEDIATE):
            events = [
                StepEvent(
                    type="intermediate",
                    step_number=step.step_number,
                    content=step.accumulated_text,
                    is_streaming=step.is_streaming,
                )
            ]

        case TextDeltaStep(step_type=StepType.FINAL_ANSWER):
            events = [
                StepEvent(
                    type="final_answer",
                    step_number=step.step_number,
                    content=step.accumulated_text,
                    is_streaming=step.is_streaming,
                )
            ]

        case ToolStartStep(current_tool=None):
            # All tools starting — emit one event per tool call
            total = len(step.tool_calls)
            events = []
            for idx, tc in enumerate(step.tool_calls, 1):
                ev = _create_tool_start_event(step, tool_call=tc)
                ev.tool_progress = (idx, total)
                events.append(ev)

        case ToolStartStep():
            # Single tool progress update
            events = [_create_tool_start_event(step, current_tool=step.current_tool)]

        case ToolResultStep():
            events = [_create_tool_result_event(step.step_number, r) for r in step.tool_results]

        case ThinkingStep():
            events = [
                StepEvent(
                    type="thinking",
                    step_number=step.step_number,
                    content=step.thinking,
                    is_streaming=step.is_streaming,
                )
            ]

    _log_events(events)
    return events


class AgentService:
    """Service for running the Rossum Agent.

    Manages MCP connection lifecycle and agent execution for API requests.
    Uses contextvars for per-request state to support concurrent requests.
    """

    def __init__(self) -> None:
        """Initialize agent service."""
        self._chat_runs: dict[str, _ChatRunState] = {}

    def _get_or_create_stores(self) -> tuple[CommitStore | None, SnapshotStore | None]:
        storage = RedisStorage()
        if storage.is_connected():
            return CommitStore(storage.client), SnapshotStore(storage.client)
        logger.warning("Redis unavailable — change tracking disabled for this run")
        return None, None

    async def _setup_change_tracking(
        self, mcp_connection: MCPConnection, chat_id: str, rossum_api_base_url: str
    ) -> tuple[CommitStore | None, SnapshotStore | None, str]:
        """Configure change tracking on the MCP connection. Returns (commit_store, snapshot_store, environment)."""
        commit_store, snapshot_store = self._get_or_create_stores()
        write_tools = await get_write_tools_async(mcp_connection)
        environment = rossum_api_base_url.rstrip("/")
        if commit_store is not None:
            assert snapshot_store is not None  # both created together from the same Redis client
            mcp_connection.setup_change_tracking(write_tools, chat_id, environment, commit_store, snapshot_store)
        else:
            mcp_connection.write_tools = write_tools
            mcp_connection.chat_id = chat_id
        return commit_store, snapshot_store, environment

    def _get_context(self) -> _RequestContext:
        """Get the current request context, creating if needed."""
        try:
            return _request_context.get()
        except LookupError:
            ctx = _RequestContext()
            _request_context.set(ctx)
            return ctx

    def _get_chat_run_state(self, chat_id: str) -> _ChatRunState:
        """Get or create run state for a chat."""
        if chat_id not in self._chat_runs:
            self._chat_runs[chat_id] = _ChatRunState()
        return self._chat_runs[chat_id]

    @staticmethod
    def _resolve_cautious_preapprovals(pending: set[str], prompt: str) -> set[str]:
        """Only pre-approve blocked writes if the user's answer was affirmative.

        The TUI formats question answers as "1. <question>\\n<selected_label>".
        We check for the approval label to avoid pre-approving on "No" or "Chat" answers.
        """
        if not pending:
            return set()
        if CAUTIOUS_APPROVAL_LABEL in prompt:
            return pending.copy()
        return set()

    async def _register_run(self, chat_id: str) -> int:
        """Register a new run for a chat, cancelling any existing run.

        Returns the new run_id for tracking.
        """
        state = self._get_chat_run_state(chat_id)
        async with state.lock:
            state.last_memory = None
            if state.active_task is not None and not state.active_task.done():
                logger.info(f"Cancelling existing run for chat {chat_id} (run_id={state.run_id})")
                state.active_task.cancel()
                with contextlib.suppress(TimeoutError, asyncio.CancelledError, Exception):
                    await asyncio.wait_for(asyncio.shield(state.active_task), timeout=2.0)
            state.run_id += 1
            state.active_task = asyncio.current_task()
            logger.info(f"Registered run_id={state.run_id} for chat {chat_id}")
            return state.run_id

    async def _clear_run(self, chat_id: str, run_id: int) -> None:
        """Clear the active run if it matches the given run_id."""
        state = self._get_chat_run_state(chat_id)
        async with state.lock:
            if state.run_id == run_id:
                state.active_task = None

    def cancel_run(self, chat_id: str) -> bool:
        """Cancel the active run for a chat.

        Returns True if a run was cancelled, False if no active run.
        """
        state = self._chat_runs.get(chat_id)
        if state is None or state.active_task is None or state.active_task.done():
            return False
        logger.info(f"Explicitly cancelling run for chat {chat_id} (run_id={state.run_id})")
        state.active_task.cancel()
        return True

    def get_output_dir(self, chat_id: str) -> Path | None:
        """Get the output directory for a chat's run."""
        state = self._chat_runs.get(chat_id)
        return state.output_dir if state else None

    def pop_last_memory(self, chat_id: str) -> AgentMemory | None:
        """Get and clear the last memory for a chat's run."""
        state = self._chat_runs.get(chat_id)
        if not state:
            return None
        memory = state.last_memory
        state.last_memory = None
        return memory

    def _enqueue_event_threadsafe(self, event: QueuedAgentEvent, event_name: str) -> None:
        """Thread-safe event enqueueing via call_soon_threadsafe.

        Callbacks may be invoked from thread pool executors, so we must marshal
        the queue operation onto the event loop thread.
        """
        ctx = self._get_context()
        if ctx.event_queue is None or ctx.event_loop is None:
            return

        def _put() -> None:
            if ctx.event_queue is None:
                return
            try:
                ctx.event_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"{event_name} queue full, dropping event")

        ctx.event_loop.call_soon_threadsafe(_put)

    def _on_sub_agent_progress(self, progress: SubAgentProgress) -> None:
        event = convert_sub_agent_progress_to_event(progress)
        self._enqueue_event_threadsafe(event, "Sub-agent progress")

    def _on_sub_agent_text(self, text: SubAgentText) -> None:
        event = SubAgentTextEvent(tool_name=text.tool_name, text=text.text, is_final=text.is_final)
        self._enqueue_event_threadsafe(event, "Sub-agent text")

    def _on_task_snapshot(self, snapshot: list[dict[str, object]]) -> None:
        event = TaskSnapshotEvent(tasks=snapshot)
        self._enqueue_event_threadsafe(event, "Task snapshot")

    def _on_agent_question(self, question: AgentQuestion) -> None:
        event = AgentQuestionEvent(
            questions=[
                AgentQuestionItemSchema(
                    question=item.question,
                    options=[
                        QuestionOptionSchema(value=o.value, label=o.label, description=o.description)
                        for o in item.options
                    ],
                    multi_select=item.multi_select,
                )
                for item in question.questions
            ],
        )
        self._enqueue_event_threadsafe(event, "Agent question")

    @staticmethod
    def _drain_queue(queue: asyncio.Queue[QueuedAgentEvent]) -> list[QueuedAgentEvent]:
        """Drain all pending events from the queue."""
        events: list[QueuedAgentEvent] = []
        while not queue.empty():
            try:
                events.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return events

    async def run_agent(
        self,
        chat_id: str,
        prompt: str,
        conversation_history: list[dict[str, Any]],
        rossum_api_token: str,
        rossum_api_base_url: str,
        mcp_mode: Literal["read-only", "read-write"] = "read-only",
        persona: Persona = Persona.DEFAULT,
        rossum_url: str | None = None,
        images: list[ImageContent] | None = None,
        documents: list[DocumentContent] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Run the agent with a new prompt.

        Creates a fresh MCP connection, initializes the agent with conversation
        history, and streams step events.

        Yields:
            StepEvent objects during execution, SubAgentProgressEvent for sub-agent progress,
            SubAgentTextEvent for sub-agent text streaming, StreamDoneEvent at the end.
        """
        logger.info(
            f"Starting agent run with {len(conversation_history)} history messages, "
            f"{len(images or [])} images, {len(documents or [])} documents"
        )

        run_id = await self._register_run(chat_id)

        req_ctx = _RequestContext()
        _request_context.set(req_ctx)

        output_dir = create_session_output_dir()
        chat_run_state = self._get_chat_run_state(chat_id)
        chat_run_state.output_dir = output_dir
        logger.info(f"Created session output directory: {output_dir}")

        if documents:
            self._save_documents_to_output_dir(documents, output_dir)

        req_ctx.event_queue = asyncio.Queue(maxsize=100)
        req_ctx.event_loop = asyncio.get_running_loop()

        agent_ctx = AgentContext(
            output_dir=output_dir,
            rossum_credentials=(rossum_api_base_url, rossum_api_token),
            persona=persona,
            cautious_preapproved_writes=self._resolve_cautious_preapprovals(
                chat_run_state.cautious_blocked_last_turn, prompt
            ),
            progress_callback=self._on_sub_agent_progress,
            text_callback=self._on_sub_agent_text,
            task_tracker=TaskTracker(),
            task_snapshot_callback=self._on_task_snapshot,
            question_callback=self._on_agent_question,
        )
        chat_run_state.cautious_blocked_last_turn.clear()
        ctx_token = set_context(agent_ctx)

        system_prompt = self._build_system_prompt(rossum_url, persona)

        try:
            try:
                async with connect_mcp_server(
                    rossum_api_token=rossum_api_token,
                    rossum_api_base_url=rossum_api_base_url,
                    mcp_mode=mcp_mode,
                ) as mcp_connection:
                    commit_store, snapshot_store, environment = await self._setup_change_tracking(
                        mcp_connection, chat_id, rossum_api_base_url
                    )

                    agent = await create_agent(
                        mcp_connection=mcp_connection, system_prompt=system_prompt, config=AgentConfig()
                    )

                    agent_ctx.mcp_connection = mcp_connection
                    agent_ctx.mcp_event_loop = asyncio.get_running_loop()
                    agent_ctx.mcp_mode = mcp_mode
                    agent_ctx.commit_store = commit_store
                    agent_ctx.snapshot_store = snapshot_store
                    agent_ctx.rossum_environment = environment

                    self._restore_conversation_history(agent, conversation_history)
                    if chat_run_state.last_main_input_tokens:
                        agent.tokens.last_main_input = chat_run_state.last_main_input_tokens

                    total_steps = 0
                    total_input_tokens = 0
                    total_output_tokens = 0

                    user_content = self._build_user_content(prompt, images, documents, output_dir)

                    try:
                        async for step in agent.run(user_content):
                            for sub_event in self._drain_queue(req_ctx.event_queue):
                                yield sub_event

                            for event in convert_step_to_events(step):
                                if not event.is_streaming and MAX_INPUT_TOKENS:
                                    event.context_usage_fraction = min(
                                        agent.tokens.last_main_input / MAX_INPUT_TOKENS, 1.0
                                    )
                                yield event

                            if isinstance(step, (ToolResultStep, FinalAnswerStep, ErrorStep)):
                                total_steps = step.step_number
                                total_input_tokens = agent.tokens.total_input
                                total_output_tokens = agent.tokens.total_output

                        for sub_event in self._drain_queue(req_ctx.event_queue):
                            yield sub_event

                        chat_run_state.last_memory = agent.memory
                        chat_run_state.last_main_input_tokens = agent.tokens.last_main_input
                        chat_run_state.cautious_blocked_last_turn = agent_ctx.cautious_blocked_writes.copy()

                        async for event in self._stream_finalization(
                            commit_store,
                            snapshot_store,
                            mcp_connection,
                            chat_id,
                            prompt,
                            rossum_api_base_url,
                            total_steps,
                            total_input_tokens,
                            total_output_tokens,
                            agent,
                        ):
                            yield event

                    except Exception as e:
                        logger.error(f"Agent execution failed: {e}", exc_info=True)
                        yield StepEvent(
                            type="error",
                            step_number=total_steps + 1,
                            content=f"Agent execution failed: {e}",
                            is_final=True,
                        )
            finally:
                reset_context(ctx_token)
        except asyncio.CancelledError:
            logger.info(f"Run cancelled for chat {chat_id} (run_id={run_id})")
            raise
        finally:
            await self._clear_run(chat_id, run_id)

    @staticmethod
    def _build_system_prompt(rossum_url: str | None, persona: Persona = Persona.DEFAULT) -> str:
        system_prompt = get_system_prompt(persona)
        url_context = extract_url_context(rossum_url)
        if not url_context.is_empty():
            context_section = format_context_for_prompt(url_context)
            system_prompt = system_prompt + "\n\n---\n" + context_section
        return system_prompt

    async def _stream_finalization(
        self,
        commit_store: CommitStore | None,
        snapshot_store: SnapshotStore | None,
        mcp_connection: MCPConnection,
        chat_id: str,
        prompt: str,
        rossum_api_base_url: str,
        total_steps: int,
        total_input_tokens: int,
        total_output_tokens: int,
        agent: RossumAgent,
    ) -> AsyncIterator[StepEvent | StreamDoneEvent]:
        commit = (
            self._try_create_config_commit(
                commit_store, snapshot_store, mcp_connection, chat_id, prompt, rossum_api_base_url
            )
            if commit_store and snapshot_store
            else None
        )
        if commit is not None:
            hook_output = await _log_commit_hook(commit)
            if hook_output:
                yield StepEvent(
                    type="final_answer",
                    step_number=total_steps + 1,
                    content=hook_output,
                    is_final=True,
                    is_hook_output=True,
                )
        yield StreamDoneEvent(
            total_steps=total_steps,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cache_creation_input_tokens=agent.tokens.total_cache_creation,
            cache_read_input_tokens=agent.tokens.total_cache_read,
            token_usage_breakdown=agent.get_token_usage_breakdown(),
            max_input_tokens=MAX_INPUT_TOKENS,
            context_usage_fraction=min(agent.tokens.last_main_input / MAX_INPUT_TOKENS, 1.0)
            if MAX_INPUT_TOKENS
            else 0.0,
            config_commit_hash=commit.hash if commit else None,
            config_commit_message=commit.message if commit else None,
            config_changes_count=len(commit.changes) if commit else 0,
        )
        agent.log_token_usage_summary()

    @staticmethod
    def _try_create_config_commit(
        commit_store: CommitStore,
        snapshot_store: SnapshotStore,
        mcp_connection: MCPConnection,
        chat_id: str,
        prompt: str,
        rossum_api_base_url: str,
    ) -> ConfigCommit | None:
        """Create a config commit if there are tracked changes."""
        if not mcp_connection.has_changes():
            return None
        commit_service = CommitService(commit_store, snapshot_store)
        return commit_service.create_commit(mcp_connection, chat_id, prompt, rossum_api_base_url.rstrip("/"))

    def _save_documents_to_output_dir(self, documents: list[DocumentContent], output_dir: Path) -> None:
        for doc in documents:
            file_path = output_dir / Path(doc.filename).name
            try:
                file_data = base64.b64decode(doc.data)
                file_path.write_bytes(file_data)
                logger.info(f"Saved document to {file_path}")
            except Exception as e:
                logger.error(f"Failed to save document {doc.filename}: {e}")

    def _build_user_content(
        self,
        prompt: str,
        images: list[ImageContent] | None,
        documents: list[DocumentContent] | None = None,
        output_dir: Path | None = None,
    ) -> UserContent:
        if not images and not documents:
            return prompt

        content: list[ImageBlockParam | TextBlockParam] = []
        if images:
            for img in images:
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": img.media_type,
                            "data": img.data,
                        },
                    }
                )
        if documents and output_dir:
            doc_paths = [str(output_dir / doc.filename) for doc in documents]
            doc_info = "\n".join(f"- {path}" for path in doc_paths)
            content.append({"type": "text", "text": f"[Uploaded documents available for processing:\n{doc_info}]"})
        content.append({"type": "text", "text": prompt})
        return content

    def _restore_conversation_history(self, agent: RossumAgent, history: list[dict[str, Any]]) -> None:
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
                    user_content = self._parse_stored_content(content)
                    agent.add_user_message(user_content)
                elif role == "assistant":
                    agent.add_assistant_message(content)

    def _parse_stored_content(self, content: str | list[dict[str, Any]]) -> UserContent:
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

    def build_updated_history(
        self,
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
        user_content = self._build_user_content(user_prompt, images)
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
