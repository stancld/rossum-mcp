import { useState, useCallback, useRef, useEffect } from "react";
import { createChat, submitFeedback as apiFeedback } from "../api/client.js";
import { streamMessage } from "rossum-agent-client";
import type {
  ClientConfig,
  ImageContent,
  DocumentContent,
} from "rossum-agent-client";
import {
  loadPersistedState,
  savePersistedState,
} from "../utils/persistence.js";
import type {
  AgentQuestionEvent,
  AttachmentInfo,
  ChatState,
  CompletedStep,
  Config,
  ConfigCommitInfo,
  FileCreatedEvent,
  SSEEvent,
  StepEvent,
  SubAgentProgressEvent,
  SubAgentTextEvent,
  TaskItem,
  TokenUsageBreakdown,
  StreamDoneEvent,
} from "../types.js";
import type {
  ImageAttachment,
  DocumentAttachment,
} from "../utils/fileAttachments.js";

const INITIAL_STATE: ChatState = {
  chatId: null,
  connectionStatus: "disconnected",
  completedSteps: [],
  currentStreaming: null,
  tasks: [],
  subAgentProgress: null,
  subAgentText: null,
  finalAnswer: null,
  tokenUsage: null,
  contextUsageFraction: null,
  configCommit: null,
  files: [],
  error: null,
  userMessages: [],
  feedback: {},
  pendingQuestion: null,
};

function stepToCompleted(step: StepEvent): CompletedStep {
  return {
    stepNumber: step.step_number,
    type: step.type,
    content: step.content,
    toolName: step.tool_name,
    toolArguments: step.tool_arguments,
    toolProgress: step.tool_progress,
    result: step.result,
    isError: step.is_error,
    toolCallId: step.tool_call_id,
    isHookOutput: step.is_hook_output,
  };
}

function isDifferentStep(a: StepEvent, b: StepEvent): boolean {
  return a.step_number !== b.step_number || a.type !== b.type;
}

function shouldCommitPrevious(
  prev: StepEvent | null,
  current: StepEvent,
): prev is StepEvent {
  return prev !== null && isDifferentStep(prev, current);
}

function resolveFinalAnswer(
  step: StepEvent,
  prev: string | null,
): string | null {
  return step.type === "final_answer" ? step.content || prev : prev;
}

function handleStepEvent(prev: ChatState, step: StepEvent): ChatState {
  if (step.type === "error") {
    return {
      ...prev,
      error: step.content || "Unknown error",
      connectionStatus: "error",
    };
  }

  if (step.is_streaming) {
    const finalAnswer = resolveFinalAnswer(step, prev.finalAnswer);

    // If we're switching to a different step while the previous one was still
    // streaming, commit the previous streaming step to completedSteps so it
    // doesn't get lost (e.g. thinking block replaced by tool_start).
    const prevStream = prev.currentStreaming;
    if (shouldCommitPrevious(prevStream, step)) {
      return {
        ...prev,
        completedSteps: [...prev.completedSteps, stepToCompleted(prevStream)],
        currentStreaming: step,
        finalAnswer,
      };
    }
    return { ...prev, currentStreaming: step, finalAnswer };
  }

  const prevStream = prev.currentStreaming;
  // Same step_number = finalization/correction of the streaming step (e.g. text
  // streamed as final_answer corrected to intermediate once tool_use arrived).
  // Don't commit the stale streaming version — only commit the authoritative finalized event.
  const extraSteps: CompletedStep[] =
    prevStream && prevStream.step_number !== step.step_number
      ? [stepToCompleted(prevStream)]
      : [];

  return {
    ...prev,
    completedSteps: [
      ...prev.completedSteps,
      ...extraSteps,
      stepToCompleted(step),
    ],
    currentStreaming: null,
    finalAnswer: step.is_final
      ? resolveFinalAnswer(step, prev.finalAnswer)
      : prev.finalAnswer,
    contextUsageFraction:
      step.context_usage_fraction ?? prev.contextUsageFraction,
  };
}

function handleSubAgentTextEvent(
  prev: ChatState,
  textEvent: SubAgentTextEvent,
): ChatState {
  const prevText =
    prev.subAgentText?.tool_name === textEvent.tool_name
      ? prev.subAgentText!.text
      : "";
  const nextText = textEvent.text.startsWith(prevText)
    ? textEvent.text
    : prevText + textEvent.text;
  return {
    ...prev,
    subAgentText: {
      tool_name: textEvent.tool_name,
      text: nextText,
      is_final: textEvent.is_final,
    },
  };
}

function handleDoneEvent(
  prev: ChatState,
  eventData: StreamDoneEvent,
): ChatState {
  const lastStream = prev.currentStreaming;
  const extra: CompletedStep[] = lastStream
    ? [stepToCompleted(lastStream)]
    : [];
  const commitInfo: ConfigCommitInfo | null = eventData.config_commit_hash
    ? {
        hash: eventData.config_commit_hash,
        message: eventData.config_commit_message ?? "",
        changesCount: eventData.config_changes_count ?? 0,
      }
    : null;

  return {
    ...prev,
    connectionStatus: "idle",
    completedSteps: [...prev.completedSteps, ...extra],
    currentStreaming: null,
    subAgentProgress: null,
    subAgentText: null,
    tokenUsage: eventData.token_usage_breakdown as TokenUsageBreakdown | null,
    contextUsageFraction: eventData.context_usage_fraction ?? null,
    configCommit: commitInfo,
  };
}

