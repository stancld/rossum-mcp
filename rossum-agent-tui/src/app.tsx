import path from "node:path";
import React, {
  useState,
  useCallback,
  useEffect,
  useMemo,
  useRef,
} from "react";
import { Box, Text, useInput } from "ink";
import { ChatView } from "./components/ChatView.js";
import type { ScrollBoxHandle } from "./components/ScrollBox.js";
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
import { Buffer } from "node:buffer";
import { getClipboardImage } from "./utils/clipboard.js";
import { useLocalCommands } from "./hooks/useLocalCommands.js";
import type {
  AgentQuestionItem,
  AttachmentInfo,
  Config,
  ExpandState,
  InteractionMode,
} from "./types.js";

const MAX_INLINE_LINES = 2000;

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

function splitTextFilesByLineCount(textFiles: TextAttachment[]): {
  inlineable: TextAttachment[];
  oversized: TextAttachment[];
} {
  const inlineable: TextAttachment[] = [];
  const oversized: TextAttachment[] = [];
  for (const f of textFiles) {
    const lineCount = f.content.split("\n").length;
    if (lineCount <= MAX_INLINE_LINES) {
      inlineable.push(f);
    } else {
      oversized.push(f);
    }
  }
  return { inlineable, oversized };
}

const MARKDOWN_EXTENSIONS = new Set([".md", ".markdown"]);

function textAttachmentToDocument(f: TextAttachment): DocumentAttachment {
  const ext = path.extname(f.filename).toLowerCase();
  return {
    type: "document",
    media_type: MARKDOWN_EXTENSIONS.has(ext) ? "text/markdown" : "text/plain",
    data: Buffer.from(f.content, "utf-8").toString("base64"),
    filename: f.filename,
  };
}

