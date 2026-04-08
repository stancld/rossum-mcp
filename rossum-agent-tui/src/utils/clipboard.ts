import { exec, spawn } from "node:child_process";
import { promisify } from "node:util";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { MAX_IMAGE_SIZE, type ImageAttachment } from "./fileAttachments.js";

const execAsync = promisify(exec);

export function copyToClipboard(text: string): Promise<void> {
  return new Promise((resolve, reject) => {
    let cmd: string;
    let args: string[];
    if (process.platform === "darwin") {
      cmd = "pbcopy";
      args = [];
    } else if (process.platform === "linux") {
      cmd = "xclip";
      args = ["-selection", "clipboard"];
    } else {
      reject(new Error("Unsupported platform"));
      return;
    }
    const proc = spawn(cmd, args, { stdio: ["pipe", "ignore", "ignore"] });
    proc.stdin.write(text);
    proc.stdin.end();
    proc.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${cmd} exited with code ${code}`));
    });
    proc.on("error", reject);
  });
}

export async function getClipboardImage(): Promise<ImageAttachment | null> {
  if (process.platform === "darwin") {
    return getMacClipboardImage();
  }
  if (process.platform === "linux") {
    return getLinuxClipboardImage();
  }
  return null;
}

async function getMacClipboardImage(): Promise<ImageAttachment | null> {
  const tmpFile = path.join(os.tmpdir(), `fabry-clipboard-${Date.now()}.png`);
  try {
    const { stdout } = await execAsync(
      `osascript -e 'try
set theImage to the clipboard as «class PNGf»
set theFile to open for access POSIX file "${tmpFile}" with write permission
write theImage to theFile
close access theFile
return "ok"
on error
return "no_image"
end try'`,
      { timeout: 5000 },
    );

    if (stdout.trim() !== "ok") return null;

    const buf = fs.readFileSync(tmpFile);
    if (buf.length > MAX_IMAGE_SIZE) return null;

    return {
      type: "image",
      media_type: "image/png",
      data: buf.toString("base64"),
    };
  } catch {
    return null;
  } finally {
    try {
      fs.unlinkSync(tmpFile);
    } catch {
      // Cleanup is best-effort
    }
  }
}

async function getLinuxClipboardImage(): Promise<ImageAttachment | null> {
  const tmpFile = path.join(os.tmpdir(), `fabry-clipboard-${Date.now()}.png`);
  try {
    const { stdout: targets } = await execAsync(
      "xclip -selection clipboard -t TARGETS -o 2>/dev/null",
      { timeout: 5000 },
    );
    if (!targets.includes("image/png")) return null;

    await execAsync(
      `xclip -selection clipboard -t image/png -o > "${tmpFile}" 2>/dev/null`,
      { timeout: 5000 },
    );

    const buf = fs.readFileSync(tmpFile);
    if (buf.length > MAX_IMAGE_SIZE) return null;

    return {
      type: "image",
      media_type: "image/png",
      data: buf.toString("base64"),
    };
  } catch {
    return null;
  } finally {
    try {
      fs.unlinkSync(tmpFile);
    } catch {
      // Cleanup is best-effort
    }
  }
}
