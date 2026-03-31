// API types from rossum-agent-client (single source of truth for OpenAPI types)
import type { components } from "rossum-agent-client";

type Schemas = components["schemas"];

// Re-export API types (direct matches)
export type ChatResponse = Schemas["ChatResponse"];
export type ChatSummary = Schemas["ChatSummary"];
export type ChatListResponse = Schemas["ChatListResponse"];
export type StepEvent = Schemas["StepEvent"];
export type SubAgentProgressEvent = Schemas["SubAgentProgressEvent"];
export type SubAgentTextEvent = Schemas["SubAgentTextEvent"];
export type AgentQuestionEvent = Schemas["AgentQuestionEvent"];
export type FileCreatedEvent = Schemas["FileCreatedEvent"];
export type StreamDoneEvent = Schemas["StreamDoneEvent"];
export type TokenUsageBySource = Schemas["TokenUsageBySource"];
export type TokenUsageBreakdown = Schemas["TokenUsageBreakdown"];
export type SubAgentTokenUsageDetail = Schemas["SubAgentTokenUsageDetail"];
export type CommandInfo = Schemas["CommandInfo"];
export type ArgumentSuggestion = Schemas["ArgumentSuggestion"];

// Re-export with name aliases (Python schema names differ from TUI names)
export type AgentQuestionItem = Schemas["AgentQuestionItemSchema"];
export type QuestionOption = Schemas["QuestionOptionSchema"];

// Derived types
export type StepType = StepEvent["type"];
export type SubAgentStatus = SubAgentProgressEvent["status"];

// TaskSnapshotEvent: spec uses untyped dicts, TUI adds structure via TaskItem
export type TaskSnapshotEvent = Schemas["TaskSnapshotEvent"] & {
  tasks: TaskItem[];
};

// --- TUI-only types below (not from the API spec) ---

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface TaskItem {
  id: string;
  subject: string;
  status: "pending" | "in_progress" | "completed";
  [key: string]: JsonValue;
}

export interface SubAgentTextState {
  tool_name: string;
  text: string;
  is_final: boolean;
}

export interface ConfigCommitInfo {
  hash: string;
  message: string;
  changesCount: number;
}

export type SSEEvent =
  | { event: "step"; data: StepEvent }
  | { event: "sub_agent_progress"; data: SubAgentProgressEvent }
  | { event: "sub_agent_text"; data: SubAgentTextEvent }
  | { event: "task_snapshot"; data: TaskSnapshotEvent }
  | { event: "agent_question"; data: AgentQuestionEvent }
  | { event: "done"; data: StreamDoneEvent }
  | { event: "file_created"; data: FileCreatedEvent };

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

export type ChatItem =
  | { kind: "user_message"; text: string; attachments?: AttachmentInfo[] }
  | { kind: "thinking"; stepNumber: number; content: string }
  | {
      kind: "tool_call";
      stepNumber: number;
      step: CompletedStep;
      resultStep?: CompletedStep;
    }
  | {
      kind: "tool_group";
      toolName: string;
      calls: Array<{ step: CompletedStep; resultStep?: CompletedStep }>;
    }
  | { kind: "intermediate"; stepNumber: number; content: string }
  | {
      kind: "final_answer";
      content: string;
      turnIndex: number;
      feedback: boolean | null;
    }
  | { kind: "error"; content: string }
  | { kind: "file_created"; filename: string; url: string }
  | { kind: "config_commit"; commit: ConfigCommitInfo }
  | {
      kind: "agent_question";
      question: string;
      options: QuestionOption[];
      multiSelect: boolean;
      questionIndex: number;
      totalQuestions: number;
    }
  | {
      kind: "streaming";
      streaming: StepEvent;
      subAgentProgress: SubAgentProgressEvent | null;
      subAgentText: SubAgentTextState | null;
    };

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

export interface CompletedStep {
  stepNumber: number;
  type: StepType;
  content: string | null;
  toolName: string | null;
  toolArguments: Record<string, unknown> | null;
  toolProgress: [number, number] | null;
  result: string | null;
  isError: boolean;
  toolCallId: string | null;
  isHookOutput: boolean;
}

export interface ChatState {
  chatId: string | null;
  connectionStatus: ConnectionStatus;
  completedSteps: CompletedStep[];
  currentStreaming: StepEvent | null;
  tasks: TaskItem[];
  subAgentProgress: SubAgentProgressEvent | null;
  subAgentText: SubAgentTextState | null;
  finalAnswer: string | null;
  tokenUsage: TokenUsageBreakdown | null;
  configCommit: ConfigCommitInfo | null;
  files: FileCreatedEvent[];
  error: string | null;
  userMessages: UserMessage[];
  feedback: Record<number, boolean>;
  contextUsageFraction: number | null;
  pendingQuestion: AgentQuestionEvent | null;
}
