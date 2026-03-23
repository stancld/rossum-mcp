import React from "react";
import { Box, Text } from "ink";
import { AgentQuestion } from "./AgentQuestion.js";
import { StreamingIndicator } from "./StreamingIndicator.js";
import { ToolCallBlock } from "./ToolCallBlock.js";
import { renderMarkdown } from "../utils/markdown.js";
import { truncate } from "../utils/format.js";
import { useTerminalSize } from "../hooks/useTerminalSize.js";
import type { ChatItem } from "../types.js";

interface ChatItemDisplayProps {
  item: ChatItem;
  expanded: boolean;
  selected: boolean;
}

function FeedbackBadge({ feedback }: { feedback: boolean | null }) {
  if (feedback === null) return null;
  if (feedback) {
    return <Text color="green"> [+1]</Text>;
  }
  return <Text color="red"> [-1]</Text>;
}

function FinalAnswerBlock({
  content,
  expanded,
  selected,
  feedback,
}: {
  content: string;
  expanded: boolean;
  selected: boolean;
  feedback: boolean | null;
}) {
  const { columns } = useTerminalSize();
  const lines = content.split("\n");
  const lineCount = lines.length;

  if (!expanded) {
    const firstLine = truncate(
      lines.map((line) => line.trim()).find((line) => line.length > 0) || "",
      80,
    );
    return (
      <Text inverse={selected}>
        {"▸ "}
        <Text color="green" bold>
          {"● "}
        </Text>
        {firstLine || "(empty)"}
        {lineCount > 1 ? ` ... (${lineCount} lines)` : ""}
        <FeedbackBadge feedback={feedback} />
      </Text>
    );
  }

  return (
    <Box flexDirection="column">
      <Text inverse={selected}>
        {"▾ "}
        <Text color="green" bold>
          {"● "}
        </Text>
        Response
        <FeedbackBadge feedback={feedback} />
      </Text>
      <Box marginLeft={2}>
        <Text wrap="wrap">{renderMarkdown(content, columns)}</Text>
      </Box>
    </Box>
  );
}

export const ChatItemDisplay = React.memo(function ChatItemDisplay({
  item,
  expanded,
  selected,
}: ChatItemDisplayProps) {
  switch (item.kind) {
    case "user_message":
      return (
        <Box flexDirection="column">
          <Text color="green" bold wrap="wrap">
            {"❯ "}
            {item.text}
          </Text>
          {!!item.attachments?.length && (
            <Box paddingLeft={2} gap={1}>
              {item.attachments.map((att, i) => (
                <Text key={i} dimColor>
                  [{att.type === "image" ? "img" : "doc"}] {att.filename}
                </Text>
              ))}
            </Box>
          )}
        </Box>
      );

    case "final_answer":
      return (
        <FinalAnswerBlock
          content={item.content}
          expanded={expanded}
          selected={selected}
          feedback={item.feedback}
        />
      );

    case "tool_call":
      return (
        <ToolCallBlock
          toolName={item.toolName}
          args={item.args}
          result={item.result}
          expanded={expanded}
          selected={selected}
        />
      );

    case "error":
      return (
        <Text color="red" bold>
          Error: {item.content}
        </Text>
      );

    case "agent_question":
      return (
        <AgentQuestion
          question={item.question}
          options={item.options}
          multiSelect={item.multiSelect}
          questionIndex={item.questionIndex}
          totalQuestions={item.totalQuestions}
        />
      );

    case "streaming":
      return <StreamingIndicator streaming={item.streaming} />;

    default:
      return null;
  }
});
