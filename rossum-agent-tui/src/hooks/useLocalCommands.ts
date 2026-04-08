import { useState, useCallback, useRef } from "react";
import { copyToClipboard } from "../utils/clipboard.js";
import { LOCAL_COMMANDS } from "./useCommands.js";
import type { CompletedStep } from "../types.js";

export interface Notification {
  message: string;
  type: "success" | "error";
}

export function useLocalCommands(completedSteps: CompletedStep[]) {
  const [notification, setNotification] = useState<Notification | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showNotification = useCallback(
    (message: string, type: "success" | "error" = "success") => {
      if (timerRef.current) clearTimeout(timerRef.current);
      setNotification({ message, type });
      timerRef.current = setTimeout(() => setNotification(null), 3000);
    },
    [],
  );

  const handleLocalCommand = useCallback(
    (message: string): boolean => {
      const trimmed = message.trim();
      const isLocal = LOCAL_COMMANDS.some((c) => trimmed === c.name);
      if (!isLocal) return false;

      if (trimmed === "/copy") {
        let lastFinal: CompletedStep | undefined;
        for (let i = completedSteps.length - 1; i >= 0; i--) {
          const s = completedSteps[i]!;
          if (s.type === "final_answer" && s.content) {
            lastFinal = s;
            break;
          }
        }
        if (!lastFinal?.content) {
          showNotification("No response to copy", "error");
          return true;
        }
        copyToClipboard(lastFinal.content)
          .then(() => showNotification("Copied to clipboard"))
          .catch(() =>
            showNotification("Failed to copy to clipboard", "error"),
          );
      }

      return true;
    },
    [completedSteps, showNotification],
  );

  return { notification, handleLocalCommand };
}
