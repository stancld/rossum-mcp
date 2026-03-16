#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import { basename, resolve } from "node:path";
import { parseArgs } from "node:util";
import {
  createChat,
  streamMessage,
  downloadFile,
} from "rossum-agent-client";

const { values, positionals } = parseArgs({
  options: {
    x: { type: "string", short: "x" },
    r: { type: "string", short: "r" },
    "mcp-mode": { type: "string", default: "read-only" },
    persona: { type: "string", default: "default" },
    "show-thinking": { type: "boolean", default: false },
    help: { type: "boolean", short: "h", default: false },
  },
  allowPositionals: true,
  strict: true,
});

if (values.help) {
  console.error(`Usage: fabry -x "prompt" [options]

Options:
  -x PROMPT          Execute prompt directly
  -r FILE            Read prompt from file
  --mcp-mode MODE    read-only (default) | read-write
  --persona PERSONA  default (default) | cautious
  --show-thinking    Show reasoning + tool calls on stderr
  -h, --help         Show this help`);
  process.exit(0);
}

const agentApiUrl = process.env.ROSSUM_AGENT_API_URL;
const rossumApiUrl = process.env.ROSSUM_API_BASE_URL;
const rossumToken = process.env.ROSSUM_API_TOKEN;

if (!agentApiUrl || !rossumApiUrl || !rossumToken) {
  const missing = [];
  if (!agentApiUrl) missing.push("ROSSUM_AGENT_API_URL");
  if (!rossumApiUrl) missing.push("ROSSUM_API_BASE_URL");
  if (!rossumToken) missing.push("ROSSUM_API_TOKEN");
  console.error(`Missing required configuration: ${missing.join(", ")}`);
  process.exit(1);
}

let prompt = values.x;
if (!prompt && values.r) {
  prompt = readFileSync(values.r, "utf-8");
}
if (!prompt && positionals.length > 0) {
  prompt = positionals.join(" ");
}
if (!prompt) {
  console.error("Error: provide a prompt with -x or -r");
  process.exit(1);
}

const config = {
  apiUrl: agentApiUrl,
  token: rossumToken,
  rossumUrl: rossumApiUrl,
};

const mcpMode = values["mcp-mode"];
const persona = values.persona;
const showThinking = values["show-thinking"];

let chat;
try {
  chat = await createChat(config, mcpMode, persona);
} catch (err) {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
}
const chatId = chat.chat_id;

let finalAnswer = "";
const createdFiles = [];

function handleStep(step) {
  if (step.type === "final_answer") {
    if (step.content) finalAnswer = step.content;
    return;
  }
  if (step.type === "error") {
    process.stderr.write(`Error: ${step.content}\n`);
    return;
  }
  if (!showThinking) return;

  if (step.type === "thinking" && step.content) {
    process.stderr.write(`[thinking] ${step.content}\n`);
  } else if (step.type === "tool_start") {
    const progress = step.tool_progress
      ? ` (${step.tool_progress[0]}/${step.tool_progress[1]})`
      : "";
    process.stderr.write(`[tool] ${step.tool_name}${progress}\n`);
  } else if (step.type === "tool_result") {
    const status = step.is_error ? "FAILED" : "OK";
    process.stderr.write(`[tool] ${step.tool_name} → ${status}\n`);
  } else if (step.type === "intermediate" && step.content) {
    process.stderr.write(`${step.content}\n`);
  }
}

function handleEvent(event) {
  if (event.event === "step") {
    handleStep(event.data);
  } else if (event.event === "file_created") {
    createdFiles.push(event.data);
    process.stderr.write(`[file] ${event.data.filename}\n`);
  } else if (event.event === "done") {
    const usage = event.data;
    process.stderr.write(
      `[done] ${usage.total_steps} steps | ${usage.input_tokens} in / ${usage.output_tokens} out\n`,
    );
  } else if (event.event === "sub_agent_progress" && showThinking) {
    const p = event.data;
    process.stderr.write(
      `[sub-agent] ${p.tool_name}: ${p.status} (${p.iteration}/${p.max_iterations})\n`,
    );
  }
}

await new Promise((resolvePromise, reject) => {
  streamMessage({
    config,
    chatId,
    message: prompt,
    mcpMode,
    persona,
    onEvent: handleEvent,
    onError(err) {
      reject(err);
    },
    onDone() {
      resolvePromise();
    },
  });
});

// Download created files to current directory
for (const file of createdFiles) {
  try {
    const data = await downloadFile(config, chatId, file.filename);
    const outPath = resolve(process.cwd(), basename(file.filename));
    await writeFile(outPath, Buffer.from(data));
    process.stderr.write(`[saved] ${outPath}\n`);
  } catch (err) {
    process.stderr.write(`[warn] Failed to download ${file.filename}: ${err instanceof Error ? err.message : err}\n`);
  }
}

// Final answer to stdout
if (finalAnswer) {
  process.stdout.write(finalAnswer + "\n");
}
