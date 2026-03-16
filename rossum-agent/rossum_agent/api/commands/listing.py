from __future__ import annotations

from datetime import UTC

from rossum_agent.agent.skills import get_all_skills
from rossum_agent.api.commands.registry import COMMANDS, CommandContext, register_command
from rossum_agent.api.models.schemas import Persona
from rossum_agent.prompts.base_prompt import PERSONA_BEHAVIORS
from rossum_agent.tools import INTERNAL_TOOLS
from rossum_agent.tools.dynamic_tools import get_cached_category_tool_names, get_load_tool_definition

VALID_PERSONAS: tuple[Persona, ...] = tuple(Persona)

PERSONA_DESCRIPTIONS: dict[str, str] = {
    "default": "Balanced mode - acts autonomously, asks only when truly ambiguous",
    "cautious": "Plans first, asks before writes, verifies before and after changes",
}


async def handle_list_commands(ctx: CommandContext) -> str:
    lines = ["**Available commands:**", ""]
    for cmd in COMMANDS.values():
        lines.append(f"- `{cmd.name}` - {cmd.description}")
    return "\n".join(lines)


async def handle_list_commits(ctx: CommandContext) -> str:
    if ctx.commit_store is None:
        return "Commit tracking is not available (Redis not connected)."

    chat_data = ctx.chat_service.get_chat_data(user_id=ctx.user_id, chat_id=ctx.chat_id)
    if chat_data is None:
        return "Chat not found."

    commit_hashes = chat_data.metadata.config_commits
    if not commit_hashes:
        return "No configuration commits have been made in this chat yet."

    environment = ctx.credentials_api_url
    lines = ["**Configuration commits in this chat:**", ""]
    for commit_hash in commit_hashes:
        commit = ctx.commit_store.get_commit(environment, commit_hash)
        if commit is None:
            lines.append(f"- `{commit_hash}` - (expired or unavailable)")
            continue
        ts = commit.timestamp.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
        badge = " **[REVERTED]**" if commit.reverted else ""
        lines.append(f"- `{commit.hash}` ({ts}) - {commit.message}{badge} ({len(commit.changes)} changes)")
        for change in commit.changes:
            lines.append(f'  - {change.entity_type} "{change.entity_name}" [{change.operation}]')
    return "\n".join(lines)


def extract_skill_goal(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("**Goal**:"):
            return line.removeprefix("**Goal**:").strip()
    return ""


async def handle_list_skills(ctx: CommandContext) -> str:
    skills = get_all_skills()
    if not skills:
        return "No skills found."

    base_url = "https://github.com/stancld/rossum-agents/blob/master/rossum-agent/rossum_agent/skills"
    lines = [f"**Available skills ({len(skills)}):**", ""]
    for skill in sorted(skills, key=lambda skill_info: skill_info.slug):
        goal = extract_skill_goal(skill.content)
        suffix = f" - {goal}" if goal else ""
        url = f"{base_url}/{skill.slug}.md"
        lines.append(f"- [{skill.slug}]({url}){suffix}")
    return "\n".join(lines)


async def handle_list_mcp_tools(ctx: CommandContext) -> str:
    catalog = get_cached_category_tool_names()
    if catalog is None:
        return "MCP tool catalog not loaded yet. Send a message to the agent first to initialize the connection."

    total = sum(len(tools) for tools in catalog.values())
    lines = [f"**MCP tools ({total} tools in {len(catalog)} categories):**", ""]
    for category in sorted(catalog):
        tool_names = sorted(catalog[category])
        lines.append(f"**{category}** ({len(tool_names)})")
        for name in tool_names:
            lines.append(f"  - `{name}`")
        lines.append("")
    return "\n".join(lines)


async def handle_list_agent_tools(ctx: CommandContext) -> str:
    tools: list[tuple[str, str]] = []
    for tool in INTERNAL_TOOLS:
        tool_dict = tool.to_dict()
        tools.append((tool_dict["name"], tool_dict.get("description", "")))
    for tool_definition in [get_load_tool_definition()]:
        tools.append((tool_definition["name"], tool_definition.get("description", "")))

    tools.sort(key=lambda tool_info: tool_info[0])

    lines = [f"**Agent tools ({len(tools)}):**", ""]
    for name, description in tools:
        first_line = description.split("\n")[0] if description else ""
        lines.append(f"- `{name}` - {first_line}")
    return "\n".join(lines)


async def handle_persona(ctx: CommandContext) -> str:
    chat_data = ctx.chat_service.get_chat_data(user_id=ctx.user_id, chat_id=ctx.chat_id)
    if chat_data is None:
        return "Chat not found."

    if not ctx.args:
        current = chat_data.metadata.persona
        lines = [f"Current persona: **{current}**", "", "Available personas:"]
        for persona in VALID_PERSONAS:
            description = PERSONA_DESCRIPTIONS.get(persona, "")
            marker = " (active)" if persona == current else ""
            lines.append(f"- `{persona}`{marker} - {description}" if description else f"- `{persona}`{marker}")
        return "\n".join(lines)

    requested = ctx.args[0].lower()
    if requested not in VALID_PERSONAS:
        available = ", ".join(f"`{persona}`" for persona in VALID_PERSONAS)
        return f"Unknown persona `{requested}`. Available personas: {available}"

    persona = Persona(requested)
    chat_data.metadata.persona = persona
    ctx.chat_service.save_messages(
        user_id=ctx.user_id,
        chat_id=ctx.chat_id,
        messages=chat_data.messages,
        metadata=chat_data.metadata,
    )
    behavior = PERSONA_BEHAVIORS.get(persona, "")
    parts = [f"Persona switched to **{requested}**."]
    if behavior:
        parts.append(f"\n{behavior.strip()}")
    return "\n".join(parts)


register_command("/list-commands", "List all available slash commands", handle_list_commands)
register_command("/list-commits", "List configuration commits made in this chat", handle_list_commits)
register_command("/list-skills", "List available agent skills", handle_list_skills)
register_command("/list-mcp-tools", "List MCP tools by category", handle_list_mcp_tools)
register_command("/list-agent-tools", "List built-in agent tools", handle_list_agent_tools)
register_command(
    "/persona",
    "Get or switch the agent persona (e.g. `/persona cautious`)",
    handle_persona,
    argument_suggestions=[(persona, PERSONA_DESCRIPTIONS[persona]) for persona in VALID_PERSONAS],
)
