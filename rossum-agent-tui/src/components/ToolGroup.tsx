import React from "react";
import { Box, Text } from "ink";
import { getDisplayToolName, truncate } from "../utils/format.js";
import type { CompletedStep } from "../types.js";

function extractKeyArg(args: Record<string, unknown> | null): string | null {
  if (!args) return null;
  for (const key of [
    "query",
    "pattern",
    "slug",
    "text",
    "objective",
    "url",
    "path",
    "name",
  ]) {
    const val = args[key];
    if (typeof val === "string" && val.trim()) {
      return truncate(val.trim(), 60);
    }
  }
  return null;
}

function GroupHeader({
  displayName,
  count,
  successCount,
  errorCount,
  arrow,
  selected,
}: {
  displayName: string;
  count: number;
  successCount: number;
  errorCount: number;
  arrow: string;
  selected: boolean;
}) {
  return (
    <Text inverse={selected} color="cyan">
      {arrow}{" "}
      <Text color={errorCount > 0 ? "yellow" : "green"}>
        {errorCount > 0 ? "!" : "\u2713"}
      </Text>{" "}
      {displayName} x{count}
      <Text dimColor>
        {" "}
        ({successCount} ok{errorCount > 0 ? `, ${errorCount} failed` : ""})
      </Text>
    </Text>
  );
}

function GroupCallRow({
  call,
  idx,
}: {
  call: { step: CompletedStep; resultStep?: CompletedStep };
  idx: number;
}) {
  const keyArg = extractKeyArg(call.step.toolArguments);
  const isError = call.resultStep?.isError ?? false;
  const result = call.resultStep?.result
    ? ` \u2192 ${truncate(call.resultStep.result.replace(/\n/g, " "), 80)}`
    : "";
  return (
    <Text dimColor>
      <Text color={isError ? "red" : "green"}>
        {isError ? "\u2717" : "\u2713"}
      </Text>{" "}
      #{idx + 1}
      {keyArg ? `: ${keyArg}` : ""}
      {result}
    </Text>
  );
}

interface ToolGroupProps {
  toolName: string;
  calls: Array<{ step: CompletedStep; resultStep?: CompletedStep }>;
  expanded: boolean;
  selected: boolean;
}

export function ToolGroup({
  toolName,
  calls,
  expanded,
  selected,
}: ToolGroupProps) {
  const displayName = getDisplayToolName(
    toolName,
    calls[0]?.step.toolArguments ?? null,
  );
  const errorCount = calls.filter((c) => c.resultStep?.isError).length;
  const successCount = calls.length - errorCount;

  const lastCall = calls[calls.length - 1]!;
  const lastResult = lastCall.resultStep?.result
    ? truncate(lastCall.resultStep.result.replace(/\n/g, " "), 80)
    : null;

  const headerProps = {
    displayName,
    count: calls.length,
    successCount,
    errorCount,
    selected,
  };

  if (!expanded) {
    return (
      <Box flexDirection="column">
        <GroupHeader {...headerProps} arrow="▸" />
        {lastResult && (
          <Box marginLeft={4}>
            <Text dimColor italic>
              {lastResult}
            </Text>
          </Box>
        )}
      </Box>
    );
  }

  return (
    <Box flexDirection="column">
      <GroupHeader {...headerProps} arrow="▾" />
      <Box flexDirection="column" marginLeft={2}>
        {calls.map((call, idx) => (
          <GroupCallRow key={idx} call={call} idx={idx} />
        ))}
      </Box>
    </Box>
  );
}
