---
name: ink-tui-best-practices
description: Best practices for building terminal UIs with Ink (React for CLI), TypeScript, and SSE streaming. Use when writing, reviewing, or refactoring Ink/React TUI code — especially AI chat interfaces with streaming, tool calls, and keyboard navigation.
---

# Ink TUI Best Practices

Comprehensive guide for building high-quality terminal user interfaces with Ink v5, React 18, and TypeScript. Covers layout, streaming, performance, accessibility, and AI chat UI patterns.

## When to Apply

Reference these guidelines when:
- Writing or reviewing Ink/React terminal UI components
- Implementing SSE streaming or real-time data display
- Designing keyboard navigation and focus management
- Optimizing TUI rendering performance
- Building AI chat interfaces (tool calls, thinking, streaming responses)

---

## 1. Ink Fundamentals

### Layout Rules

| Rule | Detail |
|------|--------|
| All text in `<Text>` | Raw strings inside `<Box>` throw errors |
| `<Box>` = flex container | Every `<Box>` is `display: flex` by default (Yoga layout engine) |
| `<Text>` contains only text | Never nest `<Box>` inside `<Text>` |
| Default direction | `flexDirection="row"` — use `"column"` for vertical stacking |
| Percentage widths | `<Box width="70%">` works for fluid layouts |
| No native scrolling | `overflow="hidden"` clips but doesn't scroll — implement virtual windowing manually |

### Layout Patterns

```tsx
// Vertical stack with spacing
<Box flexDirection="column" gap={1} padding={1}>
  <Text>Item 1</Text>
  <Text>Item 2</Text>
</Box>

// Horizontal with space distribution
<Box justifyContent="space-between" width="100%">
  <Text>Left</Text>
  <Spacer />
  <Text>Right</Text>
</Box>

// Fixed footer with flexible content
<Box flexDirection="column" height={rows}>
  <Box flexGrow={1} flexDirection="column" overflow="hidden">
    {/* Scrollable content */}
  </Box>
  <Box height={3} borderStyle="single">
    <Text>Status bar</Text>
  </Box>
</Box>
```

### Text Wrapping

`<Text wrap="truncate">` prevents long text from breaking layouts. Options: `"wrap"` (default), `"truncate"`, `"truncate-start"`, `"truncate-middle"`, `"truncate-end"`.

---

## 2. Hooks

### useInput — Keyboard Handling

```tsx
useInput((input, key) => {
  if (key.return) handleSubmit();
  if (key.escape) handleCancel();
  if (input === "q") exit();
  if (key.ctrl && input === "d") scrollDown();
}, { isActive: isFocused }); // Gate handler with isActive
```

Key object properties: `upArrow`, `downArrow`, `leftArrow`, `rightArrow`, `return`, `escape`, `tab`, `backspace`, `delete`, `ctrl`, `shift`, `meta`, `pageUp`, `pageDown`, `home`, `end`.

### useApp — Exit Control

```tsx
const { exit } = useApp();
exit();              // Clean exit
exit(new Error());   // Exit with error
```

### useFocus + useFocusManager

```tsx
const { isFocused } = useFocus({ autoFocus: true, id: "input-panel" });
const { focusNext, focusPrevious, focus } = useFocusManager();
// Tab cycles focus; programmatic control via focus("panel-id")
```

### Terminal Dimensions

```tsx
const { columns, rows } = useWindowSize();
// Or: const { stdout } = useStdout(); stdout.rows / stdout.columns
```

Always provide fallback dimensions: `stdout?.rows ?? 24`.

---

## 3. Performance

### Critical Rules

