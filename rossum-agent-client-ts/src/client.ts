import type {
  CancelResponse,
  ChatDetail,
  ChatListResponse,
  ChatResponse,
  ClientConfig,
  CommandInfo,
  CommitListResponse,
  DeleteResponse,
  FeedbackListResponse,
  FeedbackResponse,
  FileListResponse,
  HealthResponse,
  McpMode,
  Persona,
  ReportToSlackResponse,
} from "./types.js";

export function buildHeaders(config: ClientConfig): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-Rossum-Token": config.token,
    "X-Rossum-Api-Url": config.rossumUrl,
  };
}

function unwrapFetchError(err: unknown, context: string): Error {
  if (err instanceof TypeError && err.cause) {
    const cause = err.cause as { code?: string; message?: string };
    return new Error(
      `${context}: ${cause.code || cause.message || err.message}`,
    );
  }
  return err instanceof Error ? err : new Error(String(err));
}

async function request<T>(
  config: ClientConfig,
  path: string,
  init?: RequestInit,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${config.apiUrl}${path}`, {
      ...init,
      headers: { ...buildHeaders(config), ...init?.headers },
    });
  } catch (err) {
    throw unwrapFetchError(err, `Cannot connect to ${config.apiUrl}`);
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Request failed (${res.status}): ${body}`);
  }
  return (await res.json()) as T;
}

// Health

export async function healthCheck(
  config: ClientConfig,
): Promise<HealthResponse> {
  return request(config, "/api/v1/health");
}

// Chats

export async function createChat(
  config: ClientConfig,
  mcpMode: McpMode = "read-only",
  persona: Persona = "default",
): Promise<ChatResponse> {
  return request(config, "/api/v1/chats", {
    method: "POST",
    body: JSON.stringify({ mcp_mode: mcpMode, persona }),
  });
}

export async function listChats(
  config: ClientConfig,
  limit = 50,
  offset = 0,
): Promise<ChatListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return request(config, `/api/v1/chats?${params.toString()}`);
}

export async function getChat(
  config: ClientConfig,
  chatId: string,
): Promise<ChatDetail> {
  return request(config, `/api/v1/chats/${chatId}`);
}

export async function deleteChat(
  config: ClientConfig,
  chatId: string,
): Promise<DeleteResponse> {
  return request(config, `/api/v1/chats/${chatId}`, { method: "DELETE" });
}

// Messages

export async function cancelMessage(
  config: ClientConfig,
  chatId: string,
): Promise<CancelResponse> {
  return request(config, `/api/v1/chats/${chatId}/cancel`, { method: "POST" });
}

// Commands

export async function listCommands(
  config: ClientConfig,
): Promise<CommandInfo[]> {
  try {
    const data = await request<{ commands: CommandInfo[] }>(
      config,
      "/api/v1/commands",
    );
    return data.commands;
  } catch {
    return [];
  }
}

// Files

export async function listFiles(
  config: ClientConfig,
  chatId: string,
): Promise<FileListResponse> {
  return request(config, `/api/v1/chats/${chatId}/files`);
}

export async function downloadFile(
  config: ClientConfig,
  chatId: string,
  filename: string,
): Promise<ArrayBuffer> {
  let res: Response;
  try {
    res = await fetch(
      `${config.apiUrl}/api/v1/chats/${chatId}/files/${encodeURIComponent(filename)}`,
      { headers: buildHeaders(config) },
    );
  } catch (err) {
    throw unwrapFetchError(err, `Cannot connect to ${config.apiUrl}`);
  }
  if (!res.ok) {
    throw new Error(`Download failed (${res.status})`);
  }
  return res.arrayBuffer();
}

// Feedback

export async function submitFeedback(
  config: ClientConfig,
  chatId: string,
  turnIndex: number,
  isPositive: boolean,
): Promise<FeedbackResponse> {
  return request(config, `/api/v1/chats/${chatId}/feedback`, {
    method: "PUT",
    body: JSON.stringify({ turn_index: turnIndex, is_positive: isPositive }),
  });
}

export async function getFeedback(
  config: ClientConfig,
  chatId: string,
): Promise<FeedbackListResponse> {
  return request(config, `/api/v1/chats/${chatId}/feedback`);
}

export async function deleteFeedback(
  config: ClientConfig,
  chatId: string,
  turnIndex: number,
): Promise<DeleteResponse> {
  return request(config, `/api/v1/chats/${chatId}/feedback/${turnIndex}`, {
    method: "DELETE",
  });
}

// Commits

export async function listCommits(
  config: ClientConfig,
  chatId: string,
): Promise<CommitListResponse> {
  return request(config, `/api/v1/chats/${chatId}/commits`);
}

// Slack

export async function reportToSlack(
  config: ClientConfig,
  chatId: string,
  rossumUrl?: string,
): Promise<ReportToSlackResponse> {
  return request(config, `/api/v1/chats/${chatId}/report-to-slack`, {
    method: "POST",
    body: JSON.stringify(rossumUrl ? { rossum_url: rossumUrl } : {}),
  });
}
