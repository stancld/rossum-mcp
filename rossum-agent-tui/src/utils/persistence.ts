import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import type {
  AgentQuestionPart,
  ChatState,
  CompletedStep,
  TaskSnapshotPart,
  UserMessage,
} from "../types.js";

const DIR = join(homedir(), ".rossum-agent-tui");
const FILE = join(DIR, "history.json");

interface PersistedState {
  chatId: string | null;
  completedSteps: CompletedStep[];
  userMessages: UserMessage[];
  finalAnswer: string | null;
  feedback: Record<number, boolean>;
  pendingQuestion: AgentQuestionPart | null;
  tasks: TaskSnapshotPart | null;
}

function hydrateState(p: PersistedState): ChatState {
  return {
    chatId: p.chatId,
    connectionStatus: "idle",
    completedSteps: p.completedSteps ?? [],
    currentStreaming: null,
    finalAnswer: p.finalAnswer ?? null,
    error: null,
    userMessages: p.userMessages ?? [],
    feedback: p.feedback ?? {},
    pendingQuestion:
      p.pendingQuestion && Array.isArray(p.pendingQuestion.questions)
        ? p.pendingQuestion
        : null,
    pendingToolCalls: {},
    tasks: p.tasks && Array.isArray(p.tasks.tasks) ? p.tasks : null,
  };
}

export function loadPersistedState(): ChatState | null {
  try {
    const data = readFileSync(FILE, "utf-8");
    const p = JSON.parse(data) as PersistedState;
    if (!p.chatId) return null;
    return hydrateState(p);
  } catch {
    return null;
  }
}

export function savePersistedState(state: ChatState): void {
  try {
    mkdirSync(DIR, { recursive: true });
    const p: PersistedState = {
      chatId: state.chatId,
      completedSteps: state.completedSteps,
      userMessages: state.userMessages,
      finalAnswer: state.finalAnswer,
      feedback: state.feedback,
      pendingQuestion: state.pendingQuestion,
      tasks: state.tasks,
    };
    writeFileSync(FILE, JSON.stringify(p));
  } catch {
    // Non-critical: TUI works without persistence
  }
}
