import type { ChatItem, ChatState, CompletedStep } from "../types.js";

function makeFinalAnswer(
  content: string,
  turnIndex: number,
  feedback: Record<number, boolean>,
): ChatItem {
  return {
    kind: "final_answer",
    content,
    turnIndex,
    feedback: turnIndex in feedback ? feedback[turnIndex]! : null,
  };
}

function makeToolCall(step: CompletedStep): ChatItem {
  return {
    kind: "tool_call",
    toolName: step.toolName ?? "unknown",
    args: step.toolArgs ?? {},
    result: step.content || "",
  };
}

function stepToItem(
  step: CompletedStep,
  turnIndex: number,
  feedback: Record<number, boolean>,
): ChatItem {
  switch (step.type) {
    case "final_answer":
      return makeFinalAnswer(step.content || "", turnIndex, feedback);
    case "reasoning":
      return { kind: "reasoning", content: step.content || "" };
    case "tool_call":
      return makeToolCall(step);
    case "error":
      return { kind: "error", content: step.content || "Unknown error" };
    default:
      return makeFinalAnswer(step.content || "", turnIndex, feedback);
  }
}

function appendTrailingItems(
  items: ChatItem[],
  state: ChatState,
  questionIndex?: number,
): void {
  if (state.pendingQuestion) {
    const qi = questionIndex ?? 0;
    const currentQ = state.pendingQuestion.questions[qi];
    if (currentQ) {
      items.push({
        kind: "agent_question",
        question: currentQ.question,
        options: currentQ.options ?? [],
        multiSelect: currentQ.multi_select,
        questionIndex: qi,
        totalQuestions: state.pendingQuestion.questions.length,
      });
    }
  }

  if (state.tasks && state.tasks.tasks.length > 0) {
    items.push({ kind: "task_snapshot", tasks: state.tasks.tasks });
  }

  if (
    state.error &&
    (items.length === 0 || items[items.length - 1]?.kind !== "error")
  ) {
    items.push({ kind: "error", content: state.error });
  }

  if (state.currentStreaming) {
    items.push({
      kind: "streaming",
      streaming: state.currentStreaming,
    });
  }
}

export function buildChatItems(
  state: ChatState,
  questionIndex?: number,
): ChatItem[] {
  const items: ChatItem[] = [];
  const feedback = state.feedback;
  const steps = state.completedSteps;

  let msgIdx = 0;
  let turnIndex = 0;

  for (let i = 0; i < steps.length; i++) {
    // Insert user messages at their original positions
    while (
      msgIdx < state.userMessages.length &&
      state.userMessages[msgIdx]!.stepIndexBefore <= i
    ) {
      const msg = state.userMessages[msgIdx]!;
      items.push({
        kind: "user_message",
        text: msg.text,
        attachments: msg.attachments,
      });
      msgIdx++;
    }

    const step = steps[i]!;
    items.push(stepToItem(step, turnIndex, feedback));
    if (step.type === "final_answer") {
      turnIndex++;
    }
  }

  // Remaining user messages
  while (msgIdx < state.userMessages.length) {
    const msg = state.userMessages[msgIdx]!;
    items.push({
      kind: "user_message",
      text: msg.text,
      attachments: msg.attachments,
    });
    msgIdx++;
  }

  appendTrailingItems(items, state, questionIndex);
  return items;
}
