/**
 * Example TypeScript client for rossum-agent API.
 *
 * This demonstrates how to integrate with the rossum-agent backend
 * from a TypeScript/JavaScript frontend application.
 *
 * Usage:
 *   import { RossumAgentClient } from './client';
 *
 *   const client = new RossumAgentClient({
 *     baseUrl: 'http://localhost:8000',
 *     apiToken: 'your-rossum-api-token',
 *     apiBaseUrl: 'https://your-instance.rossum.app',
 *   });
 *
 *   // Send a message and handle streaming responses
 *   await client.sendMessage('Document all hooks for queue 12345', {
 *     onActionStep: (step) => console.log('Step:', step.step_number),
 *     onFinalAnswer: (answer) => console.log('Answer:', answer.output),
 *   });
 */

import type {
  RossumAgentAPIConfig,
  WSCallbacks,
  WSServerMessage,
  ChatCreateResponse,
  ChatHistoryResponse,
  FilesListResponse,
  ChatsListResponse,
  WSConfigMessage,
  WSPromptMessage,
} from "./api";

/**
 * Client for interacting with rossum-agent API.
 */
export class RossumAgentClient {
  private config: RossumAgentAPIConfig;
  private ws: WebSocket | null = null;
  private chatId: string | null = null;
  private callbacks: WSCallbacks = {};
  private isConfigured = false;

  constructor(config: RossumAgentAPIConfig) {
    this.config = config;
  }

  // ===========================================================================
  // REST API Methods
  // ===========================================================================

  /**
   * Create a new chat session.
   */
  async createChat(): Promise<string> {
    const response = await fetch(`${this.config.baseUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_token: this.config.apiToken,
        api_base_url: this.config.apiBaseUrl,
        mcp_mode: this.config.mcpMode ?? "read-only",
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to create chat: ${response.statusText}`);
    }