function reduceEvent(prev: ChatState, event: SSEEvent): ChatState {
  switch (event.event) {
    case "step":
      return handleStepEvent(prev, event.data);

    case "task_snapshot":
      return { ...prev, tasks: event.data.tasks as TaskItem[] };

    case "sub_agent_progress":
      return { ...prev, subAgentProgress: event.data as SubAgentProgressEvent };

    case "sub_agent_text":
      return handleSubAgentTextEvent(prev, event.data as SubAgentTextEvent);

    case "agent_question":
      return {
        ...prev,
        pendingQuestion: event.data as AgentQuestionEvent,
        connectionStatus: "idle",
      };

    case "done":
      return handleDoneEvent(prev, event.data);

    case "file_created":
      return {
        ...prev,
        files: [...prev.files, event.data as FileCreatedEvent],
      };

    default:
      return prev;
  }
}

export function useChat(config: Config) {
  const [state, setState] = useState<ChatState>(
    () => loadPersistedState() ?? INITIAL_STATE,
  );
  const abortRef = useRef<AbortController | null>(null);
  const chatIdRef = useRef<string | null>(state.chatId);

  useEffect(() => {
    if (state.connectionStatus !== "streaming") {
      savePersistedState(state);
    }
  }, [state]);

  const dispatch = useCallback((event: SSEEvent) => {
    setState((prev) => reduceEvent(prev, event));
  }, []);

  const sendMessage = useCallback(
    async (
      message: string,
      options?: {
        images?: ImageAttachment[];
        documents?: DocumentAttachment[];
        attachmentInfos?: AttachmentInfo[];
        displayMessage?: string;
      },
    ) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState((prev) => ({
        ...prev,
        connectionStatus: "connecting",
        completedSteps: prev.chatId ? prev.completedSteps : [],
        currentStreaming: null,
        subAgentProgress: null,
        subAgentText: null,
        pendingQuestion: null,
        finalAnswer: null,
        tokenUsage: null,
        configCommit: null,
        tasks: [],
        error: null,
        userMessages: [
          ...prev.userMessages,
          {
            text: options?.displayMessage ?? message,
            stepIndexBefore: prev.completedSteps.length,
            attachments: options?.attachmentInfos,
          },
        ],
      }));

      try {
        let chatId = chatIdRef.current;
        if (!chatId) {
          const chat = await createChat(config);
          chatId = chat.chat_id;
          chatIdRef.current = chatId;
          setState((prev) => ({ ...prev, chatId }));
        }

        if (controller.signal.aborted) {
          return;
        }

        setState((prev) => ({ ...prev, connectionStatus: "streaming" }));

        const clientConfig: ClientConfig = {
          apiUrl: config.apiUrl,
          token: config.token,
          rossumUrl: config.rossumUrl,
        };

        await streamMessage({
          config: clientConfig,
          chatId,
          message,
          persona: config.persona,
          rossumUrl: config.contextUrl,
          images: options?.images as ImageContent[] | undefined,
          documents: options?.documents as DocumentContent[] | undefined,
          onEvent: (event: Record<string, unknown>) =>
            dispatch(event as SSEEvent),
          onError: (err: Error) => {
            setState((prev) => ({
              ...prev,
              error: err.message,
              connectionStatus: "error",
            }));
          },
          onDone: () => {
            setState((prev) => ({
              ...prev,
              connectionStatus:
                prev.connectionStatus === "error" ? "error" : "idle",
            }));
          },
          signal: controller.signal,
        });
      } catch (err) {
        if (!controller.signal.aborted) {
          setState((prev) => ({
            ...prev,
            error: err instanceof Error ? err.message : String(err),
            connectionStatus: "error",
          }));
        }
      }
    },
    [config, dispatch],
  );

  const resetChat = useCallback(() => {
    abortRef.current?.abort();
    chatIdRef.current = null;
    setState(INITIAL_STATE);
  }, []);

  const abortStreaming = useCallback(() => {
    abortRef.current?.abort();
    setState((prev) => {
      if (
        prev.connectionStatus !== "connecting" &&
        prev.connectionStatus !== "streaming"
      ) {
        return prev;
      }

      const extra = prev.currentStreaming
        ? [stepToCompleted(prev.currentStreaming)]
        : [];

      return {
        ...prev,
        connectionStatus: "idle",
        completedSteps: [...prev.completedSteps, ...extra],
        currentStreaming: null,
        subAgentProgress: null,
        subAgentText: null,
        error: null,
      };
    });
  }, []);

  const submitFeedback = useCallback(
    async (turnIndex: number, isPositive: boolean) => {
      const chatId = chatIdRef.current;
      if (!chatId) return;

      // Optimistic update
      setState((prev) => ({
        ...prev,
        feedback: { ...prev.feedback, [turnIndex]: isPositive },
      }));

      try {
        await apiFeedback(config, chatId, turnIndex, isPositive);
      } catch {
        // Silent revert on failure
        setState((prev) => {
          const next = { ...prev.feedback };
          delete next[turnIndex];
          return { ...prev, feedback: next };
        });
      }
    },
    [config],
  );

  return { state, sendMessage, resetChat, abortStreaming, submitFeedback };
}
