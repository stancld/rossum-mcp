import React from "react";
import { Text, Box } from "ink";
import type {
  ConnectionStatus,
  InteractionMode,
  McpMode,
  Persona,
  TokenUsageBreakdown,
} from "../types.js";

interface StatusBarProps {
  connectionStatus: ConnectionStatus;
  mcpMode: McpMode;
  persona: Persona;
  chatId: string | null;
  tokenUsage: TokenUsageBreakdown | null;
  contextUsageFraction: number | null;
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

function contextUsageColor(fraction: number): string {
  if (fraction > 0.8) return "red";
  if (fraction >= 0.5) return "yellow";
  return "green";
}

export function StatusBar({
  connectionStatus,
  mcpMode,
  persona,
  chatId,
  tokenUsage,
  contextUsageFraction,
  mode,
}: StatusBarProps) {
  const total = tokenUsage?.total;
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
        {contextUsageFraction != null && (
          <Text color={contextUsageColor(contextUsageFraction)}>
            {"  "}context: {Math.round(contextUsageFraction * 100)}%
          </Text>
        )}
        {total && (
          <Text dimColor>
            {"  "}tokens: {total.input_tokens.toLocaleString()} in /{" "}
            {total.output_tokens.toLocaleString()} out
          </Text>
        )}
      </Text>
    </Box>
  );
}
