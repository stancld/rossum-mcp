import React, { useMemo, useLayoutEffect } from "react";
import { Box, Text } from "ink";
import { ChatItemDisplay } from "./ChatItemDisplay.js";
import { ScrollBox, type ScrollBoxHandle } from "./ScrollBox.js";
import type { ChatItem, ExpandState } from "../types.js";

interface ChatViewProps {
  items: ChatItem[];
  expandState: ExpandState;
  selectedIndex: number;
  height: number;
  width: number;
  browseMode: boolean;
  scrollRef: React.MutableRefObject<ScrollBoxHandle | null>;
}

const ROSSUM_PATTERN = "ROSSUM";

function fillPatternSegment(
  grid: string[][],
  y: number,
  fromX: number,
  toX: number,
  seed: number,
): void {
  const width = grid[0]?.length ?? 0;
  let index = seed;

  for (let x = fromX; x <= toX; x++) {
    if (x < 0 || x >= width) {
      continue;
    }
    grid[y]![x] = ROSSUM_PATTERN[index % ROSSUM_PATTERN.length]!;
    index += 1;
  }
}

function buildRossumCircle(width: number, height: number): string[] {
  const maxCols = Math.max(width - 4, 0);
  const maxRows = Math.max(height - 2, 0);
  if (maxCols < 12 || maxRows < 6) {
    return [ROSSUM_PATTERN.repeat(2)];
  }

  const xScale = 2.2;
  const maxRadius = Math.max(
    4,
    Math.floor(Math.min((maxCols - 2) / (2 * xScale), (maxRows - 2) / 2)),
  );
  const outerRadius = Math.max(4, Math.floor(maxRadius * 0.78));
  const yStep = 0.9;
  const strokeWidth = Math.min(6, Math.max(4, Math.floor(outerRadius / 2.5)));
  const innerRadius = Math.max(1, outerRadius - strokeWidth + 1);
  let rows = Math.floor((2 * outerRadius) / yStep) + 1;
  if (rows % 2 === 0) {
    rows += 1;
  }
  let cols = Math.round(outerRadius * 2 * xScale) + 1;
  if (cols % 2 === 0) {
    cols += 1;
  }
  rows = Math.min(rows, maxRows);
  cols = Math.min(cols, maxCols);
  const centerX = (cols - 1) / 2;
  const centerY = (rows - 1) / 2;
  const grid = Array.from({ length: rows }, () => Array(cols).fill(" "));

  for (let y = 0; y < rows; y++) {
    const dy = (y - centerY) * yStep;
    const outerBand = outerRadius * outerRadius - dy * dy;
    if (outerBand < 0) {
      continue;
    }

    const outerX = Math.sqrt(outerBand) * xScale;
    const leftOuter = Math.round(centerX - outerX);
    const rightOuter = Math.round(centerX + outerX);

    const innerBand = innerRadius * innerRadius - dy * dy;
    if (innerBand <= 0) {
      fillPatternSegment(grid, y, leftOuter, rightOuter, y);
      continue;
    }

    const innerX = Math.sqrt(innerBand) * xScale;
    const leftInner = Math.round(centerX - innerX);
    const rightInner = Math.round(centerX + innerX);

    fillPatternSegment(grid, y, leftOuter, leftInner - 1, y);
    fillPatternSegment(grid, y, rightInner + 1, rightOuter, y + 3);
  }

  return grid.map((row) => row.join("").replace(/\s+$/, ""));
}

export const ChatView = React.memo(function ChatView({
  items,
  expandState,
  selectedIndex,
  height,
  width,
  browseMode,
  scrollRef,
}: ChatViewProps) {
  const emptyStateCircle = useMemo(
    () => buildRossumCircle(width, height),
    [width, height],
  );

  // Keep the selected item visible after navigation or expand/collapse.
  // Runs after ScrollBox's useLayoutEffect (child-first), so measurements
  // are already up to date.
  useLayoutEffect(() => {
    scrollRef.current?.scrollToItem(selectedIndex, "nearest");
  }, [selectedIndex, expandState, scrollRef]);

  if (items.length === 0) {
    return (
      <Box flexDirection="column" height={height} overflowY="hidden">
        <Box
          flexDirection="column"
          flexGrow={1}
          justifyContent="center"
          alignItems="center"
        >
          <Box flexDirection="column">
            {emptyStateCircle.map((line, i) => (
              <Text key={i} color="blueBright">
                {line}
              </Text>
            ))}
            <Text dimColor> </Text>
            <Text dimColor>Type a message to start.</Text>
            <Text dimColor>Use / for commands and @path to attach files.</Text>
            <Text dimColor>
              Esc: browse history, Ctrl+X: stop, Ctrl+N: new chat
            </Text>
          </Box>
        </Box>
      </Box>
    );
  }

  return (
    <ScrollBox ref={scrollRef} height={height} width={width}>
      {items.map((item, i) => (
        <ChatItemDisplay
          key={i}
          item={item}
          expanded={!!expandState[i]}
          selected={browseMode && i === selectedIndex}
        />
      ))}
    </ScrollBox>
  );
});
