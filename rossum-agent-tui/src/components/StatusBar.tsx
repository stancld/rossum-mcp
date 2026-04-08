import React from "react";
import { Text, Box } from "ink";
import type {
  ConnectionStatus,
  InteractionMode,
  McpMode,
  Persona,
} from "../types.js";

interface StatusBarProps {
  connectionStatus: ConnectionStatus;
  mcpMode: McpMode;
  persona: Persona;
  chatId: string | null;
  mode: InteractionMode;
}

function statusColor(status: ConnectionStatus): string {
  switch (status) {
    case "idle":
      return "green";
    case "streaming":
    case "connecting":
      return "yellow";
    case "error":
      return "red";
    default:
      return "gray";
  }
}

export function StatusBar({
  connectionStatus,
  mcpMode,
  persona,
  chatId,
  mode,
}: StatusBarProps) {
  const modeLabel = mode === "browse" ? "[BROWSE]" : "[INPUT]";
  const modeColor = mode === "browse" ? "yellow" : "green";
  const hints =
    mode === "browse"
      ? "j/k:navigate  ^D/^U:scroll  Enter/Space:expand/collapse  +/-:feedback  i:input  ^X:stop  ^N:new chat"
      : "Esc:browse  Enter:send  M+1:Approve  M+2:Reject  M+3:Chat  ^X:stop  ^N:new chat";

  return (
    <Box
      borderStyle="single"
      borderColor="gray"
      paddingX={1}
      justifyContent="space-between"
    >
      <Text>
        <Text color={modeColor} bold>
          {modeLabel}
        </Text>
        {"  "}
        <Text color={statusColor(connectionStatus)} bold>
          {connectionStatus.toUpperCase()}
        </Text>
        {"  "}
        <Text dimColor>mode: {mcpMode}</Text>
        <Text dimColor> persona: {persona}</Text>
        {chatId && <Text dimColor> chat: {chatId.slice(0, 8)}</Text>}
      </Text>
      <Text>
        <Text dimColor>{hints}</Text>
      </Text>
    </Box>
  );
}
