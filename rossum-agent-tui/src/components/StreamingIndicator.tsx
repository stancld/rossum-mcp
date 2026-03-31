import React from "react";
import { Text, Box } from "ink";
import { Spinner } from "@inkjs/ui";
import { getDisplayToolName } from "../utils/format.js";
import type {
  StepEvent,
  SubAgentProgressEvent,
  SubAgentTextState,
} from "../types.js";

function ToolStartIndicator({
  streaming,
  subAgentProgress,
  subAgentText,
}: {
  streaming: StepEvent;
  subAgentProgress: SubAgentProgressEvent | null;
  subAgentText: SubAgentTextState | null;
}) {
  const displayName = getDisplayToolName(
    streaming.tool_name!,
    streaming.tool_arguments,
  );
  const progress = streaming.tool_progress
    ? ` (${streaming.tool_progress[0]}/${streaming.tool_progress[1]})`
    : "";

  return (
    <Box flexDirection="column">
      <Spinner label={` Running: ${displayName}${progress}`} />
      {subAgentProgress && (
        <Box flexDirection="column" marginLeft={4}>
          <Text color="blue" dimColor>
            Sub-agent ({subAgentProgress.tool_name}): iteration{" "}
            {subAgentProgress.iteration}/{subAgentProgress.max_iterations},{" "}
            {subAgentProgress.status}
            {subAgentProgress.current_tool
              ? ` [${subAgentProgress.current_tool}]`
              : ""}
          </Text>
          {(subAgentProgress.tool_calls ?? []).length > 0 && (
            <Box flexDirection="column" marginLeft={2}>
              {(subAgentProgress.tool_calls ?? []).map(
                (call: string, idx: number) => (
                  <Text key={idx} dimColor color="blue">
                    {idx === (subAgentProgress.tool_calls ?? []).length - 1 &&
                    subAgentProgress.status === "running_tool"
                      ? "  \u25B8 "
                      : "  \u2713 "}
                    {call}
                  </Text>
                ),
              )}
            </Box>
          )}
        </Box>
      )}
      {subAgentText?.text && (
        <Box marginLeft={4}>
          <Text dimColor italic wrap="wrap">
            {subAgentText.text}
          </Text>
        </Box>
      )}
    </Box>
  );
}

interface StreamingIndicatorProps {
  streaming: StepEvent;
  subAgentProgress: SubAgentProgressEvent | null;
  subAgentText: SubAgentTextState | null;
}

export function StreamingIndicator({
  streaming,
  subAgentProgress,
  subAgentText,
}: StreamingIndicatorProps) {
  if (streaming.type === "final_answer" && streaming.content) {
    return (
      <Box flexDirection="column">
        <Text wrap="wrap">
          <Text color="green" bold>
            {"● "}
          </Text>
          {streaming.content}
        </Text>
        <Spinner label=" Writing..." />
      </Box>
    );
  }

  if (streaming.type === "tool_start") {
    return (
      <ToolStartIndicator
        streaming={streaming}
        subAgentProgress={subAgentProgress}
        subAgentText={subAgentText}
      />
    );
  }

  if (streaming.type === "thinking") {
    const preview = streaming.content
      ? streaming.content.split("\n").slice(-3).join("\n")
      : "";
    return (
      <Box flexDirection="column">
        <Spinner label=" Thinking..." />
        {preview && (
          <Box marginLeft={2}>
            <Text dimColor italic wrap="wrap">
              {preview}
            </Text>
          </Box>
        )}
      </Box>
    );
  }

  if (streaming.type === "intermediate" && streaming.content) {
    return (
      <Box flexDirection="column">
        <Text wrap="wrap" dimColor>
          {"  "}
          {streaming.content}
        </Text>
        <Spinner label=" Processing..." />
      </Box>
    );
  }

  return <Spinner label=" Processing..." />;
}
