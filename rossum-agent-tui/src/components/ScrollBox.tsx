import React, {
  useState,
  useRef,
  useLayoutEffect,
  useImperativeHandle,
  useMemo,
} from "react";
import { Box, measureElement, type DOMElement } from "ink";

export interface ScrollBoxHandle {
  /** Set absolute scroll offset (clamped to valid range). */
  scrollTo(offset: number): void;
  /** Scroll by a delta (positive = down, negative = up). */
  scrollBy(delta: number): void;
  /** Scroll to the bottom and enable sticky scroll. */
  scrollToBottom(): void;
  /** Ensure the child at `index` is visible. */
  scrollToItem(index: number, position?: "top" | "bottom" | "nearest"): void;
  /** Whether sticky-scroll (auto-pin to bottom) is active. */
  isSticky(): boolean;
  /** Explicitly set sticky state. When true, also scrolls to bottom. */
  setSticky(sticky: boolean): void;
  /** Current scroll offset in rows. */
  getScrollOffset(): number;
  /** Total content height in rows. */
  getContentHeight(): number;
  /** Get the Y offset and height of a child by index. */
  getItemBounds(index: number): { top: number; height: number } | null;
}

interface ScrollBoxProps {
  /** Viewport height in terminal rows. */
  height: number;
  children: React.ReactNode;
}

export const ScrollBox = React.forwardRef<ScrollBoxHandle, ScrollBoxProps>(
  function ScrollBox({ height, children }, ref) {
    const [scrollOffset, setScrollOffset] = useState(0);

    // Refs for imperative reads (avoid stale closures in the handle)
    const scrollOffsetRef = useRef(0);
    scrollOffsetRef.current = scrollOffset;

    const stickyRef = useRef(true);
    const contentHeightRef = useRef(0);
    const itemOffsetsRef = useRef<number[]>([]);
    const itemHeightsRef = useRef<number[]>([]);
    const itemRefsMap = useRef(new Map<number, DOMElement>());

    const childArray = useMemo(
      () => React.Children.toArray(children),
      [children],
    );

    useImperativeHandle(ref, () => {
      const maxScroll = () => Math.max(0, contentHeightRef.current - height);
      const clamp = (v: number) => Math.max(0, Math.min(v, maxScroll()));

      return {
        scrollTo(offset: number) {
          setScrollOffset(clamp(offset));
        },

        scrollBy(delta: number) {
          setScrollOffset((prev) => clamp(prev + delta));
        },

        scrollToBottom() {
          stickyRef.current = true;
          setScrollOffset(maxScroll());
        },

        scrollToItem(
          index: number,
          position: "top" | "bottom" | "nearest" = "nearest",
        ) {
          const top = itemOffsetsRef.current[index] ?? 0;
          const h = itemHeightsRef.current[index] ?? 0;
          const bottom = top + h;

          setScrollOffset((prev) => {
            let next = prev;
            if (position === "top") {
              next = top;
            } else if (position === "bottom") {
              next = bottom - height;
            } else if (h > height) {
              // Taller than viewport: only scroll if completely off-screen
              if (top > prev + height || bottom < prev) next = top;
            } else {
              if (top < prev) next = top;
              else if (bottom > prev + height) next = bottom - height;
            }
            return clamp(next);
          });
        },

        isSticky: () => stickyRef.current,

        setSticky(s: boolean) {
          stickyRef.current = s;
          if (s) setScrollOffset(maxScroll());
        },

        getScrollOffset: () => scrollOffsetRef.current,
        getContentHeight: () => contentHeightRef.current,

        getItemBounds(index: number) {
          const top = itemOffsetsRef.current[index];
          const h = itemHeightsRef.current[index];
          if (top === undefined || h === undefined) return null;
          return { top, height: h };
        },
      };
    }, [height]);

    // Measure children after each render; auto-scroll if sticky
    useLayoutEffect(() => {
      const offsets: number[] = [];
      const heights: number[] = [];
      let cumulative = 0;

      for (let i = 0; i < childArray.length; i++) {
        offsets[i] = cumulative;
        const el = itemRefsMap.current.get(i);
        const h = el ? measureElement(el).height : 1;
        heights[i] = h;
        cumulative += h;
      }

      itemOffsetsRef.current = offsets;
      itemHeightsRef.current = heights;
      contentHeightRef.current = cumulative;

      const max = Math.max(0, cumulative - height);
      if (stickyRef.current) {
        setScrollOffset((prev) => (prev !== max ? max : prev));
      } else {
        // Clamp if content shrunk
        setScrollOffset((prev) => (prev > max ? max : prev));
      }
    });

    return (
      <Box height={height} overflowY="hidden" flexDirection="column">
        <Box flexDirection="column" marginTop={-scrollOffset}>
          {childArray.map((child, index) => (
            <Box
              key={index}
              ref={(el: DOMElement | null) => {
                if (el) itemRefsMap.current.set(index, el);
                else itemRefsMap.current.delete(index);
              }}
              flexDirection="column"
            >
              {child}
            </Box>
          ))}
        </Box>
      </Box>
    );
  },
);
