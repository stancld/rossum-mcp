import React from "react";
import { Text, Box } from "ink";
import { Spinner } from "@inkjs/ui";
import type { StreamingStep } from "../types.js";

interface StreamingIndicatorProps {
  streaming: StreamingStep;
}

export function StreamingIndicator({ streaming }: StreamingIndicatorProps) {
  if (streaming.content) {
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

  return <Spinner label=" Thinking..." />;
}
