// Raw OpenAPI types (for consumers that need schema-level access)
export type { paths, components } from "./generated.js";

// Types
export type {
  // Config
  ClientConfig,
  McpMode,
  Persona,
  // Chat
  ChatResponse,
  ChatSummary,
  ChatDetail,
  ChatListResponse,
  CreateChatRequest,
  DeleteResponse,
  CancelResponse,
  // Messages & content
  Message,
  MessageRequest,
  TextContent,
  ImageContent,
  DocumentContent,
  // Files
  FileInfo,
  FileListResponse,
  // Health
  HealthResponse,
  // Commands
  CommandInfo,
  CommandListResponse,
  ArgumentSuggestion,
  // Feedback
  FeedbackRequest,
  FeedbackResponse,
  FeedbackListResponse,
  // Commits
  CommitInfo,
  CommitListResponse,
  EntityChangeInfo,
  // Slack
  ReportToSlackRequest,
  ReportToSlackResponse,
  // Errors
  ErrorResponse,
} from "./types.js";

// Client functions
export {
  buildHeaders,
  healthCheck,
  createChat,
  listChats,
  getChat,
  deleteChat,
  cancelMessage,
  listCommands,
  listFiles,
  downloadFile,
  submitFeedback,
  getFeedback,
  deleteFeedback,
  listCommits,
  reportToSlack,
} from "./client.js";