| Priority | Rule | Why |
|----------|------|-----|
| 1 | Viewport-constrained rendering | Only render visible items — never the entire scrollback. O(viewport) not O(total). |
| 2 | Cache finalized content | Re-render only the currently streaming block; all completed blocks use cached output. |
| 3 | Throttle streaming renders | 30 FPS is sufficient for streaming text. Ink's default is 30 FPS (`maxFps`). |
| 4 | `useMemo` for expensive derivations | Transform state → renderable items only when state changes. |
| 5 | `useCallback` for handler props | Prevents child re-renders when parent state changes. |
| 6 | Functional state updates | Always `setState(prev => ...)` during streaming — React 18 batches within async contexts. |
| 7 | Limit rendered nodes | Never render thousands of `<Text>` nodes. Slice to viewport + small buffer. |
| 8 | No `console.log` during render | Corrupts Ink layout. Use `patchConsole: true` (default) to redirect above UI. |

### Virtual Scrolling Pattern

```tsx
const visibleItems = items.slice(scrollOffset, scrollOffset + viewportHeight);

<Box flexDirection="column" overflow="hidden" height={viewportHeight}>
  {visibleItems.map(item => <Text key={item.id}>{item.text}</Text>)}
</Box>
```

### Static Component for Immutable Content

`<Static>` permanently renders items above the dynamic UI. Items are never re-rendered — ideal for completed messages/logs.

```tsx
<Static items={completedLogs}>
  {(log) => <Text key={log.id}>{log.message}</Text>}
</Static>
<Box>{/* Dynamic UI below */}</Box>
```

Caveat: Items in `<Static>` cannot be updated after rendering. Use only for truly immutable output.

### Long Session Memory Management

- Cap scrollback buffer size
- LRU eviction for cached renders of off-screen content
- Object pooling over continuous allocation
- Periodic cleanup of finalized streaming buffers

Cautionary tale: OpenCode hit 6.9GB memory and 100% CPU after 530+ messages because the renderer recalculated virtual lines for ALL content on every token arrival.

---

## 4. Render Options (Ink v5)

```tsx
render(<App />, {
  exitOnCtrlC: false,          // Handle Ctrl+C yourself for graceful cleanup
  patchConsole: true,           // Redirect console.* above UI (default)
  maxFps: 30,                  // Frame rate cap
  incrementalRendering: true,   // Only redraw changed lines
  concurrent: true,             // Enable React concurrent mode
  alternateScreen: true,        // Use alternate terminal buffer
});
```

---

## 5. SSE Streaming Architecture

### Event Reducer Pattern

Centralize all event handling in a pure function:

```tsx
function reduceEvent(prev: ChatState, event: SSEEvent): ChatState {
  switch (event.event) {
    case "step": return handleStepEvent(prev, event.data);
    case "done": return handleDoneEvent(prev, event.data);
    // ...
  }
}
```

### Streaming Lifecycle

| Behavior | Detail |
|----------|--------|
| `is_streaming: true` | Step in progress; may be replaced by updated events with same step_number/type |
| `is_streaming: false` | Step finalized; safe to commit to history |
| Finalization guarantee | Every streaming step is eventually followed by a finalized version |
| Type correction | Finalized event may change the step type (e.g., `final_answer` → `intermediate` when tool calls arrive) |

### AbortController for Cancellation

```tsx
const abortRef = useRef<AbortController | null>(null);
// On send:
abortRef.current?.abort();
const controller = new AbortController();
abortRef.current = controller;
```

### State Separation

Maintain `currentStreaming` (mutable, in-progress) separately from `completedSteps` (immutable, finalized). When a streaming step finalizes, promote it to completed. Derive display items via `useMemo` from both.

---

## 6. AI Chat UI Patterns

### Streaming Response Display

| Pattern | Implementation |
|---------|----------------|
| Token-by-token | Stream text as it arrives, re-render active block only |
| Auto-scroll | Keep new content visible, but stop if user scrolled up manually |
| Disable input during stream | Prevent overlapping submissions; track processing state |
| Thinking indicator | Spinner + contextual text ("Thinking...", "Calling list_users...") |

### Tool Call Display

