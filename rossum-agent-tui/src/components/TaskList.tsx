import React from "react";
import { Box, Text } from "ink";
import { Spinner } from "@inkjs/ui";
import type { TaskItem } from "../types.js";

interface TaskListProps {
  tasks: TaskItem[];
}

function TaskBadge({ task }: { task: TaskItem }) {
  switch (task.status) {
    case "completed":
      return (
        <Text color="green">
          {"  ✓ "}
          {task.subject}
        </Text>
      );
    case "in_progress":
      return <Spinner label={`  ${task.subject}`} />;
    default:
      return (
        <Text dimColor>
          {"  ○ "}
          {task.subject}
        </Text>
      );
  }
}

export function TaskList({ tasks }: TaskListProps) {
  if (tasks.length === 0) return null;

  return (
    <Box flexDirection="column" paddingX={1}>
      {tasks.map((task) => (
        <TaskBadge key={task.id} task={task} />
      ))}
    </Box>
  );
}
