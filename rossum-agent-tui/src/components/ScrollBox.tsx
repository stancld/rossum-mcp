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
  /** Viewport width — triggers height cache invalidation on resize. */
  width?: number;
  children: React.ReactNode;
}

/** Extra items rendered above/below the viewport for smooth scrolling. */
const CULL_BUFFER = 3;

/** Fallback height for items not yet measured. */
const DEFAULT_HEIGHT = 1;

/**
 * Compute the child index range to render, plus spacer heights for culled
 * items above and below. Returns full range when no cache exists yet
 * (first render or after width-change invalidation).
 */
function computeVisibleRange(
  childCount: number,
  scrollOffset: number,
  viewportHeight: number,
  cache: number[],
): { start: number; end: number; topSpacer: number; bottomSpacer: number } {
  if (childCount === 0) {
    return { start: 0, end: -1, topSpacer: 0, bottomSpacer: 0 };
  }

  // No cache — render everything for the initial measurement pass
  if (cache.length === 0) {
    return { start: 0, end: childCount - 1, topSpacer: 0, bottomSpacer: 0 };
  }

  // Build cumulative offsets from cache + defaults for unmeasured items
  const offsets = new Array<number>(childCount);
  const heights = new Array<number>(childCount);
  let totalHeight = 0;
  for (let i = 0; i < childCount; i++) {
    offsets[i] = totalHeight;
    heights[i] = cache[i] ?? DEFAULT_HEIGHT;
    totalHeight += heights[i]!;
  }

  const viewBottom = scrollOffset + viewportHeight;

  // First visible: first item whose bottom edge extends below scrollOffset
  let start = childCount - 1;
  for (let i = 0; i < childCount; i++) {
    if (offsets[i]! + heights[i]! > scrollOffset) {
      start = i;
      break;
    }
  }

  // Last visible: last item whose top edge is above viewBottom
  let end = start;
  for (let i = childCount - 1; i >= start; i--) {
    if (offsets[i]! < viewBottom) {
      end = i;
      break;
    }
  }

  // Always include unmeasured items (new items appended beyond cache)
  if (cache.length < childCount) {
    end = Math.max(end, childCount - 1);
  }

  // Apply buffer
  start = Math.max(0, start - CULL_BUFFER);
  end = Math.min(childCount - 1, end + CULL_BUFFER);

  const topSpacer = offsets[start]!;
  const bottomSpacer = Math.max(
    0,
    totalHeight - (offsets[end]! + heights[end]!),
  );

  return { start, end, topSpacer, bottomSpacer };
}

export const ScrollBox = React.forwardRef<ScrollBoxHandle, ScrollBoxProps>(
  function ScrollBox({ height, width, children }, ref) {
    const [scrollOffset, setScrollOffset] = useState(0);

    // Avoid stale closures in the imperative handle
    const scrollOffsetRef = useRef(0);
    scrollOffsetRef.current = scrollOffset;

    const stickyRef = useRef(true);
    const contentHeightRef = useRef(0);
    const itemOffsetsRef = useRef<number[]>([]);
    const itemHeightsRef = useRef<number[]>([]);

    // Cached heights from prior measurements — drives viewport culling.
    // Sparse entries (unmeasured) fall back to DEFAULT_HEIGHT via ??.
    const heightCacheRef = useRef<number[]>([]);
    const itemRefsMap = useRef(new Map<number, DOMElement>());

    const childArray = useMemo(
      () => React.Children.toArray(children),
      [children],
    );

    // Invalidate cache when terminal width changes (text wrapping changes heights)
    const prevWidthRef = useRef(width);
    if (width !== undefined && width !== prevWidthRef.current) {
      heightCacheRef.current = [];
      prevWidthRef.current = width;
    }

    const { start, end, topSpacer, bottomSpacer } = computeVisibleRange(
      childArray.length,
      scrollOffset,
      height,
      heightCacheRef.current,
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

    // Measure rendered children and rebuild authoritative layout data
    useLayoutEffect(() => {
      const cache = heightCacheRef.current;

      // Measure items currently in the DOM
      for (let i = start; i <= end; i++) {
        const el = itemRefsMap.current.get(i);
        if (el) {
          cache[i] = measureElement(el).height;
        }
      }

      // Trim cache if children were removed
      if (cache.length > childArray.length) {
        cache.length = childArray.length;
      }

      // Rebuild offsets from cache (measured) + defaults (unmeasured)
      const offsets: number[] = [];
      const heights: number[] = [];
      let cumulative = 0;
      for (let i = 0; i < childArray.length; i++) {
        offsets[i] = cumulative;
        const h = cache[i] ?? DEFAULT_HEIGHT;
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
          {topSpacer > 0 && <Box height={topSpacer} />}
          {childArray.slice(start, end + 1).map((child, idx) => {
            const index = start + idx;
            return (
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
            );
          })}
          {bottomSpacer > 0 && <Box height={bottomSpacer} />}
        </Box>
      </Box>
    );
  },
);
