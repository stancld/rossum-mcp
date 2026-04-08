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
export type McpMode = CreateChatRequest["mcp_mode"];
export type Persona = CreateChatRequest["persona"];

// Client configuration
export interface ClientConfig {
  apiUrl: string;
  token: string;
  rossumUrl: string;
}