    const data: ChatCreateResponse = await response.json();
    this.chatId = data.chat_id;
    return data.chat_id;
  }

  /**
   * Get chat history.
   */
  async getChatHistory(chatId?: string): Promise<ChatHistoryResponse> {
    const id = chatId ?? this.chatId;
    if (!id) throw new Error("No chat ID available");

    const response = await fetch(`${this.config.baseUrl}/api/chat/${id}`);
    if (!response.ok) {
      throw new Error(`Failed to get chat history: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * List all chats.
   */
  async listChats(userId?: string): Promise<ChatsListResponse> {
    const url = new URL(`${this.config.baseUrl}/api/chats`);
    if (userId) url.searchParams.set("user_id", userId);

    const response = await fetch(url.toString());
    if (!response.ok) {
      throw new Error(`Failed to list chats: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Delete a chat session.
   */
  async deleteChat(chatId?: string): Promise<void> {
    const id = chatId ?? this.chatId;
    if (!id) throw new Error("No chat ID available");

    const response = await fetch(`${this.config.baseUrl}/api/chat/${id}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      throw new Error(`Failed to delete chat: ${response.statusText}`);
    }

    if (id === this.chatId) {
      this.chatId = null;
    }
  }

  /**
   * List files for a chat.
   */
  async listFiles(chatId?: string): Promise<FilesListResponse> {
    const id = chatId ?? this.chatId;
    if (!id) throw new Error("No chat ID available");

    const response = await fetch(`${this.config.baseUrl}/api/chat/${id}/files`);
    if (!response.ok) {
      throw new Error(`Failed to list files: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Download a file.
   */
  async downloadFile(filename: string, chatId?: string): Promise<Blob> {
    const id = chatId ?? this.chatId;
    if (!id) throw new Error("No chat ID available");

    const response = await fetch(
      `${this.config.baseUrl}/api/chat/${id}/files/${encodeURIComponent(filename)}`
    );

    if (!response.ok) {
      throw new Error(`Failed to download file: ${response.statusText}`);
    }

    return response.blob();
  }

  /**
   * Get file download URL.
   */
  getFileUrl(filename: string, chatId?: string): string {
    const id = chatId ?? this.chatId;
    if (!id) throw new Error("No chat ID available");
    return `${this.config.baseUrl}/api/chat/${id}/files/${encodeURIComponent(filename)}`;
  }

  // ===========================================================================
  // WebSocket Methods
  // ===========================================================================

  /**
   * Connect to WebSocket for real-time chat.
   */
  async connect(chatId?: string): Promise<void> {
    const id = chatId ?? this.chatId ?? "new";
    const wsUrl = `${this.config.baseUrl.replace(/^http/, "ws")}/ws/chat/${id}`;

    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        // Send config message immediately after connecting
        const configMsg: WSConfigMessage = {
          type: "config",
          api_token: this.config.apiToken,
          api_base_url: this.config.apiBaseUrl,
          mcp_mode: this.config.mcpMode ?? "read-only",
        };
        this.ws!.send(JSON.stringify(configMsg));
        this.isConfigured = true;
        resolve();
      };

      this.ws.onerror = (error) => {
        reject(error);
      };

      this.ws.onclose = () => {
        this.isConfigured = false;
        this.callbacks.onDisconnect?.();
      };

      this.ws.onmessage = (event) => {
        const msg: WSServerMessage = JSON.parse(event.data);
        this.handleMessage(msg);
      };
    });
  }

  /**
   * Disconnect WebSocket.
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.isConfigured = false;
    }
  }

  /**
   * Send a message to the agent.
   * Returns a promise that resolves when the agent completes.
   */
  async sendMessage(content: string, callbacks?: WSCallbacks): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      await this.connect();
    }

    if (callbacks) {
      this.callbacks = { ...this.callbacks, ...callbacks };
    }

    return new Promise((resolve, reject) => {
      const originalOnComplete = this.callbacks.onComplete;
      const originalOnError = this.callbacks.onError;

      this.callbacks.onComplete = (response) => {
        originalOnComplete?.(response);
        this.chatId = response.chat_id;
        resolve();
      };

      this.callbacks.onError = (error) => {
        originalOnError?.(error);
        reject(new Error(error.message));
      };

      const promptMsg: WSPromptMessage = {
        type: "prompt",
        content,
      };

      this.ws!.send(JSON.stringify(promptMsg));
    });
  }

  /**
   * Set callbacks for WebSocket events.
   */
  setCallbacks(callbacks: WSCallbacks): void {
    this.callbacks = callbacks;
  }

  /**
   * Send ping to keep connection alive.
   */
  ping(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "ping" }));
    }
  }

  /**
   * Get current chat ID.
   */
  getChatId(): string | null {
    return this.chatId;
  }

  /**
   * Check if WebSocket is connected.
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  // ===========================================================================
  // Private Methods
  // ===========================================================================

  private handleMessage(msg: WSServerMessage): void {
    switch (msg.type) {
      case "planning":
        this.callbacks.onPlanningStep?.(msg);
        break;
      case "action":
        this.callbacks.onActionStep?.(msg);
        break;
      case "final_answer":
        this.callbacks.onFinalAnswer?.(msg);
        break;
      case "error":
        this.callbacks.onError?.(msg);
        break;
      case "complete":
        this.callbacks.onComplete?.(msg);
        break;
      case "chat_id_assigned":
        this.chatId = msg.chat_id;
        break;
      case "pong":
        // Ignore pong responses
        break;
    }
  }
}

// ===========================================================================
// React Hook Example (for reference)
// ===========================================================================

/**
 * Example React hook for using the client.
 * Note: This is just for reference - copy and adapt to your needs.
 *
 * ```tsx
 * import { useRossumAgent } from './hooks/useRossumAgent';
 *
 * function ChatComponent() {
 *   const {
 *     messages,
 *     isLoading,
 *     currentStep,
 *     sendMessage,
 *     files,
 *   } = useRossumAgent({
 *     baseUrl: 'http://localhost:8000',
 *     apiToken: process.env.ROSSUM_API_TOKEN,
 *     apiBaseUrl: process.env.ROSSUM_API_BASE_URL,
 *   });
 *
 *   return (
 *     <div>
 *       {messages.map((msg, i) => (
 *         <div key={i} className={msg.role}>{msg.content}</div>
 *       ))}
 *       {isLoading && <div>Step {currentStep}...</div>}
 *       <input onSubmit={(e) => sendMessage(e.target.value)} />
 *     </div>
 *   );
 * }
 * ```
 */
export interface UseRossumAgentOptions extends RossumAgentAPIConfig {
  onError?: (error: Error) => void;
}

export interface UseRossumAgentReturn {
  messages: Array<{ role: "user" | "assistant"; content: string }>;
  isLoading: boolean;
  currentStep: number | null;
  plan: string | null;
  sendMessage: (content: string) => Promise<void>;
  files: Array<{ filename: string; size: number }>;
  chatId: string | null;
  reset: () => void;
}