| Pattern | Implementation |
|---------|----------------|
| Two-phase | Show `tool_start` immediately, then `tool_result` when complete |
| Collapsible | Collapsed: tool name + args summary + status icon + result preview. Expanded: full details |
| Progress | Spinner with tool name during execution; sub-agent progress inline |
| Pairing | Match tool_start with tool_result by step_number or call_id |
| Grouping | 3+ consecutive identical tool types → collapsed group |

### Thinking/Reasoning Display

- Dim or italic text, collapsed by default, expandable
- Stream separately so users can watch or ignore
- Visually differentiate from final output

### Markdown in Terminals

| Element | Rendering |
|---------|-----------|
| Code blocks | Syntax-highlighted, bordered/backgrounded, language label |
| Headers | Bold, possibly with horizontal rule |
| Lists | Indented with bullet/number markers |
| Links | Show URL (OSC 8 hyperlinks for modern terminals) |
| Tables | Box-drawing characters for alignment |
| Inline code | Background highlighting or distinct color |

---

## 7. Keyboard-First Design

### Principles

| Principle | Detail |
|-----------|--------|
| Every feature keyboard-accessible | Mouse enhances but never replaces |
| Familiar bindings | Arrows for nav, Tab for focus, Enter for action, Escape for back |
| Vim-style optional | j/k for scrolling, G for jump-to-end |
| Contextual hints | Show available keybindings for current mode, not all at once |
| Graceful Ctrl+C | Disable `exitOnCtrlC`, handle cleanup yourself |

### Multi-Mode Input

Design explicit modes (input/browse) with clear visual indicators of which mode is active. Route keyboard events based on current mode at the top-level component.

---

## 8. Color and Styling

### Design in Layers

1. **Monochrome** — interface must be usable with no color
2. **16 ANSI colors** — semantic color coding for readability
3. **256/TrueColor** — aesthetic enhancement

### Rules

| Rule | Detail |
|------|--------|
| Respect `NO_COLOR` | Disable all color when env var is set |
| Never rely on exact hues | Terminal themes vary wildly |
| Use `dimColor` | De-emphasize metadata, timestamps, secondary info |
| Use `bold` | Emphasis for headings, selections, active elements |
| Use `inverse` | Highlight current selection in lists |
| Semantic colors | Green=success, Red=error, Yellow=warning |

Ink supports: named colors, hex (`"#005cc5"`), RGB (`"rgb(232, 131, 136)"`).

---

## 9. Unicode and Cross-Platform

### Safe Characters

Box-drawing characters, standard Latin/Greek/Cyrillic, math symbols, basic geometric shapes (bullets, arrows, triangles), currency symbols.

### Problematic

Emoji rendering varies wildly across terminals. Most terminals don't handle emoji width correctly. Prefer standard Unicode symbols and provide ASCII fallbacks.

