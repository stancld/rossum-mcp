import { useState, useEffect, useMemo } from "react";
import { listCommands } from "../api/client.js";
import type { CommandInfo, Config } from "../types.js";

/** Commands handled locally by the TUI (never sent to the backend). */
export const LOCAL_COMMANDS: CommandInfo[] = [
  {
    name: "/copy",
    description: "Copy the last response to clipboard",
    argument_suggestions: [],
  },
];

const LOCAL_COMMAND_NAMES = new Set(LOCAL_COMMANDS.map((c) => c.name));

const FALLBACK_COMMANDS: CommandInfo[] = [
  {
    name: "/list-commands",
    description: "List all available slash commands",
    argument_suggestions: [],
  },
  {
    name: "/list-commits",
    description: "List configuration commits made in this chat",
    argument_suggestions: [],
  },
  {
    name: "/list-skills",
    description: "List available agent skills",
    argument_suggestions: [],
  },
  {
    name: "/list-mcp-tools",
    description: "List MCP tools by category",
    argument_suggestions: [],
  },
  {
    name: "/list-agent-tools",
    description: "List built-in agent tools",
    argument_suggestions: [],
  },
  {
    name: "/persona",
    description: "Get or switch the agent persona (e.g. `/persona cautious`)",
    argument_suggestions: [
      {
        value: "default",
        description:
          "Balanced mode — acts autonomously, asks only when truly ambiguous",
      },
      {
        value: "cautious",
        description:
          "Plans first, asks before writes, verifies before and after changes",
      },
    ],
  },
];

export function useCommands(config: Config): { commands: CommandInfo[] } {
  const [serverCommands, setServerCommands] =
    useState<CommandInfo[]>(FALLBACK_COMMANDS);

  useEffect(() => {
    let cancelled = false;
    listCommands(config).then((result) => {
      if (!cancelled && result.length > 0) {
        setServerCommands(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [config]);

  const commands = useMemo(() => {
    const filtered = serverCommands.filter(
      (c) => !LOCAL_COMMAND_NAMES.has(c.name),
    );
    return [...LOCAL_COMMANDS, ...filtered];
  }, [serverCommands]);

  return { commands };
}
