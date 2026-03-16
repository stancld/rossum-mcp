import React, {
  useState,
  useCallback,
  useEffect,
  useMemo,
  useRef,
} from "react";
import { Box, useInput } from "ink";
import { ChatView, estimateItemHeight } from "./components/ChatView.js";
import { InputArea } from "./components/InputArea.js";
import { QuestionSelector } from "./components/QuestionSelector.js";
import { StatusBar } from "./components/StatusBar.js";
import { TaskList } from "./components/TaskList.js";
import { useChat } from "./hooks/useChat.js";
import { useCommands } from "./hooks/useCommands.js";
import { useMouseScroll } from "./hooks/useMouseScroll.js";
import { useTerminalSize } from "./hooks/useTerminalSize.js";
import { buildChatItems } from "./utils/buildChatItems.js";
import {
  parseAtTokens,
  readAttachment,
  type ImageAttachment,
  type DocumentAttachment,
  type TextAttachment,
} from "./utils/fileAttachments.js";
import { getClipboardImage } from "./utils/clipboard.js";
import type {
  AgentQuestionItem,
  AttachmentInfo,
  Config,
  ExpandState,
  InteractionMode,
} from "./types.js";

interface ProcessedAttachments {
  images: ImageAttachment[];
  documents: DocumentAttachment[];
  textFiles: TextAttachment[];
  attachmentInfos: AttachmentInfo[];
  errors: string[];
}

function processAttachments(paths: string[]): ProcessedAttachments {
  const images: ImageAttachment[] = [];
  const documents: DocumentAttachment[] = [];
  const textFiles: TextAttachment[] = [];
  const attachmentInfos: AttachmentInfo[] = [];
  const errors: string[] = [];

  for (const filePath of paths) {
    try {
      const attachment = readAttachment(filePath);
      if (attachment.type === "image") {
        if (images.length < 5) {
          images.push(attachment);
          attachmentInfos.push({
            filename: filePath.split("/").pop() ?? filePath,
            type: "image",
          });
        }
      } else if (attachment.type === "text") {
        textFiles.push(attachment);
        attachmentInfos.push({
          filename: attachment.filename,
          type: "text",
        });
      } else {
        if (documents.length < 5) {
          documents.push(attachment);
          attachmentInfos.push({
            filename: attachment.filename,
            type: "document",
          });
        }
      }
    } catch (err) {
      errors.push(
        `${filePath}: ${err instanceof Error ? err.message : String(err)}`,
      );
    }
  }

  return { images, documents, textFiles, attachmentInfos, errors };
}

function buildMessageContent(
  message: string,
  textFiles: TextAttachment[],
  errors: string[],
): string {
  let content = message.replace(/\s+/g, " ").trim();
  if (!content && textFiles.length === 0) {
    content = "See attached files.";
  }

  if (textFiles.length > 0) {
    const inlined = textFiles
      .map(
        (f) =>
          `<file_content path="${f.filename}">\n${f.content}\n</file_content>`,
      )
      .join("\n\n");
    content = content ? `${content}\n\n${inlined}` : inlined;
  }

  if (errors.length > 0) {
    content += "\n\n[Attachment errors: " + errors.join("; ") + "]";
  }

  return content;
}

function buildDisplayMessage(message: string): string {
  const cleaned = message.replace(/\s+/g, " ").trim();
  return cleaned || "See attached files.";
}

interface AppProps {
  config: Config;
}

const INTRA_SCROLL_STEP = 3;

function computeMaxIntraOffset(
  item: ReturnType<typeof buildChatItems>[number] | undefined,
  expanded: boolean,
  width: number,
  viewportHeight: number,
): number {
  if (!item) return 0;
  const h = estimateItemHeight(item, expanded, width);
  return h > viewportHeight ? h - viewportHeight : 0;
}

function isExpandable(kind: string): boolean {
  return (
    kind === "thinking" ||
    kind === "tool_call" ||
    kind === "tool_group" ||
    kind === "intermediate" ||
    kind === "final_answer"
  );
}

