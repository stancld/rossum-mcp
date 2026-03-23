import { useState, useCallback, useRef, useEffect } from "react";
import { createChat, submitFeedback as apiFeedback } from "../api/client.js";
import {
  loadPersistedState,
  savePersistedState,
} from "../utils/persistence.js";
import type {
  AgentQuestionPart,
  AttachmentInfo,
  ChatState,
  CompletedStep,
  Config,
  PendingToolCall,
} from "../types.js";
import type {
  ImageAttachment,
  DocumentAttachment,
} from "../utils/fileAttachments.js";
import type { ImageContent, DocumentContent } from "rossum-agent-client";
import { buildHeaders } from "../api/client.js";

const INITIAL_STATE: ChatState = {
  chatId: null,
  connectionStatus: "disconnected",
  completedSteps: [],
  currentStreaming: null,
  finalAnswer: null,
  error: null,
  userMessages: [],
  feedback: {},
  pendingQuestion: null,
  pendingToolCalls: {},
};

// --- Wire event types (minimal v1 protocol) ---

interface WireTextStart {
  type: "text-start";
  id: string;
}

interface WireTextDelta {
  type: "text-delta";
  id: string;
  delta: string;
}

interface WireTextEnd {
  type: "text-end";
  id: string;
}

interface WireError {
  type: "error";
  errorText: string;
}

interface WireFinish {
  type: "finish";
}

interface WireStart {
  type: "start";
}

interface WireAgentQuestion {
  type: "data-agent-question";
  questions: Array<{
    question: string;
    options: Array<{ value: string; label: string; description: string }>;
    multi_select: boolean;
  }>;
}

interface WireToolInputStart {
  type: "tool-input-start";
  toolCallId: string;
  toolName: string;
}

interface WireToolInputAvailable {
  type: "tool-input-available";
  toolCallId: string;
  toolName: string;
  input: Record<string, unknown>;
}

interface WireToolOutputAvailable {
  type: "tool-output-available";
  toolCallId: string;
  output: string;
}

type WireEvent =
  | WireStart
  | WireFinish
  | WireTextStart
  | WireTextDelta
  | WireTextEnd
  | WireError
  | WireAgentQuestion
  | WireToolInputStart
  | WireToolInputAvailable
  | WireToolOutputAvailable;

// --- SSE stream helpers ---

function buildRequestBody(
  opts: Pick<
    StreamOptions,
    "message" | "images" | "documents" | "persona" | "rossumUrl" | "mcpMode"
  >,
): string {
  const body: Record<string, unknown> = { content: opts.message };
  if (opts.persona) body.persona = opts.persona;
  if (opts.mcpMode) body.mcp_mode = opts.mcpMode;
  if (opts.rossumUrl) body.rossum_url = opts.rossumUrl;
  if (opts.images && opts.images.length > 0) body.images = opts.images;
  if (opts.documents && opts.documents.length > 0)
    body.documents = opts.documents;
  return JSON.stringify(body);
}

interface StreamOptions {
  config: Config;
  chatId: string;
  message: string;
  mcpMode?: string;
  persona?: string;
  rossumUrl?: string;
  images?: ImageContent[];
  documents?: DocumentContent[];
  onEvent: (event: WireEvent) => void;
  onError: (error: Error) => void;
  onDone: () => void;
  signal?: AbortSignal;
}

/** Parse SSE data lines from a chunk, returning true if [DONE] was encountered. */
function processSSEChunk(
  chunk: string,
  onEvent: (event: WireEvent) => void,
  onDone: () => void,
): boolean {
  for (const line of chunk.split("\n")) {
    if (!line.startsWith("data: ")) continue;
    const data = line.slice(6);
    if (data === "[DONE]") {
      onDone();
      return true;
    }
    try {
      onEvent(JSON.parse(data) as WireEvent);
    } catch {
      // Skip malformed events
    }
  }
  return false;
}

