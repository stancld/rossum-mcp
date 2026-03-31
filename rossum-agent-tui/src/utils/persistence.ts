import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import type {
  AgentQuestionEvent,
  ChatState,
  CompletedStep,
  UserMessage,
  TaskItem,
  FileCreatedEvent,
  TokenUsageBreakdown,
} from "../types.js";

const DIR = join(homedir(), ".rossum-agent-tui");
const FILE = join(DIR, "history.json");

interface PersistedState {
  chatId: string | null;
  completedSteps: CompletedStep[];
  userMessages: UserMessage[];
  tasks: TaskItem[];
  files: FileCreatedEvent[];
  tokenUsage: TokenUsageBreakdown | null;
  contextUsageFraction: number | null;
  finalAnswer: string | null;
  feedback: Record<number, boolean>;
  pendingQuestion: AgentQuestionEvent | null;
}

function hydrateState(p: PersistedState): ChatState {
  return {
    chatId: p.chatId,
    connectionStatus: "idle",
    completedSteps: p.completedSteps ?? [],
    currentStreaming: null,
    tasks: p.tasks ?? [],
    subAgentProgress: null,
    subAgentText: null,
    finalAnswer: p.finalAnswer ?? null,
    tokenUsage: p.tokenUsage ?? null,
    contextUsageFraction: p.contextUsageFraction ?? null,
    configCommit: null,
    files: p.files ?? [],
    error: null,
    userMessages: p.userMessages ?? [],
    feedback: p.feedback ?? {},
    pendingQuestion:
      p.pendingQuestion && Array.isArray(p.pendingQuestion.questions)
        ? p.pendingQuestion
        : null,
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
      tasks: state.tasks,
      files: state.files,
      tokenUsage: state.tokenUsage,
      contextUsageFraction: state.contextUsageFraction,
      finalAnswer: state.finalAnswer,
      feedback: state.feedback,
      pendingQuestion: state.pendingQuestion,
    };
    writeFileSync(FILE, JSON.stringify(p));
  } catch {
    // Non-critical: TUI works without persistence
  }
}