| Instead of | Use |
|------------|-----|
| Green checkmark emoji | `✓` or `[ok]` |
| Red X emoji | `✗` or `[fail]` |
| Spinner emoji | ASCII spinner (`|/-\`) |

### Terminal Quirks

| Environment | Issue |
|-------------|-------|
| tmux/screen | May intercept/modify color capabilities |
| CI | No ANSI for overwriting — detect via `CI` env var |
| Windows Console | Default charset isn't UTF-8 (Windows Terminal is fine) |
| SSH | May have reduced capabilities |

---

## 10. @inkjs/ui Components

| Component | Purpose | Key Pattern |
|-----------|---------|-------------|
| `TextInput` | Single-line input | Uncontrolled — use `onChange`/`onSubmit`, no `value` prop |
| `ConfirmInput` | Y/n confirmation | Simple boolean result |
| `Select` | Single-choice list | `options: Array<{label, value}>`, fires `onChange(value)` |
| `MultiSelect` | Multi-choice | Returns array of selected values |
| `Spinner` | Loading animation | Show during async operations |
| `ProgressBar` | Progress indicator | 0-100 range |
| `Badge` | Status label | Colored by variant |
| `StatusMessage` | Status with icon | Variants: success/error/warning/info |
| `Alert` | High-visibility notice | For errors, confirmations |

Theming: All components customizable via `extendTheme` + `ThemeProvider`.

---

## 11. Architecture Patterns

### File Organization

```
src/
  index.tsx          # Entry point, CLI arg parsing
  app.tsx            # Root component, layout, input routing
  types.ts           # All TypeScript types (centralized)
  api/               # API client functions
  components/        # React components (presentational)
  hooks/             # Custom hooks (business logic + state)
  utils/             # Pure transformation functions
```

### Separation of Concerns

| Layer | Responsibility |
|-------|---------------|
| Hooks | State management, API calls, streaming, event handling |
| Components | Purely presentational, receives data via props |
| Utils | Pure functions: state → display items, formatting, serialization |
| Root App | Orchestrator: consumes hooks, derives data, distributes to children |

### Type-Safe Discriminated Unions

```tsx
type ChatItem =
  | { kind: "user_message"; text: string }
  | { kind: "tool_call"; stepNumber: number; step: CompletedStep }
  | { kind: "final_answer"; content: string };

// Exhaustive handling via switch
function renderItem(item: ChatItem) {
  switch (item.kind) {
    case "user_message": return <Text>{item.text}</Text>;
    case "tool_call": return <ToolCall step={item.step} />;
    case "final_answer": return <Text>{item.content}</Text>;
  }
}
```

### Explicit State Phases

```tsx
type AppPhase = "idle" | "connecting" | "streaming" | "awaiting_question" | "error";
```

Model UI flows as explicit state machines to prevent impossible states.

---

## 12. Testing

Use `ink-testing-library`:

```tsx
import { render } from "ink-testing-library";

const { lastFrame, stdin } = render(<Counter count={0} />);
expect(lastFrame()).toContain("Count: 0");

// Simulate input
stdin.write("q");

// Rerender with new props
rerender(<Counter count={1} />);
expect(lastFrame()).toContain("Count: 1");
```

For async/concurrent rendering, wrap updates in `act()`.

---

## 13. TUI Design Principles

### Progressive Disclosure

| Layer | Content | Example |
|-------|---------|---------|
| Always visible | Essential state, active task | Final answer, current status |
| On demand | Detailed info, expandable | Tool call arguments, thinking blocks |
| Explicit request | Debug, raw data | Full error traces, token counts |

### Transparency Over Magic

Show what the AI agent is doing. Display tool calls with arguments. Users trust tools that explain themselves. Lazygit's most popular feature: showing the underlying git commands being executed.

### State-Action-State Cycle

After every action, immediately reflect the new state. This is a TUI's fundamental advantage over a CLI — no manual state querying.

### Responsive Design

Use `useWindowSize()` and adapt layouts to terminal dimensions. Recalculate viewport heights on resize. Use percentage-based widths and `flexGrow` for fluid layouts.

---

## Sources

- [Ink GitHub](https://github.com/vadimdemedes/ink) — Official docs and API reference
- [@inkjs/ui](https://github.com/vadimdemedes/ink-ui) — Component library
- [ink-testing-library](https://github.com/vadimdemedes/ink-testing-library)
- [clig.dev](https://clig.dev/) — Command Line Interface Guidelines
- [Lazygit 5 Years On](https://jesseduffield.com/Lazygit-5-Years-On/) — TUI design lessons
- [OpenCode Issue #6172](https://github.com/anomalyco/opencode/issues/6172) — Performance case study
- [Charm Design Philosophy](https://charm.land/blog/the-next-generation) — Modern TUI aesthetics
- [patterns.dev AI UI Patterns](https://www.patterns.dev/react/ai-ui-patterns) — AI chat interface patterns
- [The Renaissance of the Command Line](https://www.dlvhdr.me/posts/the-renaissance-of-the-command-line)
- [Terminal Interfaces — brandur.org](https://brandur.org/interfaces)
