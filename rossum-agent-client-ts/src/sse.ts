import { createParser, type EventSourceMessage } from "eventsource-parser";
import { buildHeaders } from "./client.js";
import type {
  ClientConfig,
  DocumentContent,
  ImageContent,
  McpMode,
  Persona,
  SSEEvent,
} from "./types.js";

export interface StreamOptions {
  config: ClientConfig;
  chatId: string;
  message: string;
  mcpMode?: McpMode;
  persona?: Persona;
  rossumUrl?: string;
  images?: ImageContent[];
  documents?: DocumentContent[];
  onEvent: (event: SSEEvent) => void;
  onError: (error: Error) => void;
  onDone: () => void;
  signal?: AbortSignal;
}

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

function formatFetchError(err: unknown, apiUrl: string): Error {
  const cause =
    err instanceof TypeError && err.cause
      ? (err.cause as { code?: string; message?: string })
      : null;
  const detail =
    cause?.code ||
    cause?.message ||
    (err instanceof Error ? err.message : String(err));
  return new Error(`Cannot connect to ${apiUrl}: ${detail}`);
}

async function readStream(
  body: ReadableStream<Uint8Array>,
  parser: ReturnType<typeof createParser>,
  onDone: () => void,
  signal?: AbortSignal,
  onError?: (error: Error) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.feed(decoder.decode(value, { stream: true }));
    }
    onDone();
  } catch (e) {
    if (signal?.aborted) return;
    onError?.(e instanceof Error ? e : new Error(String(e)));
  }
}

export async function streamMessage(opts: StreamOptions): Promise<void> {
  const { config, chatId, onEvent, onError, onDone, signal } = opts;

  let res: Response;
  try {
    res = await fetch(`${config.apiUrl}/api/v1/chats/${chatId}/messages`, {
      method: "POST",
      headers: buildHeaders(config),
      body: buildRequestBody(opts),
      signal,
    });
  } catch (err) {
    if (signal?.aborted) return;
    onError(formatFetchError(err, config.apiUrl));
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

  const parser = createParser({
    onEvent(event: EventSourceMessage) {
      try {
        const data = JSON.parse(event.data);
        const eventType = event.event || "step";
        onEvent({ event: eventType, data } as SSEEvent);
      } catch {
        onError(new Error(`Failed to parse SSE data: ${event.data}`));
      }
    },
  });

  await readStream(res.body, parser, onDone, signal, onError);
}
