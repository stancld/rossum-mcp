import fs from "node:fs";
import path from "node:path";
import os from "node:os";

export interface ImageAttachment {
  type: "image";
  media_type: string;
  data: string;
}

export interface DocumentAttachment {
  type: "document";
  media_type: string;
  data: string;
  filename: string;
}

export interface TextAttachment {
  type: "text";
  content: string;
  filename: string;
}

export type Attachment = ImageAttachment | DocumentAttachment | TextAttachment;

export interface FileEntry {
  name: string;
  isDirectory: boolean;
}

const IMAGE_EXTENSIONS: Record<string, string> = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
};

const DOCUMENT_EXTENSIONS: Record<string, string> = {
  ".pdf": "application/pdf",
};

const SPREADSHEET_EXTENSIONS = new Set([".xlsx", ".xls"]);

const TEXT_EXTENSIONS = new Set([
  ".md",
  ".markdown",
  ".txt",
  ".csv",
  ".json",
  ".yaml",
  ".yml",
  ".toml",
  ".xml",
  ".html",
  ".css",
  ".js",
  ".ts",
  ".jsx",
  ".tsx",
  ".py",
  ".rs",
  ".go",
  ".sh",
  ".bash",
  ".zsh",
  ".sql",
  ".graphql",
  ".env",
  ".cfg",
  ".ini",
  ".conf",
  ".log",
]);

function isSupportedFileExtension(ext: string): boolean {
  return (
    ext in IMAGE_EXTENSIONS ||
    ext in DOCUMENT_EXTENSIONS ||
    TEXT_EXTENSIONS.has(ext) ||
    SPREADSHEET_EXTENSIONS.has(ext)
  );
}

export const MAX_IMAGE_SIZE = 5 * 1024 * 1024; // 5MB
const MAX_DOCUMENT_SIZE = 20 * 1024 * 1024; // 20MB
const MAX_TEXT_SIZE = 1 * 1024 * 1024; // 1MB

export function expandPath(raw: string): string {
  const expanded = raw.startsWith("~/")
    ? path.join(os.homedir(), raw.slice(2))
    : raw;
  return path.resolve(expanded);
}

export function getSupportedMimeType(
  filePath: string,
): { mimeType: string; kind: "image" | "document" | "text" } | null {
  const ext = path.extname(filePath).toLowerCase();
  if (ext in IMAGE_EXTENSIONS) {
    return { mimeType: IMAGE_EXTENSIONS[ext]!, kind: "image" };
  }
  if (ext in DOCUMENT_EXTENSIONS) {
    return { mimeType: DOCUMENT_EXTENSIONS[ext]!, kind: "document" };
  }
  if (TEXT_EXTENSIONS.has(ext) || SPREADSHEET_EXTENSIONS.has(ext)) {
    return { mimeType: "text/plain", kind: "text" };
  }
  return null;
}

export function listDirectory(partialPath: string): FileEntry[] {
  const expanded = expandPath(partialPath);

  let dirPath: string;
  let prefix: string;

  try {
    const stat = fs.statSync(expanded);
    if (stat.isDirectory()) {
      dirPath = expanded;
      prefix = "";
    } else {
      dirPath = path.dirname(expanded);
      prefix = path.basename(expanded).toLowerCase();
    }
  } catch {
    dirPath = path.dirname(expanded);
    prefix = path.basename(expanded).toLowerCase();
  }

  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    const filtered = entries
      .filter((e) => {
        if (e.name.startsWith(".")) return false;
        if (prefix && !e.name.toLowerCase().startsWith(prefix)) return false;
        if (!e.isDirectory()) {
          if (!isSupportedFileExtension(path.extname(e.name).toLowerCase())) {
            return false;
          }
        }
        return true;
      })
      .sort((a, b) => {
        if (a.isDirectory() && !b.isDirectory()) return -1;
        if (!a.isDirectory() && b.isDirectory()) return 1;
        return a.name.localeCompare(b.name);
      })
      .slice(0, 20)
      .map((e) => ({ name: e.name, isDirectory: e.isDirectory() }));
    return filtered;
  } catch {
    return [];
  }
}

