#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const resourcesDir = join(__dirname, "..", "resources");

if (!existsSync(join(resourcesDir, "CLAUDE.md"))) {
  console.error("Error: resources directory not found. Is the package installed correctly?");
  process.exit(1);
}

const binDir = join(__dirname, "..");
const args = ["--model", "claude-haiku-4-5-20251001", "start", ...process.argv.slice(2)];

try {
  execFileSync("claude", args, {
    cwd: resourcesDir,
    stdio: "inherit",
    env: { ...process.env, PATH: `${join(binDir, "bin")}:${process.env.PATH}` },
  });
} catch (err) {
  if (err.status != null) process.exit(err.status);
  throw err;
}
