import React from "react";
import { Box, Text } from "ink";
import { getDisplayToolName, truncate } from "../utils/format.js";

interface ToolCallBlockProps {
  toolName: string;
  args: Record<string, unknown>;
  result: string;
  expanded: boolean;
  selected: boolean;
}

function formatArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args);
  if (entries.length === 0) return "";
  const parts = entries.map(([k, v]) => {
    const val = typeof v === "string" ? v : JSON.stringify(v);
    return `${k}=${truncate(val, 40)}`;
  });
  return parts.join(", ");
}

function resultPreview(result: string): string {
  const firstLine = result
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.length > 0);
  return truncate(firstLine || "(empty)", 60);
}

export function ToolCallBlock({
  toolName,
  args,
  result,
  expanded,
  selected,
}: ToolCallBlockProps) {
  const displayName = getDisplayToolName(toolName, args);
  const argsStr = formatArgs(args);

  if (!expanded) {
    return (
      <Text inverse={selected} dimColor>
        {"  "}
        <Text color="cyan">{"~ "}</Text>
        {displayName}
        {argsStr ? `(${truncate(argsStr, 50)})` : "()"}
        {" -> "}
        {resultPreview(result)}
      </Text>
    );
  }

  return (
    <Box flexDirection="column">
      <Text inverse={selected} dimColor>
        {"  "}
        <Text color="cyan">{"~ "}</Text>
        {displayName}({argsStr})
      </Text>
      <Box marginLeft={4}>
        <Text dimColor wrap="wrap">
          {truncate(result, 500)}
        </Text>
      </Box>
    </Box>
  );
}