function buildMessageContent(
  message: string,
  inlineableFiles: TextAttachment[],
  oversizedFiles: TextAttachment[],
  errors: string[],
): string {
  let content = message.replace(/\s+/g, " ").trim();
  if (!content && inlineableFiles.length === 0 && oversizedFiles.length === 0) {
    content = "See attached files.";
  }

  if (inlineableFiles.length > 0) {
    const inlined = inlineableFiles
      .map(
        (f) =>
          `<file_content path="${f.filename}">\n${f.content}\n</file_content>`,
      )
      .join("\n\n");
    content = content ? `${content}\n\n${inlined}` : inlined;
  }

  if (oversizedFiles.length > 0) {
    const names = oversizedFiles.map((f) => f.filename).join(", ");
    content += `\n\n[Large text files attached as documents (>${MAX_INLINE_LINES} lines): ${names}]`;
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

function NotificationBar({
  notification,
}: {
  notification: { message: string; type: "success" | "error" } | null;
}) {
  if (!notification) return null;
  return (
    <Box paddingLeft={2}>
      <Text color={notification.type === "success" ? "green" : "red"}>
        {notification.message}
      </Text>
    </Box>
  );
}

interface AppProps {
  config: Config;
}

const INTRA_SCROLL_STEP = 3;

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
  const [inputAreaRows, setInputAreaRows] = useState(1);
  const [questionIndex, setQuestionIndex] = useState(0);
  const scrollRef = useRef<ScrollBoxHandle>(null);
  const [questionAnswers, setQuestionAnswers] = useState<string[]>([]);
  const [otherSelected, setOtherSelected] = useState(false);
  const [pendingImages, setPendingImages] = useState<ImageAttachment[]>([]);
  const { notification, handleLocalCommand } = useLocalCommands(
    state.completedSteps,
  );

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

  // Layout: ChatView (flex) + notification (0-1 rows) + InputArea (1+ rows) + TaskList (N rows) + StatusBar (3 rows with border)
  const taskListHeight = state.tasks.length;
  const notificationHeight = notification ? 1 : 0;
  const fixedHeight = 3 + notificationHeight + inputAreaRows + taskListHeight;
  const chatAreaHeight = Math.max(rows - fixedHeight, 1);

  // When sticky and new items arrive, keep selectedIndex on the last item
  useEffect(() => {
    if (scrollRef.current?.isSticky() && items.length > 0) {
      setSelectedIndex(items.length - 1);
    }
  }, [items.length]);

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
      if (handleLocalCommand(message)) return;

      scrollRef.current?.setSticky(true);
      setExpandState({});

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

      // Split text files: inline small ones, send large ones as documents
      const { inlineable, oversized } = splitTextFilesByLineCount(
        processed.textFiles,
      );
      const oversizedDocs = oversized.map(textAttachmentToDocument);
      const allDocuments = [...processed.documents, ...oversizedDocs].slice(
        0,
        5,
      );

      const hasAttachments =
        allImages.length > 0 ||
        allDocuments.length > 0 ||
        inlineable.length > 0;

      if (!hasAttachments) {
        sendMessage(message);
      } else {
        const content = buildMessageContent(
          message,
          inlineable,
          oversized,
          processed.errors,
        );
        const displayMessage = buildDisplayMessage(message);

        sendMessage(content, {
          displayMessage,
          images: allImages.length > 0 ? allImages : undefined,
          documents: allDocuments.length > 0 ? allDocuments : undefined,
          attachmentInfos: allInfos.length > 0 ? allInfos : undefined,
        });
      }

      setPendingImages([]);
    },
    [sendMessage, pendingImages, handleLocalCommand],
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
      scrollRef.current?.setSticky(true);
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
    const scroll = scrollRef.current;
    if (!scroll) return;

    // If current item extends below the viewport, scroll within it
    const bounds = scroll.getItemBounds(selectedIndex);
    if (bounds) {
      const viewBottom = scroll.getScrollOffset() + chatAreaHeight;
      if (bounds.top + bounds.height > viewBottom + 0.5) {
        scroll.setSticky(false);
        scroll.scrollBy(INTRA_SCROLL_STEP);
        return;
      }
    }

    if (selectedIndex >= items.length - 1) return;
    const nextIdx = selectedIndex + 1;
    setSelectedIndex(nextIdx);
    if (nextIdx === items.length - 1) scroll.setSticky(true);
  }, [selectedIndex, items.length, chatAreaHeight]);

  const handleBrowseUp = useCallback(() => {
    const scroll = scrollRef.current;
    if (!scroll) return;

    // If current item extends above the viewport, scroll within it
    const bounds = scroll.getItemBounds(selectedIndex);
    if (bounds) {
      const viewTop = scroll.getScrollOffset();
      if (bounds.top < viewTop - 0.5) {
        scroll.setSticky(false);
        scroll.scrollBy(-INTRA_SCROLL_STEP);
        return;
      }
    }

    if (selectedIndex <= 0) return;
    scroll.setSticky(false);
    const prevIdx = selectedIndex - 1;
    setSelectedIndex(prevIdx);
    // Show the bottom of the previous item (like scrolling through a document)
    scroll.scrollToItem(prevIdx, "bottom");
  }, [selectedIndex]);

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
        setSelectedIndex(Math.max(items.length - 1, 0));
        scrollRef.current?.setSticky(true);
        return true;
      }
      return false;
    },
    [handleBrowseDown, handleBrowseUp, items.length],
  );

  const handleBrowseScroll = useCallback(
    (input: string, key: { ctrl: boolean }) => {
      if (!key.ctrl) return false;
      const half = Math.max(Math.floor(chatAreaHeight / 2), 1);
      if (input === "d") {
        scrollRef.current?.setSticky(false);
        scrollRef.current?.scrollBy(half);
        return true;
      }
      if (input === "u") {
        scrollRef.current?.setSticky(false);
        scrollRef.current?.scrollBy(-half);
        return true;
      }
      return false;
    },
    [chatAreaHeight],
  );

  const handleMouseScrollUp = useCallback(() => {
    scrollRef.current?.setSticky(false);
    scrollRef.current?.scrollBy(-INTRA_SCROLL_STEP);
  }, []);

  const handleMouseScrollDown = useCallback(() => {
    scrollRef.current?.setSticky(false);
    scrollRef.current?.scrollBy(INTRA_SCROLL_STEP);
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
        }
      }
    },
    { isActive: mode === "browse" },
  );

  const handleEscapeFromInput = useCallback(() => {
    setMode("browse");
    if (items.length > 0) {
      setSelectedIndex(items.length - 1);
    }
  }, [items.length]);

  // Legacy Escape handling for terminals without Kitty protocol support.
  // Kitty-protocol Escape (\x1b[27u) is handled via onEscape prop instead.
  useInput(
    (_input, key) => {
      if (key.escape) handleEscapeFromInput();
    },
    { isActive: mode === "input" },
  );

  // Ctrl+V: paste image from clipboard
  const isPastingRef = useRef(false);
  const handlePasteImage = useCallback(() => {
    if (isPastingRef.current) return;
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
  }, [state.connectionStatus]);

  const handleNewChat = useCallback(() => {
    resetChat();
    setExpandState({});
    setSelectedIndex(0);
    scrollRef.current?.setSticky(true);
    setMode("input");
    setPendingImages([]);
  }, [resetChat]);

  // Kitty keyboard protocol encodes Ctrl+key as CSI-u sequences that Ink
  // can't parse. MultiLineInput detects these and forwards the key here.
  const handleCtrlKey = useCallback(
    (key: string) => {
      if (key === "v") handlePasteImage();
      if (key === "u" && pendingImages.length > 0) setPendingImages([]);
      if (key === "n") handleNewChat();
      if (key === "x") abortStreaming();
    },
    [handlePasteImage, pendingImages.length, handleNewChat, abortStreaming],
  );

  useInput(
    (input, key) => {
      if (input === "v" && key.ctrl) handlePasteImage();
      if (input === "u" && key.ctrl && pendingImages.length > 0) {
        setPendingImages([]);
      }
    },
    { isActive: mode === "input" },
  );

  useInput((input, key) => {
    if (input === "n" && key.ctrl) handleNewChat();
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
        scrollRef={scrollRef}
      />
      <NotificationBar notification={notification} />
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
          onEscape={handleEscapeFromInput}
          onCtrlKey={handleCtrlKey}
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