async function readSSEStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: WireEvent) => void,
  onDone: () => void,
  onError: (error: Error) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        if (processSSEChunk(part, onEvent, onDone)) return;
      }
    }
    onDone();
  } catch (e) {
    if (signal?.aborted) return;
    onError(e instanceof Error ? e : new Error(String(e)));
  }
}

async function streamMessage(opts: StreamOptions): Promise<void> {
  const { config, chatId, onEvent, onError, onDone, signal } = opts;
  const headers = buildHeaders(config);

  let res: Response;
  try {
    res = await fetch(`${config.apiUrl}/api/v1/chats/${chatId}/messages`, {
      method: "POST",
      headers,
      body: buildRequestBody(opts),
      signal,
    });
  } catch (err) {
    if (signal?.aborted) return;
    const detail = err instanceof Error ? err.message : String(err);
    onError(new Error(`Cannot connect to ${config.apiUrl}: ${detail}`));
    return;
  }

  if (!res.ok) {
    const text = await res.text();
    onError(new Error(`Stream request failed (${res.status}): ${text}`));
    return;
  }

  if (!res.body) {
    onError(new Error("Response body is null"));
    return;
  }

  await readSSEStream(res.body, onEvent, onDone, onError, signal);
}

// --- State helpers ---

function nextStepNumber(steps: CompletedStep[]): number {
  return steps.length + 1;
}

function commitStreaming(prev: ChatState): {
  steps: CompletedStep[];
  streaming: null;
} {
  if (!prev.currentStreaming || prev.currentStreaming.type === "tool") {
    return { steps: prev.completedSteps, streaming: null };
  }
  return {
    steps: [
      ...prev.completedSteps,
      {
        stepNumber: nextStepNumber(prev.completedSteps),
        type: prev.currentStreaming.type,
        content: prev.currentStreaming.content,
      },
    ],
    streaming: null,
  };
}

function handleFinish(prev: ChatState): ChatState {
  const lastStream = prev.currentStreaming;
  const extra: CompletedStep[] =
    lastStream && lastStream.type !== "tool"
      ? [
          {
            stepNumber: nextStepNumber(prev.completedSteps),
            type: lastStream.type,
            content: lastStream.content,
          },
        ]
      : [];
  // Mark the last text step as final_answer
  const steps = [...prev.completedSteps, ...extra];
  for (let i = steps.length - 1; i >= 0; i--) {
    if (steps[i]!.type === "text") {
      steps[i] = { ...steps[i]!, type: "final_answer" };
      break;
    }
  }
  return {
    ...prev,
    connectionStatus: "idle",
    completedSteps: steps,
    currentStreaming: null,
  };
}

function handleTextEvent(
  prev: ChatState,
  wire: WireTextStart | WireTextDelta | WireTextEnd,
): ChatState {
  if (wire.type === "text-start") {
    const committed = commitStreaming(prev);
    return {
      ...prev,
      completedSteps: committed.steps,
      currentStreaming: { type: "text", content: null },
    };
  }
  if (wire.type === "text-delta") {
    if (!prev.currentStreaming || prev.currentStreaming.type !== "text")
      return prev;
    const newContent = (prev.currentStreaming.content ?? "") + wire.delta;
    return {
      ...prev,
      currentStreaming: { ...prev.currentStreaming, content: newContent },
      finalAnswer: newContent,
    };
  }
  // text-end
  const text = prev.currentStreaming;
  if (!text || text.type !== "text") return prev;
  return {
    ...prev,
    completedSteps: [
      ...prev.completedSteps,
      {
        stepNumber: nextStepNumber(prev.completedSteps),
        type: "text",
        content: text.content,
      },
    ],
    currentStreaming: null,
  };
}

