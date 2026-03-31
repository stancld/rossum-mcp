import type { ChatItem, ChatState, CompletedStep } from "../types.js";

function pairSteps(
  steps: CompletedStep[],
): Array<{ step: CompletedStep; resultStep?: CompletedStep }> {
  const resultsByCallId = new Map<string, CompletedStep>();
  const resultsByStep = new Map<number, CompletedStep>();
  for (const step of steps) {
    if (step.type === "tool_result") {
      if (step.toolCallId) {
        resultsByCallId.set(step.toolCallId, step);
      } else {
        resultsByStep.set(step.stepNumber, step);
      }
    }
  }

  const pairs: Array<{ step: CompletedStep; resultStep?: CompletedStep }> = [];
  for (const step of steps) {
    if (step.type === "tool_result") continue;
    if (step.type === "tool_start") {
      const result = step.toolCallId
        ? resultsByCallId.get(step.toolCallId)
        : resultsByStep.get(step.stepNumber);
      pairs.push({ step, resultStep: result });
    } else {
      pairs.push({ step });
    }
  }
  return pairs;
}

function pairedStepToItem(
  pair: {
    step: CompletedStep;
    resultStep?: CompletedStep;
  },
  turnIndex: number,
  feedback: Record<number, boolean>,
): ChatItem {
  const { step, resultStep } = pair;
  switch (step.type) {
    case "thinking":
      return {
        kind: "thinking",
        stepNumber: step.stepNumber,
        content: step.content || "",
      };
    case "tool_start":
      return {
        kind: "tool_call",
        stepNumber: step.stepNumber,
        step,
        resultStep,
      };
    case "intermediate":
      return {
        kind: "intermediate",
        stepNumber: step.stepNumber,
        content: step.content || "",
      };
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
      return {
        kind: "intermediate",
        stepNumber: step.stepNumber,
        content: step.content || "",
      };
  }
}

function appendTrailingItems(
  items: ChatItem[],
  state: ChatState,
  paired: Array<{ step: CompletedStep; resultStep?: CompletedStep }>,
  questionIndex?: number,
): void {
  for (const f of state.files) {
    items.push({ kind: "file_created", filename: f.filename, url: f.url });
  }

  if (state.configCommit) {
    items.push({ kind: "config_commit", commit: state.configCommit });
  }

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
    (paired.length === 0 || paired[paired.length - 1]?.step.type !== "error")
  ) {
    items.push({ kind: "error", content: state.error });
  }

  if (state.currentStreaming) {
    items.push({
      kind: "streaming",
      streaming: state.currentStreaming,
      subAgentProgress: state.subAgentProgress,
      subAgentText: state.subAgentText,
    });
  }
}

export function buildChatItems(
  state: ChatState,
  questionIndex?: number,
): ChatItem[] {
  const items: ChatItem[] = [];
  const paired = pairSteps(state.completedSteps);
  const feedback = state.feedback;

  let msgIdx = 0;
  let turnIndex = 0;

  for (let i = 0; i < paired.length; ) {
    while (
      msgIdx < state.userMessages.length &&
      state.userMessages[msgIdx]!.stepIndexBefore <=
        getOriginalStepIndex(paired, i)
    ) {
      const msg = state.userMessages[msgIdx]!;
      items.push({
        kind: "user_message",
        text: msg.text,
        attachments: msg.attachments,
      });
      msgIdx++;
    }
    const pair = paired[i]!;

    // Group consecutive tool_start calls with the same tool name (3+)
    if (pair.step.type === "tool_start" && pair.step.toolName) {
      const toolName = pair.step.toolName;
      let groupEnd = i + 1;
      while (
        groupEnd < paired.length &&
        paired[groupEnd]!.step.type === "tool_start" &&
        paired[groupEnd]!.step.toolName === toolName
      ) {
        groupEnd++;
      }
      const groupSize = groupEnd - i;
      if (groupSize >= 3) {
        const calls = paired.slice(i, groupEnd);
        items.push({
          kind: "tool_group",
          toolName,
          calls,
        });
        i = groupEnd;
        continue;
      }
    }

    items.push(pairedStepToItem(pair, turnIndex, feedback));
    if (pair.step.type === "final_answer") {
      turnIndex++;
    }
    i++;
  }

  while (msgIdx < state.userMessages.length) {
    const msg = state.userMessages[msgIdx]!;
    items.push({
      kind: "user_message",
      text: msg.text,
      attachments: msg.attachments,
    });
    msgIdx++;
  }

  appendTrailingItems(items, state, paired, questionIndex);
  return items;
}

function getOriginalStepIndex(
  paired: Array<{ step: CompletedStep; resultStep?: CompletedStep }>,
  pairIndex: number,
): number {
  // Count original steps consumed by pairs before this one
  let count = 0;
  for (let i = 0; i < pairIndex; i++) {
    count++;
    if (paired[i]!.resultStep) count++;
  }
  return count;
}