export function readAttachment(filePath: string): Attachment {
  const absolutePath = expandPath(filePath);
  const info = getSupportedMimeType(absolutePath);
  if (!info) {
    throw new Error(
      `Unsupported file type: ${path.extname(absolutePath) || "(no extension)"}`,
    );
  }

  const filename = path.basename(absolutePath);
  const ext = path.extname(absolutePath).toLowerCase();

  // Spreadsheets: pass file path for agent to read via execute_python
  if (SPREADSHEET_EXTENSIONS.has(ext)) {
    fs.statSync(absolutePath); // verify file exists
    return { type: "text", content: absolutePath, filename };
  }

  const stat = fs.statSync(absolutePath);
  const maxSize =
    info.kind === "image"
      ? MAX_IMAGE_SIZE
      : info.kind === "text"
        ? MAX_TEXT_SIZE
        : MAX_DOCUMENT_SIZE;
  const kindLabel =
    info.kind === "image"
      ? "Image"
      : info.kind === "text"
        ? "Text"
        : "Document";
  if (stat.size > maxSize) {
    const limitMB = maxSize / (1024 * 1024);
    throw new Error(
      `File too large (${(stat.size / (1024 * 1024)).toFixed(1)}MB). ${kindLabel} limit is ${limitMB}MB.`,
    );
  }

  if (info.kind === "text") {
    const content = fs.readFileSync(absolutePath, "utf-8");
    return { type: "text", content, filename };
  }

  const data = fs.readFileSync(absolutePath).toString("base64");

  if (info.kind === "image") {
    return { type: "image", media_type: info.mimeType, data };
  }
  return {
    type: "document",
    media_type: info.mimeType,
    data,
    filename,
  };
}

const IGNORED_DIRS = new Set([
  "node_modules",
  ".git",
  "__pycache__",
  ".venv",
  "venv",
  ".tox",
  ".mypy_cache",
  ".pytest_cache",
  ".ruff_cache",
  "dist",
  "build",
  ".next",
  ".agents",
]);

// Recursively search for files/directories whose name starts with `query`.
// Returns entries with relative paths from cwd (e.g. "rossum_agent/skills").
export function searchFiles(query: string, maxDepth: number = 4): FileEntry[] {
  const results: FileEntry[] = [];
  const lowerQuery = query.toLowerCase();
  const cwd = process.cwd();

  function walk(dir: string, depth: number, relPath: string) {
    if (depth > maxDepth) return;

    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      if (results.length >= 20) return;
      if (entry.name.startsWith(".")) continue;
      if (IGNORED_DIRS.has(entry.name)) continue;

      const entryRelPath = relPath ? relPath + "/" + entry.name : entry.name;

      if (entry.isDirectory()) {
        if (entry.name.toLowerCase().startsWith(lowerQuery)) {
          results.push({ name: entryRelPath, isDirectory: true });
        }
        walk(path.join(dir, entry.name), depth + 1, entryRelPath);
      } else if (entry.name.toLowerCase().startsWith(lowerQuery)) {
        if (isSupportedFileExtension(path.extname(entry.name).toLowerCase())) {
          results.push({ name: entryRelPath, isDirectory: false });
        }
      }
    }
  }

  walk(cwd, 0, "");

  results.sort((a, b) => {
    if (a.isDirectory && !b.isDirectory) return -1;
    if (!a.isDirectory && b.isDirectory) return 1;
    // Prefer shallower results
    const aDepth = a.name.split("/").length;
    const bDepth = b.name.split("/").length;
    if (aDepth !== bDepth) return aDepth - bDepth;
    return a.name.localeCompare(b.name);
  });

  return results.slice(0, 20);
}

// Matches @-prefixed file paths: ~/path, ./path, ../path, /path, or bare relative paths containing /
const AT_TOKEN_REGEX = /@((?:~\/|\.\/|\.\.\/|\/)[^\s]+|[^\s]+\/[^\s]*)/g;

export function parseAtTokens(text: string): string[] {
  const matches: string[] = [];
  let match: RegExpExecArray | null;
  while ((match = AT_TOKEN_REGEX.exec(text)) !== null) {
    matches.push(match[1]!);
  }
  AT_TOKEN_REGEX.lastIndex = 0;
  return matches;
}

export function stripAtTokens(text: string): string {
  return text.replace(AT_TOKEN_REGEX, "").replace(/\s+/g, " ").trim();
}
