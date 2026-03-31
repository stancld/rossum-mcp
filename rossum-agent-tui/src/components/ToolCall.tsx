import React from "react";
import { Box, Text } from "ink";
import { getDisplayToolName, truncate } from "../utils/format.js";
import type { CompletedStep } from "../types.js";

const RESULT_PREVIEW_LEN = 100;

function formatArgsSummary(args: Record<string, unknown> | null): string {
  if (!args) return "";
  const entries = Object.entries(args)
    .filter(([k]) => k !== "connection_id" && k !== "tool_name")
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
  return entries ? truncate(entries, 80) : "";
}

function resultPreview(result: string): string {
  if (result.length <= RESULT_PREVIEW_LEN) return result.replace(/\n/g, " ");
  return result.slice(0, RESULT_PREVIEW_LEN).replace(/\n/g, " ") + "...";
}

interface ToolCallSharedProps {
  displayName: string;
  progress: string;
  statusIcon: string;
  statusColor: string;
  selected: boolean;
}

function ToolCallCollapsed({
  displayName,
  progress,
  statusIcon,
  statusColor,
  selected,
  argsSummary,
  result,
}: ToolCallSharedProps & { argsSummary: string; result: string | null }) {
  return (
    <Box flexDirection="column">
      <Text inverse={selected} color="cyan">
        {"▸"} <Text color={statusColor}>{statusIcon}</Text> {displayName}
        {progress}
        {argsSummary ? ` (${argsSummary})` : ""}
      </Text>
      {result && (
        <Box marginLeft={4}>
          <Text dimColor italic>
            {resultPreview(result)}
          </Text>
        </Box>
      )}
    </Box>
  );
}

function ToolCallExpanded({
  displayName,
  progress,
  statusIcon,
  statusColor,
  selected,
  args,
  result,
  isError,
}: ToolCallSharedProps & {
  args: Record<string, unknown> | null;
  result: string | null;
  isError: boolean;
}) {
  const hasArgs = args !== null && Object.keys(args).length > 0;
  return (
    <Box flexDirection="column">
      <Text inverse={selected} color="cyan">
        {"▾"} <Text color={statusColor}>{statusIcon}</Text> {displayName}
        {progress}
      </Text>
      {hasArgs && (
        <Box marginLeft={2} flexDirection="column">
          {Object.entries(args!)
            .filter(([k]) => k !== "connection_id" && k !== "tool_name")
            .map(([k, v]) => (
              <Text key={k} dimColor>
                {k}: {typeof v === "string" ? v : JSON.stringify(v)}
              </Text>
            ))}
        </Box>
      )}
      {result && (
        <Box marginLeft={2} flexDirection="column">
          <Text bold dimColor>
            Result:
          </Text>
          <Text color={isError ? "red" : "gray"} wrap="wrap">
            {result}
          </Text>
        </Box>
      )}
    </Box>
  );
}

// Matches CAUTIOUS_CONFIRMATION_MARKER from rossum_agent.tools.core
function isPendingConfirmation(resultStep?: CompletedStep): boolean {
  return (
    (resultStep?.isError ?? false) &&
    typeof resultStep?.result === "string" &&
    resultStep.result.includes("requires user confirmation")
  );
}

function getToolStatus(resultStep?: CompletedStep): {
  icon: string;
  color: string;
} {
  if (!resultStep) return { icon: "…", color: "yellow" };
  if (isPendingConfirmation(resultStep)) return { icon: "⏳", color: "yellow" };
  if (resultStep.isError) return { icon: "✗", color: "red" };
  return { icon: "✓", color: "green" };
}

interface ToolCallProps {
  step: CompletedStep;
  resultStep?: CompletedStep;
  expanded: boolean;
  selected: boolean;
}

export function ToolCall({
  step,
  resultStep,
  expanded,
  selected,
}: ToolCallProps) {
  const displayName = getDisplayToolName(
    step.toolName ?? "",
    step.toolArguments,
  );
  const progress = step.toolProgress
    ? ` [${step.toolProgress[0]}/${step.toolProgress[1]}]`
    : "";
  const { icon: statusIcon, color: statusColor } = getToolStatus(resultStep);
  const isError = resultStep?.isError ?? false;
  const result = resultStep?.result ?? null;

  if (!expanded) {
    return (
      <ToolCallCollapsed
        displayName={displayName}
        progress={progress}
        statusIcon={statusIcon}
        statusColor={statusColor}
        selected={selected}
        argsSummary={formatArgsSummary(step.toolArguments)}
        result={result}
      />
    );
  }

  return (
    <ToolCallExpanded
      displayName={displayName}
      progress={progress}
      statusIcon={statusIcon}
      statusColor={statusColor}
      selected={selected}
      args={step.toolArguments}
      result={result}
      isError={isError}
    />
  );
}