export function App({ config }: AppProps) {
  const { state, sendMessage, resetChat, abortStreaming, submitFeedback } =
    useChat(config);
  const { commands } = useCommands(config);
  const { rows, columns } = useTerminalSize();

  const [mode, setMode] = useState<InteractionMode>("input");
  const [expandState, setExpandState] = useState<ExpandState>({});
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [autoScroll, setAutoScroll] = useState(true);
  const [inputAreaRows, setInputAreaRows] = useState(1);
  const [scrollNudge, setScrollNudge] = useState(0);
  const [intraScrollOffset, setIntraScrollOffset] = useState(0);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [questionAnswers, setQuestionAnswers] = useState<string[]>([]);
  const [otherSelected, setOtherSelected] = useState(false);
  const [pendingImages, setPendingImages] = useState<ImageAttachment[]>([]);

  // Reset question iteration state when a new question event arrives
  const pendingRef = useRef(state.pendingQuestion);
  useEffect(() => {
    if (state.pendingQuestion !== pendingRef.current) {
      pendingRef.current = state.pendingQuestion;
      setQuestionIndex(0);
      setQuestionAnswers([]);
      setOtherSelected(false);
    }
  }, [state.pendingQuestion]);

  const items = useMemo(
    () => buildChatItems(state, questionIndex),
    [state, questionIndex],
  );

  // Layout: ChatView (flex) + InputArea (1+ rows) + TaskList (N rows) + StatusBar (3 rows with border)
  const taskListHeight = state.tasks.length;
  const fixedHeight = 3 + inputAreaRows + taskListHeight; // statusBar + input + taskList
  const chatAreaHeight = Math.max(rows - fixedHeight, 1);

  useEffect(() => {
    if (autoScroll && items.length > 0) {
      const lastIndex = items.length - 1;
      setSelectedIndex((prev) => (prev === lastIndex ? prev : lastIndex));
      const lastItem = items[lastIndex];
      if (lastItem) {
        const h = estimateItemHeight(
          lastItem,
          !!expandState[lastIndex],
          columns,
        );
        if (h > chatAreaHeight) {
          setIntraScrollOffset(Math.max(0, h - chatAreaHeight));
        }
      }
    }
  }, [items, autoScroll, expandState, columns, chatAreaHeight]);

  useEffect(() => {
    let latestFinalAnswerIndex = -1;
    for (let i = items.length - 1; i >= 0; i--) {
      if (items[i]?.kind === "final_answer") {
        latestFinalAnswerIndex = i;
        break;
      }
    }

    setExpandState((prev) => {
      let changed = false;
      const next = { ...prev };
      items.forEach((item, i) => {
        if (isExpandable(item.kind) && !(i in next)) {
          next[i] =
            item.kind === "final_answer" && i === latestFinalAnswerIndex;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [items]);

  const handleSendMessage = useCallback(
    async (message: string) => {
      setAutoScroll(true);
      setExpandState({});
      setIntraScrollOffset(0);

      const paths = parseAtTokens(message);
      const processed =
        paths.length > 0
          ? processAttachments(paths)
          : {
              images: [],
              documents: [],
              textFiles: [],
              attachmentInfos: [],
              errors: [],
            };

      // Merge clipboard-pasted images with @-file images
      const allImages = [...pendingImages, ...processed.images];
      const allInfos: AttachmentInfo[] = [
        ...pendingImages.map((_, i) => ({
          filename: `Pasted image ${i + 1}`,
          type: "image" as const,
        })),
        ...processed.attachmentInfos,
      ];

      const hasAttachments =
        allImages.length > 0 ||
        processed.documents.length > 0 ||
        processed.textFiles.length > 0;

      if (!hasAttachments) {
        sendMessage(message);
      } else {
        const content = buildMessageContent(
          message,
          processed.textFiles,
          processed.errors,
        );
        const displayMessage = buildDisplayMessage(message);

        sendMessage(content, {
          displayMessage,
          images: allImages.length > 0 ? allImages : undefined,
          documents:
            processed.documents.length > 0 ? processed.documents : undefined,
          attachmentInfos: allInfos.length > 0 ? allInfos : undefined,
        });
      }

      setPendingImages([]);
    },
    [sendMessage, pendingImages],
  );

  const handleQuestionAnswer = useCallback(
    (answer: string) => {
      const pq = state.pendingQuestion;
      if (!pq) return;

      const updatedAnswers = [...questionAnswers, answer];
      if (updatedAnswers.length < pq.questions.length) {
        setQuestionAnswers(updatedAnswers);
        setQuestionIndex(updatedAnswers.length);
        setOtherSelected(false);
        return;
      }

      // All questions answered — format combined answer and send
      const combined = pq.questions
        .map(
          (q: AgentQuestionItem, i: number) =>
            `${i + 1}. ${q.question}\n${updatedAnswers[i]}`,
        )
        .join("\n\n");
      setAutoScroll(true);
      setExpandState({});
      sendMessage(combined);
    },
    [state.pendingQuestion, questionAnswers, sendMessage],
  );

  const sendQuickReply = useCallback(
    (message: string) => {
      if (mode !== "input") return;
      if (
        state.connectionStatus === "connecting" ||
        state.connectionStatus === "streaming"
      ) {
        return;
      }
      handleSendMessage(message);
    },
    [handleSendMessage, mode, state.connectionStatus],
  );

  const handleBrowseDown = useCallback(() => {
    const maxOffset = computeMaxIntraOffset(
      items[selectedIndex],
      !!expandState[selectedIndex],
      columns,
      chatAreaHeight,
    );
    if (maxOffset > 0 && intraScrollOffset < maxOffset) {
      setAutoScroll(false);
      setIntraScrollOffset((prev) =>
        Math.min(prev + INTRA_SCROLL_STEP, maxOffset),
      );
      return;
    }
    if (selectedIndex >= items.length - 1) return;
    setIntraScrollOffset(0);
    setSelectedIndex((prev) => {
      const next = Math.min(prev + 1, items.length - 1);
      if (next === items.length - 1) setAutoScroll(true);
      return next;
    });
  }, [
    items,
    expandState,
    columns,
    chatAreaHeight,
    selectedIndex,
    intraScrollOffset,
  ]);

  const handleBrowseUp = useCallback(() => {
    if (intraScrollOffset > 0) {
      setAutoScroll(false);
      setIntraScrollOffset((prev) => Math.max(prev - INTRA_SCROLL_STEP, 0));
      return;
    }
    const nextIdx = Math.max(selectedIndex - 1, 0);
    if (nextIdx < selectedIndex) {
      setAutoScroll(false);
      setIntraScrollOffset(
        computeMaxIntraOffset(
          items[nextIdx],
          !!expandState[nextIdx],
          columns,
          chatAreaHeight,
        ),
      );
    }
    setSelectedIndex(nextIdx);
  }, [
    items,
    expandState,
    columns,
    chatAreaHeight,
    selectedIndex,
    intraScrollOffset,
  ]);

  const handleBrowseNavigation = useCallback(
    (input: string, key: { downArrow: boolean; upArrow: boolean }) => {
      if (input === "j" || key.downArrow) {
        handleBrowseDown();
        return true;
      }
      if (input === "k" || key.upArrow) {
        handleBrowseUp();
        return true;
      }
      if (input === "G") {
        const lastIdx = Math.max(items.length - 1, 0);
        setSelectedIndex(lastIdx);
        setAutoScroll(true);
        setIntraScrollOffset(
          computeMaxIntraOffset(
            items[lastIdx],
            !!expandState[lastIdx],
            columns,
            chatAreaHeight,
          ),
        );
        return true;
      }
      return false;
    },
    [
      handleBrowseDown,
      handleBrowseUp,
      items,
      expandState,
      columns,
      chatAreaHeight,
    ],
  );

  const handleBrowseScroll = useCallback(
    (input: string, key: { ctrl: boolean }) => {
      if (!key.ctrl) return false;
      const half = Math.max(Math.floor(chatAreaHeight / 2), 1);
      const maxOffset = computeMaxIntraOffset(
        items[selectedIndex],
        !!expandState[selectedIndex],
        columns,
        chatAreaHeight,
      );
      if (input === "d") {
        setAutoScroll(false);
        if (maxOffset > 0) {
          setIntraScrollOffset((prev) => Math.min(prev + half, maxOffset));
        } else {
          setScrollNudge((prev) => prev + half);
        }
        return true;
      }
      if (input === "u") {
        setAutoScroll(false);
        if (maxOffset > 0) {
          setIntraScrollOffset((prev) => Math.max(prev - half, 0));
        } else {
          setScrollNudge((prev) => prev - half);
        }
        return true;
      }
      return false;
    },
    [chatAreaHeight, items, selectedIndex, expandState, columns],
  );

  const handleMouseScrollUp = useCallback(() => {
    setAutoScroll(false);
    setScrollNudge((prev) => prev - INTRA_SCROLL_STEP);
  }, []);

  const handleMouseScrollDown = useCallback(() => {
    setAutoScroll(false);
    setScrollNudge((prev) => prev + INTRA_SCROLL_STEP);
  }, []);

  useMouseScroll({
    onScrollUp: handleMouseScrollUp,
    onScrollDown: handleMouseScrollDown,
  });

  const handleBrowseFeedback = useCallback(
    (input: string) => {
      if (input !== "+" && input !== "-") return false;
      const item = items[selectedIndex];
      if (item && item.kind === "final_answer") {
        submitFeedback(item.turnIndex, input === "+");
      }
      return true;
    },
    [items, selectedIndex, submitFeedback],
  );

  useInput(
    (input, key) => {
      if (input === "i" || key.tab) {
        setMode("input");
        return;
      }
      if (handleBrowseNavigation(input, key)) return;
      if (handleBrowseScroll(input, key)) return;
      if (handleBrowseFeedback(input)) return;

      if (key.return || input === " ") {
        const item = items[selectedIndex];
        if (item && isExpandable(item.kind)) {
          setExpandState((prev) => ({
            ...prev,
            [selectedIndex]: !prev[selectedIndex],
          }));
          setIntraScrollOffset(0);
        }
      }
    },
    { isActive: mode === "browse" },
  );

  useInput(
    (_input, key) => {
      if (key.escape) {
        setMode("browse");
        if (items.length > 0) {
          setSelectedIndex(items.length - 1);
        }
      }
    },
    { isActive: mode === "input" },
  );

  // Ctrl+V: paste image from clipboard
  const isPastingRef = useRef(false);
  useInput(
    (input, key) => {
      if (input === "v" && key.ctrl && !isPastingRef.current) {
        const isDisabled =
          state.connectionStatus === "connecting" ||
          state.connectionStatus === "streaming";
        if (isDisabled) return;

        isPastingRef.current = true;
        getClipboardImage()
          .then((image) => {
            if (image) {
              setPendingImages((prev) =>
                prev.length < 5 ? [...prev, image] : prev,
              );
            }
          })
          .finally(() => {
            isPastingRef.current = false;
          });
      }
      // Ctrl+U: clear pending images
      if (input === "u" && key.ctrl && pendingImages.length > 0) {
        setPendingImages([]);
      }
    },
    { isActive: mode === "input" },
  );

  useInput((input, key) => {
    if (input === "n" && key.ctrl) {
      resetChat();
      setExpandState({});
      setSelectedIndex(0);
      setAutoScroll(true);
      setIntraScrollOffset(0);
      setMode("input");
      setPendingImages([]);
    }
  });

  useInput((input, key) => {
    if (input === "x" && key.ctrl) {
      abortStreaming();
    }
  });

  useInput((input, key) => {
    if (!key.meta) return;
    if (input === "1") {
      sendQuickReply("Approve");
      return;
    }
    if (input === "2") {
      sendQuickReply("Reject");
      return;
    }
    if (input === "3") {
      sendQuickReply("Let's chat about it.");
    }
  });

  return (
    <Box flexDirection="column" height={rows} overflow="hidden">
      <ChatView
        items={items}
        expandState={expandState}
        selectedIndex={selectedIndex}
        height={chatAreaHeight}
        width={columns}
        browseMode={mode === "browse"}
        autoScrollToBottom={autoScroll && selectedIndex === items.length - 1}
        scrollNudge={scrollNudge}
        intraScrollOffset={intraScrollOffset}
      />
      {state.pendingQuestion &&
      !otherSelected &&
      (state.pendingQuestion.questions[questionIndex]?.options ?? []).length ? (
        <QuestionSelector
          key={questionIndex}
          options={
            state.pendingQuestion.questions[questionIndex]!.options ?? []
          }
          multiSelect={
            state.pendingQuestion.questions[questionIndex]!.multi_select
          }
          onSubmit={handleQuestionAnswer}
          onOtherSelected={() => setOtherSelected(true)}
          mode={mode}
          onHeightChange={setInputAreaRows}
        />
      ) : (
        <InputArea
          onSubmit={
            state.pendingQuestion ? handleQuestionAnswer : handleSendMessage
          }
          connectionStatus={state.connectionStatus}
          mode={mode}
          commands={state.pendingQuestion ? [] : commands}
          onHeightChange={setInputAreaRows}
          pendingImageCount={pendingImages.length}
        />
      )}
      {state.tasks.length > 0 && <TaskList tasks={state.tasks} />}
      <StatusBar
        connectionStatus={state.connectionStatus}
        mcpMode={config.mcpMode}
        persona={config.persona}
        chatId={state.chatId}
        tokenUsage={state.tokenUsage}
        contextUsageFraction={state.contextUsageFraction}
        mode={mode}
      />
    </Box>
  );
}
