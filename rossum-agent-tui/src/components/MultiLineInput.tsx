import {
  useState,
  useEffect,
  useCallback,
  useImperativeHandle,
  useRef,
  forwardRef,
} from "react";
import { Box, Text, useInput, useStdin, useStdout } from "ink";

interface MultiLineInputProps {
  onSubmit: (value: string) => void;
  isActive: boolean;
  placeholder?: string;
  onChange?: (text: string) => void;
  onCursorChange?: (row: number, col: number) => void;
  onEscape?: () => void;
  onCtrlKey?: (key: string) => void;
}

export interface MultiLineInputHandle {
  setText: (text: string) => void;
}

function isArrowKey(key: {
  leftArrow: boolean;
  rightArrow: boolean;
  upArrow: boolean;
  downArrow: boolean;
}): boolean {
  return key.leftArrow || key.rightArrow || key.upArrow || key.downArrow;
}

function isModifierKey(key: {
  tab: boolean;
  ctrl: boolean;
  meta: boolean;
}): boolean {
  return key.tab || key.ctrl || key.meta;
}

// eslint-disable-next-line no-control-regex
const KITTY_CTRL_RE = /^\x1b\[(\d+);5u$/;

/** Try to handle a Kitty CSI-u sequence. Returns true if consumed. */
function handleKittySequence(
  str: string,
  handlers: {
    onNewLine: () => void;
    onEscape?: () => void;
    onCtrlKey?: (key: string) => void;
  },
): boolean {
  // Shift+Enter, Ctrl+Enter, or Alt+Enter — insert newline
  if (str === "\x1b[13;2u" || str === "\x1b[13;5u" || str === "\x1b\r") {
    handlers.onNewLine();
    return true;
  }
  // Escape (\x1b[27u)
  if (str === "\x1b[27u") {
    handlers.onEscape?.();
    return true;
  }
  // Ctrl+<key> (\x1b[<code>;5u)
  const ctrlMatch = str.match(KITTY_CTRL_RE);
  if (ctrlMatch) {
    handlers.onCtrlKey?.(String.fromCharCode(parseInt(ctrlMatch[1]!, 10)));
    return true;
  }
  return false;
}

function getLineLen(lines: string[], row: number): number {
  return (lines[row] ?? "").length;
}

export const MultiLineInput = forwardRef<
  MultiLineInputHandle,
  MultiLineInputProps
>(function MultiLineInput(
  {
    onSubmit,
    isActive,
    placeholder,
    onChange,
    onCursorChange,
    onEscape,
    onCtrlKey,
  },
  ref,
) {
  const [lines, setLines] = useState<string[]>([""]);
  const [cursorRow, setCursorRow] = useState(0);
  const [cursorCol, setCursorCol] = useState(0);
  const { stdin } = useStdin();
  const { stdout } = useStdout();

  // Refs for immediate cursor tracking. Paste handlers read these to avoid
  // stale closures when multiple stdin chunks arrive before React re-renders.
  const cursorRowRef = useRef(0);
  const cursorColRef = useRef(0);
  cursorRowRef.current = cursorRow;
  cursorColRef.current = cursorCol;

  // Notify parent when text changes via useEffect (React 18 batches setState
  // updaters, so capturing values from inside setLines is unreliable).
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const text = lines.join("\n");
  useEffect(() => {
    onChangeRef.current?.(text);
  }, [text]);

  const onCursorChangeRef = useRef(onCursorChange);
  onCursorChangeRef.current = onCursorChange;

  useEffect(() => {
    onCursorChangeRef.current?.(cursorRow, cursorCol);
  }, [cursorRow, cursorCol]);

  useImperativeHandle(
    ref,
    () => ({
      setText: (newText: string) => {
        const newLines = newText.split("\n");
        setLines(newLines);
        const lastRow = newLines.length - 1;
        const lastCol = newLines[lastRow]!.length;
        setCursorRow(lastRow);
        setCursorCol(lastCol);
        cursorRowRef.current = lastRow;
        cursorColRef.current = lastCol;
      },
    }),
    [],
  );

  const reset = useCallback(() => {
    setLines([""]);
    setCursorRow(0);
    setCursorCol(0);
    cursorRowRef.current = 0;
    cursorColRef.current = 0;
  }, []);

  const handleMultiLinePaste = useCallback((pastedLines: string[]) => {
    const row = cursorRowRef.current;
    const col = cursorColRef.current;
    setLines((prev) => {
      const before = prev.slice(0, row);
      const currentLine = prev[row] ?? "";
      const leftOfCursor = currentLine.slice(0, col);
      const rightOfCursor = currentLine.slice(col);

      const merged: string[] = [...before];
      for (let i = 0; i < pastedLines.length; i++) {
        if (i === 0) {
          merged.push(leftOfCursor + pastedLines[i]!);
        } else if (i === pastedLines.length - 1) {
          merged.push(pastedLines[i]! + rightOfCursor);
        } else {
          merged.push(pastedLines[i]!);
        }
      }
      merged.push(...prev.slice(row + 1));
      return merged;
    });
    const newRow = row + pastedLines.length - 1;
    const newCol = pastedLines[pastedLines.length - 1]!.length;
    cursorRowRef.current = newRow;
    cursorColRef.current = newCol;
    setCursorRow(newRow);
    setCursorCol(newCol);
  }, []);

  const handleSingleLinePaste = useCallback((str: string) => {
    const row = cursorRowRef.current;
    const col = cursorColRef.current;
    setLines((prev) => {
      const updated = [...prev];
      const currentLine = updated[row] ?? "";
      updated[row] = currentLine.slice(0, col) + str + currentLine.slice(col);
      return updated;
    });
    const newCol = col + str.length;
    cursorColRef.current = newCol;
    setCursorCol(newCol);
  }, []);

  const handleNewLine = useCallback(() => {
    const row = cursorRowRef.current;
    const col = cursorColRef.current;
    setLines((prev) => {
      const currentLine = prev[row] ?? "";
      const before = currentLine.slice(0, col);
      const after = currentLine.slice(col);
      const updated = [...prev];
      updated.splice(row, 1, before, after);
      return updated;
    });
    cursorRowRef.current = row + 1;
    cursorColRef.current = 0;
    setCursorRow(row + 1);
    setCursorCol(0);
  }, []);

  const handleSubmit = useCallback(() => {
    const trimmed = lines.join("\n").trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    reset();
  }, [lines, onSubmit, reset]);

  // Track when the raw stdin handler consumed an event so useInput skips it
  const consumedRef = useRef(false);

  // Enable Kitty keyboard protocol (flag 1: disambiguate escape codes) so the
  // terminal sends \x1b[13;2u for Shift+Enter instead of plain \r.
  // Terminals that don't support it silently ignore the sequence.
  useEffect(() => {
    if (!isActive || !stdout) return;
    stdout.write("\x1b[>1u");
    return () => {
      stdout.write("\x1b[<u");
    };
  }, [isActive, stdout]);

  // Raw stdin handler for paste and newline key combos that Ink can't parse.
  // Most terminals send identical \r for Enter and Shift+Enter, so useInput
  // cannot distinguish them. We intercept Kitty-protocol Shift+Enter and
  // Alt+Enter here instead.
  useEffect(() => {
    if (!isActive || !stdin) return;

    const kittyHandlers = {
      onNewLine: handleNewLine,
      onEscape,
      onCtrlKey,
    };

    const onData = (data: Buffer) => {
      let str = data.toString("utf-8");

      if (handleKittySequence(str, kittyHandlers)) {
        consumedRef.current = true;
        return;
      }

      // Strip bracketed paste markers (\x1b[200~ start, \x1b[201~ end).
      // Terminals may send these when bracketed paste mode was left enabled
      // (e.g., from a prior shell session or terminal configuration).
      // eslint-disable-next-line no-control-regex
      str = str.replace(/\x1b\[200~/g, "").replace(/\x1b\[201~/g, "");

      // Ignore empty (marker-only chunks), single-char inputs, and
      // control sequences — handled by useInput
      if (!str || str.length <= 1 || str.startsWith("\x1b")) return;

      if (str.includes("\n") || str.includes("\r")) {
        handleMultiLinePaste(str.split(/\r\n|\r|\n/));
      } else {
        handleSingleLinePaste(str);
      }
    };

    stdin.on("data", onData);
    return () => {
      stdin.off("data", onData);
    };
  }, [
    isActive,
    stdin,
    handleNewLine,
    handleMultiLinePaste,
    handleSingleLinePaste,
    onEscape,
    onCtrlKey,
  ]);

  const handleBackspace = useCallback(() => {
    if (cursorCol > 0) {
      setLines((prev) => {
        const updated = [...prev];
        const line = updated[cursorRow] ?? "";
        updated[cursorRow] =
          line.slice(0, cursorCol - 1) + line.slice(cursorCol);
        return updated;
      });
      setCursorCol((c) => c - 1);
    } else if (cursorRow > 0) {
      setLines((prev) => {
        const updated = [...prev];
        const prevLine = updated[cursorRow - 1] ?? "";
        const currentLine = updated[cursorRow] ?? "";
        const newCol = prevLine.length;
        updated.splice(cursorRow - 1, 2, prevLine + currentLine);
        setTimeout(() => setCursorCol(newCol), 0);
        return updated;
      });
      setCursorRow((r) => r - 1);
    }
  }, [cursorRow, cursorCol]);

  const handleArrowKeys = useCallback(
    (key: {
      leftArrow: boolean;
      rightArrow: boolean;
      upArrow: boolean;
      downArrow: boolean;
    }) => {
      if (key.leftArrow) {
        if (cursorCol > 0) {
          setCursorCol((c) => c - 1);
        } else if (cursorRow > 0) {
          setCursorRow((r) => r - 1);
          setCursorCol(getLineLen(lines, cursorRow - 1));
        }
      } else if (key.rightArrow) {
        if (cursorCol < getLineLen(lines, cursorRow)) {
          setCursorCol((c) => c + 1);
        } else if (cursorRow < lines.length - 1) {
          setCursorRow((r) => r + 1);
          setCursorCol(0);
        }
      } else if (key.upArrow) {
        if (cursorRow > 0) {
          setCursorRow((r) => r - 1);
          setCursorCol(Math.min(cursorCol, getLineLen(lines, cursorRow - 1)));
        }
      } else if (key.downArrow) {
        if (cursorRow < lines.length - 1) {
          setCursorRow((r) => r + 1);
          setCursorCol(Math.min(cursorCol, getLineLen(lines, cursorRow + 1)));
        }
      }
    },
    [lines, cursorRow, cursorCol],
  );

  const handleCharInput = useCallback(
    (input: string) => {
      setLines((prev) => {
        const updated = [...prev];
        const line = updated[cursorRow] ?? "";
        updated[cursorRow] =
          line.slice(0, cursorCol) + input + line.slice(cursorCol);
        return updated;
      });
      setCursorCol((c) => c + 1);
    },
    [cursorRow, cursorCol],
  );

  useInput(
    (input, key) => {
      // Skip if the raw stdin handler already consumed this event
      if (consumedRef.current) {
        consumedRef.current = false;
        return;
      }
      if (key.return) return key.shift ? handleNewLine() : handleSubmit();
      // Ctrl+J sends \n which Ink parses as name:'enter' (not 'return')
      if (input === "\n") return handleNewLine();
      if (key.backspace || key.delete) return handleBackspace();
      if (isArrowKey(key)) return handleArrowKeys(key);
      if (isModifierKey(key)) return;
      // Only insert printable characters — filter control chars (\r, \n, etc.)
      if (input.length === 1 && input.charCodeAt(0) >= 0x20)
        handleCharInput(input);
    },
    { isActive },
  );

  const isEmpty = lines.length === 1 && lines[0] === "";

  const MAX_VISIBLE_LINES = 10;
  const visibleCount = Math.min(lines.length, MAX_VISIBLE_LINES);
  const scrollOffset = Math.max(
    0,
    Math.min(
      cursorRow - MAX_VISIBLE_LINES + 1,
      lines.length - MAX_VISIBLE_LINES,
    ),
  );
  const visibleLines = lines.slice(scrollOffset, scrollOffset + visibleCount);
  const visibleWidth = Math.max((stdout?.columns ?? 80) - 4, 20);

  function truncateForDisplay(line: string): string {
    if (line.length <= visibleWidth) return line;
    if (visibleWidth <= 3) return line.slice(0, visibleWidth);
    return line.slice(0, visibleWidth - 3) + "...";
  }

  function cursorWindow(
    line: string,
    col: number,
  ): { segment: string; start: number } {
    if (line.length <= visibleWidth) {
      return { segment: line, start: 0 };
    }
    const maxStart = Math.max(0, line.length - visibleWidth);
    const preferredStart = Math.max(col - Math.floor(visibleWidth * 0.7), 0);
    const start = Math.min(preferredStart, maxStart);
    return {
      segment: line.slice(start, start + visibleWidth),
      start,
    };
  }

  return (
    <Box flexDirection="column">
      {isEmpty && placeholder ? (
        <Box>
          <Text dimColor>{placeholder}</Text>
          <Text backgroundColor="green"> </Text>
        </Box>
      ) : (
        visibleLines.map((line, visIdx) => {
          const rowIdx = scrollOffset + visIdx;
          const isCursorRow = rowIdx === cursorRow;
          if (!isCursorRow) {
            return (
              <Text key={rowIdx} wrap="truncate">
                {truncateForDisplay(line)}
              </Text>
            );
          }

          const { segment, start } = cursorWindow(line, cursorCol);
          const hasCharAtCursor = cursorCol < line.length;
          const localCursor = Math.min(
            Math.max(cursorCol - start, 0),
            segment.length,
          );
          const before = segment.slice(0, localCursor);
          const cursorChar = hasCharAtCursor ? (line[cursorCol] ?? " ") : " ";
          const after = hasCharAtCursor
            ? segment.slice(localCursor + 1)
            : segment.slice(localCursor);

          return (
            <Text key={rowIdx} wrap="truncate">
              {before}
              <Text backgroundColor="green" color="black">
                {cursorChar}
              </Text>
              {after}
            </Text>
          );
        })
      )}
      {lines.length > 1 && (
        <Text dimColor italic>
          ({lines.length} lines, showing {scrollOffset + 1}-
          {scrollOffset + visibleCount}) Shift+Enter: new line | Enter: send
        </Text>
      )}
    </Box>
  );
});
