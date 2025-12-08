/**
 * TypeScript type definitions for rossum-agent API.
 *
 * These types define the API contract between the Python backend
 * and TypeScript frontend applications.
 */

// =============================================================================
// REST API Types
// =============================================================================

/**
 * Request to create a new chat session.
 * POST /api/chat
 */
export interface ChatCreateRequest {
  api_token: string;
  api_base_url: string;
  mcp_mode?: "read-only" | "read-write";
}

/**
 * Response after creating a chat session.
 * POST /api/chat
 */
export interface ChatCreateResponse {
  chat_id: string;
}

/**
 * A single chat message.
 */
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/**
 * Response containing chat history.
 * GET /api/chat/{chat_id}
 */
export interface ChatHistoryResponse {
  chat_id: string;
  messages: ChatMessage[];
}

/**
 * Information about a generated file.
 */
export interface FileInfo {
  filename: string;
  size: number;
  timestamp: string;
}

/**
 * Response containing list of generated files.
 * GET /api/chat/{chat_id}/files
 */
export interface FilesListResponse {
  chat_id: string;
  files: FileInfo[];
}

/**
 * Chat metadata for listing.
 */
export interface ChatInfo {
  chat_id: string;
  timestamp: number;
  message_count: number;
  first_message: string;
}

/**
 * Response containing list of chats.
 * GET /api/chats
 */
export interface ChatsListResponse {
  chats: ChatInfo[];
}

// =============================================================================
// WebSocket Message Types
// =============================================================================

/**
 * Information about a tool call made by the agent.
 */
export interface ToolCallInfo {
  name: string;
  arguments: Record<string, unknown>;
}

/**
 * Planning step - agent's high-level plan.
 */
export interface PlanningStepResponse {
  type: "planning";
  plan: string;
}

/**
 * Action step - a single step in the ReAct loop.
 */
export interface ActionStepResponse {
  type: "action";
  step_number: number;
  model_output: string | null;
  tool_calls: ToolCallInfo[];
  observations: string | null;
  is_final_answer: boolean;
  action_output: string | null;
  error: string | null;
}

/**
 * Final answer step - the agent's conclusion.
 */
export interface FinalAnswerStepResponse {
  type: "final_answer";
  output: string;
}

/**
 * Error response from WebSocket.
 */
export interface ErrorResponse {
  type: "error";
  message: string;
}

/**
 * Completion response after agent finishes.
 */
export interface CompleteResponse {
  type: "complete";
  chat_id: string;
  new_files?: string[];
}

/**
 * Chat ID assignment (when connecting with invalid/new chat_id).
 */
export interface ChatIdAssignedResponse {
  type: "chat_id_assigned";
  chat_id: string;
}

/**
 * Pong response to ping.
 */
export interface PongResponse {
  type: "pong";
}

/**
 * Union type for all possible WebSocket responses from server.
 */
export type WSServerMessage =
  | PlanningStepResponse
  | ActionStepResponse
  | FinalAnswerStepResponse
  | ErrorResponse
  | CompleteResponse
  | ChatIdAssignedResponse
  | PongResponse;

/**
 * Type guard for planning step.
 */
export function isPlanningStep(msg: WSServerMessage): msg is PlanningStepResponse {
  return msg.type === "planning";
}

/**
 * Type guard for action step.
 */
export function isActionStep(msg: WSServerMessage): msg is ActionStepResponse {
  return msg.type === "action";
}

/**
 * Type guard for final answer step.
 */
export function isFinalAnswerStep(msg: WSServerMessage): msg is FinalAnswerStepResponse {
  return msg.type === "final_answer";
}

/**
 * Type guard for error.
 */
export function isError(msg: WSServerMessage): msg is ErrorResponse {
  return msg.type === "error";
}

/**
 * Type guard for completion.
 */
export function isComplete(msg: WSServerMessage): msg is CompleteResponse {
  return msg.type === "complete";
}

// =============================================================================
// WebSocket Client Message Types
// =============================================================================

/**
 * Configuration message - must be sent first after connecting.
 */
export interface WSConfigMessage {
  type: "config";
  api_token: string;
  api_base_url: string;
  mcp_mode?: "read-only" | "read-write";
}

/**
 * Prompt message - send user query to agent.
 */
export interface WSPromptMessage {
  type: "prompt";
  content: string;
}

/**
 * Ping message for keepalive.
 */
export interface WSPingMessage {
  type: "ping";
}

/**
 * Union type for all possible WebSocket messages to server.
 */
export type WSClientMessage = WSConfigMessage | WSPromptMessage | WSPingMessage;

// =============================================================================
// API Client Helper Types
// =============================================================================

/**
 * Configuration for the API client.
 */
export interface RossumAgentAPIConfig {
  /** Base URL of the API server (e.g., "http://localhost:8000") */
  baseUrl: string;
  /** Rossum API token for authentication */
  apiToken: string;
  /** Rossum API base URL */
  apiBaseUrl: string;
  /** MCP mode */
  mcpMode?: "read-only" | "read-write";
}

/**
 * Callbacks for WebSocket events.
 */
export interface WSCallbacks {
  onPlanningStep?: (step: PlanningStepResponse) => void;
  onActionStep?: (step: ActionStepResponse) => void;
  onFinalAnswer?: (step: FinalAnswerStepResponse) => void;
  onError?: (error: ErrorResponse) => void;
  onComplete?: (response: CompleteResponse) => void;
  onDisconnect?: () => void;
}