function handleToolEvent(
  prev: ChatState,
  wire: WireToolInputStart | WireToolInputAvailable | WireToolOutputAvailable,
): ChatState {
  if (wire.type === "tool-input-start") {
    const committed = commitStreaming(prev);
    const pending: PendingToolCall = {
      toolName: wire.toolName,
      toolCallId: wire.toolCallId,
    };
    return {
      ...prev,
      completedSteps: committed.steps,
      currentStreaming: {
        type: "tool",
        content: null,
        toolName: wire.toolName,
      },
      pendingToolCalls: {
        ...prev.pendingToolCalls,
        [wire.toolCallId]: pending,
      },
    };
  }
  if (wire.type === "tool-input-available") {
    const existing = prev.pendingToolCalls[wire.toolCallId];
    if (!existing) return prev;
    return {
      ...prev,
      pendingToolCalls: {
        ...prev.pendingToolCalls,
        [wire.toolCallId]: { ...existing, input: wire.input },
      },
    };
  }
  // tool-output-available
  const tc = prev.pendingToolCalls[wire.toolCallId];
  if (!tc) return prev;
  const { [wire.toolCallId]: _matched, ...remaining } = prev.pendingToolCalls; // eslint-disable-line @typescript-eslint/no-unused-vars
  const hasMorePending = Object.keys(remaining).length > 0;
  return {
    ...prev,
    completedSteps: [
      ...prev.completedSteps,
      {
        stepNumber: nextStepNumber(prev.completedSteps),
        type: "tool_call" as const,
        content: wire.output,
        toolName: tc.toolName,
        toolCallId: tc.toolCallId,
        toolArgs: tc.input ?? {},
      },
    ],
    currentStreaming: hasMorePending ? prev.currentStreaming : null,
    pendingToolCalls: remaining,
  };
}

function reduceWireEvent(prev: ChatState, wire: WireEvent): ChatState {
  const t = wire.type;
  if (t === "start") return prev;
  if (t === "finish") return handleFinish(prev);
  if (t === "error")
    return { ...prev, error: wire.errorText, connectionStatus: "error" };
  if (t.startsWith("text-"))
    return handleTextEvent(
      prev,
      wire as WireTextStart | WireTextDelta | WireTextEnd,
    );
  if (t.startsWith("tool-"))
    return handleToolEvent(
      prev,
      wire as
        | WireToolInputStart
        | WireToolInputAvailable
        | WireToolOutputAvailable,
    );
  if (t === "data-agent-question")
    return {
      ...prev,
      pendingQuestion: wire as AgentQuestionPart,
      connectionStatus: "idle",
    };
  return prev;
}

// --- Hook ---

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

  const dispatch = useCallback((wire: WireEvent) => {
    setState((prev) => reduceWireEvent(prev, wire));
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
        pendingQuestion: null,
        finalAnswer: null,
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

        await streamMessage({
          config,
          chatId,
          message,
          persona: config.persona,
          rossumUrl: config.contextUrl,
          mcpMode: config.mcpMode,
          images: options?.images as ImageContent[] | undefined,
          documents: options?.documents as DocumentContent[] | undefined,
          onEvent: dispatch,
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

      const extra: CompletedStep[] =
        prev.currentStreaming && prev.currentStreaming.type !== "tool"
          ? [
              {
                stepNumber: nextStepNumber(prev.completedSteps),
                type: prev.currentStreaming.type,
                content: prev.currentStreaming.content,
              },
            ]
          : [];

      return {
        ...prev,
        connectionStatus: "idle",
        completedSteps: [...prev.completedSteps, ...extra],
        currentStreaming: null,
        error: null,
      };
    });
  }, []);

  const submitFeedback = useCallback(
    async (turnIndex: number, isPositive: boolean) => {
      const chatId = chatIdRef.current;
      if (!chatId) return;

      setState((prev) => ({
        ...prev,
        feedback: { ...prev.feedback, [turnIndex]: isPositive },
      }));

      try {
        await apiFeedback(config, chatId, turnIndex, isPositive);
      } catch {
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
