"""Agent service for running the Rossum Agent.

Manages MCP connection lifecycle, per-chat run state, and event streaming for
API requests. Helpers for file intake, conversation history, and cautious-
persona pre-approval gating live in sibling modules.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from rossum_agent.agent.core import RossumAgent, create_agent
from rossum_agent.agent.models import (
    AgentQuestionPart,
    AgentStep,
    ErrorStep,
    FinalAnswerStep,
    QueuedAgentEvent,
    ReasoningStep,
    TaskSnapshotPart,
    TaskSnapshotTask,
    TaskStatus,
    TextDeltaStep,
    ToolResultStep,
    ToolStartStep,
)
from rossum_agent.agent.system_prompt import get_system_prompt
from rossum_agent.api.models.schemas import (
    AgentQuestionItemSchema,
    DocumentContent,
    ImageContent,
    MCPMode,
    Persona,
    QuestionOptionSchema,
    StreamDoneEvent,
)
from rossum_agent.api.services.agent_service import (
    cautious,
    file_intake,
    history,
)
from rossum_agent.bedrock_client import MAX_INPUT_TOKENS
from rossum_agent.change_tracking.commit_service import CommitService
from rossum_agent.change_tracking.store import CommitStore, SnapshotStore
from rossum_agent.rossum_mcp_integration.connection import MCPConnection, connect_mcp_server
from rossum_agent.tools.core import (
    AgentContext,
    AgentQuestion,
    reset_context,
    set_context,
)
from rossum_agent.tools.dynamic_tools import get_write_tools_async
from rossum_agent.tools.task_tracker import TaskTracker
from rossum_agent.url_context import extract_url_context, format_context_for_prompt
from rossum_agent.utils import create_session_output_dir
from rossum_agent.valkey_client import ValkeyConnection

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from rossum_agent.agent.memory import AgentMemory
    from rossum_agent.change_tracking.models import ConfigCommit

logger = structlog.get_logger(__name__)


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
    # Unconsumed pre-approvals that carry over when the agent asked questions instead of writing
    cautious_unconsumed_preapprovals: set[str] = dataclasses.field(default_factory=set)
    # Tools approved by the user (persists for the conversation lifetime)
    cautious_approved_tools: set[str] = dataclasses.field(default_factory=set)


_request_context: contextvars.ContextVar[_RequestContext] = contextvars.ContextVar("request_context")

type StreamEvent = AgentStep | StreamDoneEvent | QueuedAgentEvent


def _log_step(step: AgentStep) -> None:
    """Log each agent step using the wire event type names.

    Only logs finalized events to avoid flooding logs with per-token streaming chunks.
    """
    match step:
        case ReasoningStep() if not step.is_streaming:
            logger.info(f"StepEvent: type=reasoning, step={step.step_number}")
        case TextDeltaStep() if not step.is_streaming:
            logger.info(f"StepEvent: type=text-delta, step={step.step_number}, stepType={step.step_type.value}")
        case ToolStartStep():
            for tc in step.tool_calls:
                logger.info(
                    f"StepEvent: type=tool-input-start, step={step.step_number}, "
                    f"tool_call_id={tc.id}, tool_name={tc.name}"
                )
        case ToolResultStep():
            for r in step.tool_results:
                logger.info(
                    f"StepEvent: type=tool-output-available, step={step.step_number}, "
                    f"tool_call_id={r.tool_call_id}, tool_name={r.name}"
                )
        case FinalAnswerStep():
            logger.info(f"StepEvent: type=data-final-answer, step={step.step_number}")
        case ErrorStep():
            logger.info(f"StepEvent: type=error, step={step.step_number}")


class AgentService:
    """Service for running the Rossum Agent.

    Manages MCP connection lifecycle and agent execution for API requests.
    Uses contextvars for per-request state to support concurrent requests.
    """

    def __init__(self) -> None:
        self._chat_runs: dict[str, _ChatRunState] = {}

    def _get_or_create_stores(self) -> tuple[CommitStore | None, SnapshotStore | None]:
        conn = ValkeyConnection()
        if conn.is_connected():
            return CommitStore(conn.client), SnapshotStore(conn.client)
        logger.warning("Valkey unavailable — change tracking disabled for this run")
        return None, None

    async def _setup_change_tracking(
        self, mcp_connection: MCPConnection, chat_id: str, rossum_api_base_url: str
    ) -> tuple[CommitStore | None, SnapshotStore | None, str]:
        """Configure change tracking on the MCP connection. Returns (commit_store, snapshot_store, environment)."""
        commit_store, snapshot_store = self._get_or_create_stores()
        write_tools = await get_write_tools_async(mcp_connection)
        environment = rossum_api_base_url.rstrip("/")
        if commit_store is not None:
            assert snapshot_store is not None  # both created together from the same Valkey client
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
        if chat_id not in self._chat_runs:
            self._chat_runs[chat_id] = _ChatRunState()
        return self._chat_runs[chat_id]

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
        state = self._chat_runs.get(chat_id)
        return state.output_dir if state else None

    def get_last_memory(self, chat_id: str) -> AgentMemory | None:
        """Get the last memory for a chat's run without clearing it."""
        state = self._chat_runs.get(chat_id)
        return state.last_memory if state else None

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

    def _on_task_snapshot(self, snapshot: list[dict[str, object]]) -> None:
        try:
            tasks = [
                TaskSnapshotTask(
                    id=str(task.get("id", "")),
                    subject=str(task.get("subject", "")),
                    status=TaskStatus(str(task.get("status", "pending"))),
                    description=str(task.get("description", "")),
                )
                for task in snapshot
            ]
            part = TaskSnapshotPart(tasks=tasks)
        except (ValueError, KeyError) as e:
            logger.warning(f"Invalid task snapshot data: {e}")
            return
        self._enqueue_event_threadsafe(part, "Task snapshot")

    def _on_agent_question(self, question: AgentQuestion) -> None:
        part = AgentQuestionPart(
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
        self._enqueue_event_threadsafe(part, "Agent question")

    @staticmethod
    def _drain_queue(queue: asyncio.Queue[QueuedAgentEvent]) -> list[QueuedAgentEvent]:
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
        mcp_mode: MCPMode = "read-only",
        persona: Persona = Persona.DEFAULT,
        rossum_url: str | None = None,
        images: list[ImageContent] | None = None,
        documents: list[DocumentContent] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Run the agent with a new prompt.

        Creates a fresh MCP connection, initializes the agent with conversation
        history, and streams AgentStep objects, queued events, and a final StreamDoneEvent.
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
            file_intake.save_documents_to_output_dir(documents, output_dir)
        text_file_paths = file_intake.extract_and_save_text_files(prompt, output_dir)

        req_ctx.event_queue = asyncio.Queue(maxsize=100)
        req_ctx.event_loop = asyncio.get_running_loop()

        agent_ctx = AgentContext(
            output_dir=output_dir,
            rossum_credentials=(rossum_api_base_url, rossum_api_token),
            persona=persona,
            cautious_preapproved_writes=cautious.resolve_cautious_preapprovals(
                chat_run_state.cautious_blocked_last_turn,
                prompt,
                chat_run_state.cautious_unconsumed_preapprovals,
                chat_run_state.cautious_approved_tools,
            ),
            task_tracker=TaskTracker(),
            task_snapshot_callback=self._on_task_snapshot,
            question_callback=self._on_agent_question,
        )
        chat_run_state.cautious_blocked_last_turn.clear()
        chat_run_state.cautious_unconsumed_preapprovals.clear()
        ctx_token = set_context(agent_ctx)

        system_prompt = self._build_system_prompt(rossum_url, persona, mcp_mode)
        system_prompt = cautious.inject_preapproval_into_system_prompt(
            system_prompt, agent_ctx.cautious_preapproved_writes
        )

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

                    agent = await create_agent(mcp_connection=mcp_connection, system_prompt=system_prompt)

                    agent_ctx.mcp_connection = mcp_connection
                    agent_ctx.mcp_event_loop = asyncio.get_running_loop()
                    agent_ctx.mcp_mode = mcp_mode
                    agent_ctx.commit_store = commit_store
                    agent_ctx.snapshot_store = snapshot_store
                    agent_ctx.rossum_environment = environment

                    history.restore_conversation_history(agent, conversation_history)
                    if chat_run_state.last_main_input_tokens:
                        agent.tokens.last_main_input = chat_run_state.last_main_input_tokens

                    total_steps = 0
                    total_input_tokens = 0
                    total_output_tokens = 0

                    user_content = file_intake.build_user_content(
                        prompt, images, documents, output_dir, text_file_paths
                    )

                    try:
                        async for step in agent.run(user_content):
                            for sub_event in self._drain_queue(req_ctx.event_queue):
                                yield sub_event

                            _log_step(step)
                            yield step

                            if isinstance(step, (ToolResultStep, FinalAnswerStep, ErrorStep)):
                                total_steps = step.step_number
                                total_input_tokens = agent.tokens.total_input
                                total_output_tokens = agent.tokens.total_output
                                # Update memory after each completed step so intermediate
                                # saves in the route layer can persist progress.
                                chat_run_state.last_memory = agent.memory

                        for sub_event in self._drain_queue(req_ctx.event_queue):
                            yield sub_event

                        chat_run_state.last_memory = agent.memory
                        chat_run_state.last_main_input_tokens = agent.tokens.last_main_input

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
                        yield ErrorStep(
                            step_number=total_steps + 1,
                            error=f"Agent execution failed: {e}",
                        )
                    finally:
                        # Persist cautious state in `finally` — the front-end
                        # can cancel the run before the agent finishes (e.g.
                        # when a question is emitted), and without this the
                        # blocked-tool state would be lost.
                        chat_run_state.cautious_blocked_last_turn = agent_ctx.cautious_blocked_writes.copy()
                        chat_run_state.cautious_unconsumed_preapprovals = (
                            agent_ctx.cautious_preapproved_writes - agent_ctx.cautious_executed_preapproved
                        )
                        chat_run_state.cautious_approved_tools.update(agent_ctx.cautious_executed_preapproved)
            finally:
                reset_context(ctx_token)
        except asyncio.CancelledError:
            logger.info(f"Run cancelled for chat {chat_id} (run_id={run_id})")
            raise
        finally:
            await self._clear_run(chat_id, run_id)

    @staticmethod
    def _build_system_prompt(
        rossum_url: str | None,
        persona: Persona = Persona.DEFAULT,
        mcp_mode: MCPMode = "read-only",
    ) -> str:
        system_prompt = get_system_prompt(persona, mcp_mode)
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
    ) -> AsyncIterator[FinalAnswerStep | StreamDoneEvent]:
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
                yield FinalAnswerStep(
                    step_number=total_steps + 1,
                    final_answer=hook_output,
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
