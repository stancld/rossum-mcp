#!/usr/bin/env node
import React from "react";
import { render } from "ink";
import meow from "meow";
import { spawn, type ChildProcess } from "child_process";
import { App } from "./app.js";
import { resolveConfig } from "./hooks/useConfig.js";

async function waitForApi(
  apiUrl: string,
  abortSignal: AbortSignal,
  timeoutMs = 30000,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (abortSignal.aborted) throw new Error(abortSignal.reason as string);
    try {
      const res = await fetch(`${apiUrl}/api/v1/health`);
      if (res.ok) return;
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(
    `API at ${apiUrl} did not become ready within ${timeoutMs}ms`,
  );
}

const cli = meow(
  `
  Usage
    $ rossum-agent-tui [options]

  Options
    --api-url      Agent API URL (env: ROSSUM_AGENT_API_URL)
    --token        Rossum API token (env: ROSSUM_API_TOKEN)
    --rossum-url   Rossum API base URL (env: ROSSUM_API_BASE_URL)
    --mcp-mode     MCP mode: read-only | read-write (default: read-only)
    --persona      Agent persona: default | cautious (default: default)
    --context-url  Rossum app URL for context (e.g. queue/document page)
    --start-api    Start rossum-agent-api server automatically

  Examples
    $ rossum-agent-tui --api-url http://localhost:8000
    $ rossum-agent-tui --start-api --api-url http://localhost:8000
    $ ROSSUM_AGENT_API_URL=http://localhost:8000 rossum-agent-tui
`,
  {
    importMeta: import.meta,
    flags: {
      apiUrl: { type: "string" },
      token: { type: "string" },
      rossumUrl: { type: "string" },
      mcpMode: { type: "string" },
      persona: { type: "string" },
      contextUrl: { type: "string" },
      startApi: { type: "boolean", default: false },
    },
  },
);

async function main() {
  try {
    const config = resolveConfig(cli.flags);

    if (cli.flags.startApi) {
      const url = new URL(config.apiUrl);
      const host = url.hostname;
      const port = url.port || "8000";

      const abort = new AbortController();

      const apiProcess: ChildProcess = spawn(
        "uv",
        ["run", "rossum-agent-api", "--host", host, "--port", port],
        {
          env: {
            ...process.env,
            ROSSUM_API_TOKEN: config.token,
            ROSSUM_API_BASE_URL: config.rossumUrl,
          },
          stdio: ["ignore", "ignore", "pipe"],
        },
      );

      let stderrOutput = "";
      apiProcess.stderr?.on("data", (chunk: Buffer) => {
        stderrOutput += chunk.toString();
      });

      apiProcess.on("error", (err) => {
        const isNotFound = (err as NodeJS.ErrnoException).code === "ENOENT";
        const message = isNotFound
          ? "uv not found. Install uv (https://docs.astral.sh/uv/) and run from a directory with rossum-agent installed."
          : `Failed to start rossum-agent-api: ${err.message}`;
        abort.abort(message);
      });
      apiProcess.on("exit", (code) => {
        if (code !== 0 && code !== null) {
          const detail = stderrOutput.trim();
          abort.abort(
            `rossum-agent-api exited with code ${code}${detail ? `\n${detail}` : ""}`,
          );
        }
      });

      process.on("exit", () => apiProcess.kill());

      process.stderr.write("Starting rossum-agent-api...\n");
      await waitForApi(config.apiUrl, abort.signal);
    }

    render(<App config={config} />);
  } catch (err) {
    console.error(err instanceof Error ? err.message : String(err));
    process.exit(1);
  }
}

main();
