// API types generated from OpenAPI spec — run `npm run generate` to update
import type { components } from "./generated.js";

type Schemas = components["schemas"];

// Chat
export type ChatResponse = Schemas["ChatResponse"];
export type ChatSummary = Schemas["ChatSummary"];
export type ChatDetail = Schemas["ChatDetail"];
export type ChatListResponse = Schemas["ChatListResponse"];
export type CreateChatRequest = Schemas["CreateChatRequest"];
export type DeleteResponse = Schemas["DeleteResponse"];
export type CancelResponse = Schemas["CancelResponse"];

// Messages & content
export type Message = Schemas["Message"];
export type MessageRequest = Schemas["MessageRequest"];
export type TextContent = Schemas["TextContent"];
export type ImageContent = Schemas["ImageContent"];
export type DocumentContent = Schemas["DocumentContent"];

// SSE events
export type StepEvent = Schemas["StepEvent"];
export type SubAgentProgressEvent = Schemas["SubAgentProgressEvent"];
export type SubAgentTextEvent = Schemas["SubAgentTextEvent"];
export type TaskSnapshotEvent = Schemas["TaskSnapshotEvent"];
export type AgentQuestionEvent = Schemas["AgentQuestionEvent"];
export type AgentQuestionItemSchema = Schemas["AgentQuestionItemSchema"];
export type QuestionOptionSchema = Schemas["QuestionOptionSchema"];
export type FileCreatedEvent = Schemas["FileCreatedEvent"];
export type StreamDoneEvent = Schemas["StreamDoneEvent"];

// Token usage
export type TokenUsageBySource = Schemas["TokenUsageBySource"];
export type TokenUsageBreakdown = Schemas["TokenUsageBreakdown"];
export type SubAgentTokenUsageDetail = Schemas["SubAgentTokenUsageDetail"];

// Files
export type FileInfo = Schemas["FileInfo"];
export type FileListResponse = Schemas["FileListResponse"];

// Health
export type HealthResponse = Schemas["HealthResponse"];

// Commands
export type CommandInfo = Schemas["CommandInfo"];
export type CommandListResponse = Schemas["CommandListResponse"];
export type ArgumentSuggestion = Schemas["ArgumentSuggestion"];

// Feedback
export type FeedbackRequest = Schemas["FeedbackRequest"];
export type FeedbackResponse = Schemas["FeedbackResponse"];
export type FeedbackListResponse = Schemas["FeedbackListResponse"];

// Commits
export type CommitInfo = Schemas["CommitInfo"];
export type CommitListResponse = Schemas["CommitListResponse"];
export type EntityChangeInfo = Schemas["EntityChangeInfo"];

// Slack
export type ReportToSlackRequest = Schemas["ReportToSlackRequest"];
export type ReportToSlackResponse = Schemas["ReportToSlackResponse"];

// Errors
export type ErrorResponse = Schemas["ErrorResponse"];

// Derived types
export type StepType = StepEvent["type"];
export type SubAgentStatus = SubAgentProgressEvent["status"];
export type McpMode = CreateChatRequest["mcp_mode"];
export type Persona = CreateChatRequest["persona"];

// Discriminated SSE event union
export type SSEEvent =
  | { event: "step"; data: StepEvent }
  | { event: "sub_agent_progress"; data: SubAgentProgressEvent }
  | { event: "sub_agent_text"; data: SubAgentTextEvent }
  | { event: "task_snapshot"; data: TaskSnapshotEvent }
  | { event: "agent_question"; data: AgentQuestionEvent }
  | { event: "done"; data: StreamDoneEvent }
  | { event: "file_created"; data: FileCreatedEvent };

// Client configuration
export interface ClientConfig {
  apiUrl: string;
  token: string;
  rossumUrl: string;
}
