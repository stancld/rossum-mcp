import React from "react";
import { Box, Text } from "ink";
import type { TaskSnapshotTaskSchema } from "../types.js";

const STATUS_ICON: Record<TaskSnapshotTaskSchema["status"], string> = {
  pending: "○",
  in_progress: "◐",
  completed: "●",
};

const STATUS_COLOR: Record<TaskSnapshotTaskSchema["status"], string> = {
  pending: "gray",
  in_progress: "yellow",
  completed: "green",
};

interface TaskSnapshotProps {
  tasks: TaskSnapshotTaskSchema[];
}

export const TaskSnapshot = React.memo(function TaskSnapshot({
  tasks,
}: TaskSnapshotProps) {
  return (
    <Box flexDirection="column" marginY={1}>
      <Text bold color="cyan">
        Tasks
      </Text>
      {tasks.map((task) => (
        <Box key={task.id} gap={1}>
          <Text color={STATUS_COLOR[task.status]}>
            {STATUS_ICON[task.status]}
          </Text>
          <Text wrap="wrap">
            {task.subject}
            {task.description ? (
              <Text dimColor> — {task.description}</Text>
            ) : null}
          </Text>
        </Box>
      ))}
    </Box>
  );
});
