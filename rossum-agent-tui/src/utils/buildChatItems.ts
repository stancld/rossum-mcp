import type { ChatItem, ChatState, CompletedStep } from "../types.js";

function stepToItem(
  step: CompletedStep,
  turnIndex: number,
  feedback: Record<number, boolean>,
): ChatItem {
  switch (step.type) {
    case "final_answer":
      return {
        kind: "final_answer",
        content: step.content || "",
        turnIndex,
        feedback: turnIndex in feedback ? feedback[turnIndex]! : null,
      };
    case "error":
      return { kind: "error", content: step.content || "Unknown error" };
    default:
      // "text" steps that are not final_answer are intermediate —
      // they get promoted to final_answer on finish, so this case
      // only appears if streaming was aborted mid-text.
      return {
        kind: "final_answer",
        content: step.content || "",
        turnIndex,
        feedback: turnIndex in feedback ? feedback[turnIndex]! : null,
      };
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
