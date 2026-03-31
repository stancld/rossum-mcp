import React from "react";
import { Box, Text } from "ink";
import { AgentQuestion } from "./AgentQuestion.js";
import { ThinkingBlock } from "./ThinkingBlock.js";
import { ToolCall } from "./ToolCall.js";
import { ToolGroup } from "./ToolGroup.js";
import { StreamingIndicator } from "./StreamingIndicator.js";
import { renderMarkdown } from "../utils/markdown.js";
import { truncate } from "../utils/format.js";
import { useTerminalSize } from "../hooks/useTerminalSize.js";
import type { ChatItem, ConfigCommitInfo } from "../types.js";

interface ChatItemDisplayProps {
  item: ChatItem;
  expanded: boolean;
  selected: boolean;
}

function IntermediateBlock({
  content,
  expanded,
  selected,
}: {
  content: string;
  expanded: boolean;
  selected: boolean;
}) {
  const lines = content.split("\n");
  const lineCount = lines.length;
  const arrow = expanded ? "▾" : "▸";
  const preview = truncate(
    lines
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .slice(0, 2)
      .join(" "),
    100,
  );

  if (!expanded) {
    return (
      <Text inverse={selected} dimColor>
        {arrow} {preview || "(empty)"}
        {preview && lineCount > 1 ? ` ... (${lineCount} lines)` : ""}
      </Text>
    );
  }

  return (
    <Box flexDirection="column">
      <Text inverse={selected} dimColor>
        {arrow} Draft response ({lineCount} lines)
      </Text>
      <Box marginLeft={2}>
        <Text dimColor wrap="wrap">
          {content}
        </Text>
      </Box>
    </Box>
  );
}

function ConfigCommitItem({ commit }: { commit: ConfigCommitInfo }) {
  const suffix = commit.changesCount !== 1 ? "s" : "";
  return (
    <Text color="cyan">
      {"  ✓ "}
      <Text bold>Committed</Text> <Text dimColor>[{commit.hash}]</Text>{" "}
      {commit.message}{" "}
      <Text dimColor>
        ({commit.changesCount} change{suffix})
      </Text>
    </Text>
  );
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

// eslint-disable-next-line complexity -- discriminated union switch on ChatItem.kind
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

    case "thinking":
      return (
        <ThinkingBlock
          content={item.content}
          expanded={expanded}
          selected={selected}
        />
      );

    case "tool_call":
      return (
        <ToolCall
          step={item.step}
          resultStep={item.resultStep}
          expanded={expanded}
          selected={selected}
        />
      );

    case "tool_group":
      return (
        <ToolGroup
          toolName={item.toolName}
          calls={item.calls}
          expanded={expanded}
          selected={selected}
        />
      );

    case "intermediate":
      return (
        <IntermediateBlock
          content={item.content}
          expanded={expanded}
          selected={selected}
        />
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

    case "error":
      return (
        <Text color="red" bold>
          Error: {item.content}
        </Text>
      );

    case "file_created":
      return (
        <Text color="blue">
          {"  📎 "}
          {item.filename} - {item.url}
        </Text>
      );

    case "config_commit":
      return <ConfigCommitItem commit={item.commit} />;

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
      return (
        <StreamingIndicator
          streaming={item.streaming}
          subAgentProgress={item.subAgentProgress}
          subAgentText={item.subAgentText}
        />
      );

    default:
      return null;
  }
});
