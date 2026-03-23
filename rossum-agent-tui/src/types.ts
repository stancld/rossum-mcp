// API types from rossum-agent-client (single source of truth for OpenAPI types)
import type { components } from "rossum-agent-client";

type Schemas = components["schemas"];

// Re-export API types (direct matches)
export type ChatResponse = Schemas["ChatResponse"];
export type ChatSummary = Schemas["ChatSummary"];
export type ChatListResponse = Schemas["ChatListResponse"];
export type CommandInfo = Schemas["CommandInfo"];
export type ArgumentSuggestion = Schemas["ArgumentSuggestion"];

// Question types
export type AgentQuestionItemSchema = Schemas["AgentQuestionItemSchema"];
export type QuestionOption = Schemas["QuestionOptionSchema"];

// Task snapshot types
export type TaskSnapshotTaskSchema = Schemas["TaskSnapshotTaskSchema"];

// Agent question wire event (parsed from SSE stream)
export interface AgentQuestionPart {
  type: "data-agent-question";
  questions: AgentQuestionItemSchema[];
}

// Task snapshot wire event (parsed from SSE stream)
export interface TaskSnapshotPart {
  type: "data-task-snapshot";
  tasks: TaskSnapshotTaskSchema[];
}

// Alias for backward compatibility with question handling code
export type AgentQuestionItem = AgentQuestionItemSchema;

// --- TUI-only types below (not from the API spec) ---

export type McpMode = "read-only" | "read-write";
export type Persona = "default" | "cautious";

export interface Config {
  apiUrl: string;
  token: string;
  rossumUrl: string;
  mcpMode: McpMode;
  persona: Persona;
  contextUrl?: string;
}

export type InteractionMode = "input" | "browse";

// Step types
export type StepType =
  | "text"
  | "final_answer"
  | "error"
  | "tool_call"
  | "reasoning";

export interface CompletedStep {
  stepNumber: number;
  type: StepType;
  content: string | null;
  toolName?: string;
  toolArgs?: Record<string, unknown>;
}

export interface PendingToolCall {
  toolName: string;
  toolCallId: string;
  input?: Record<string, unknown>;
}

// Current streaming step for display
export interface StreamingStep {
  type: "text" | "tool" | "reasoning";
  content: string | null;
  toolName?: string;
}

export type ChatItem =
  | { kind: "user_message"; text: string; attachments?: AttachmentInfo[] }
  | {
      kind: "final_answer";
      content: string;
      turnIndex: number;
      feedback: boolean | null;
    }
  | { kind: "reasoning"; content: string }
  | {
      kind: "tool_call";
      toolName: string;
      args: Record<string, unknown>;
      result: string;
    }
  | {
      kind: "agent_question";
      question: string;
      options: QuestionOption[];
      multiSelect: boolean;
      questionIndex: number;
      totalQuestions: number;
    }
  | { kind: "error"; content: string }
  | { kind: "streaming"; streaming: StreamingStep }
  | { kind: "task_snapshot"; tasks: TaskSnapshotTaskSchema[] };

export interface ExpandState {
  [itemIndex: number]: boolean;
}

export interface AttachmentInfo {
  filename: string;
  type: "image" | "document" | "text";
}

export interface UserMessage {
  text: string;
  stepIndexBefore: number;
  attachments?: AttachmentInfo[];
}

export type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "streaming"
  | "idle"
  | "error";

export interface ChatState {
  chatId: string | null;
  connectionStatus: ConnectionStatus;
  completedSteps: CompletedStep[];
  currentStreaming: StreamingStep | null;
  error: string | null;
  userMessages: UserMessage[];
  feedback: Record<number, boolean>;
  pendingQuestion: AgentQuestionPart | null;
  pendingToolCalls: Record<string, PendingToolCall>;
  tasks: TaskSnapshotPart | null;
}
