from __future__ import annotations

from rossum_agent.tools.core import CAUTIOUS_APPROVAL_LABEL


def resolve_cautious_preapprovals(
    pending: set[str],
    prompt: str,
    unconsumed: set[str] | None = None,
    approved: set[str] | None = None,
) -> set[str]:
    """Resolve pre-approved writes from blocked tools, unconsumed carry-overs, and lifetime approvals.

    The front-end formats question answers as "1. <question>\\n<selected_label>".
    We check for the approval label to avoid pre-approving on "No" or "Chat" answers.

    Unconsumed pre-approvals from previous turns (where the agent asked
    questions instead of executing the write) are always carried forward.

    Lifetime-approved tools (already approved and executed in earlier turns)
    are always included — the MCP server is re-instantiated each turn,
    so approvals must persist at the service level.
    """
    result: set[str] = set()
    if approved:
        result.update(approved)
    if unconsumed:
        result.update(unconsumed)
    if pending and CAUTIOUS_APPROVAL_LABEL in prompt:
        result.update(pending)
    return result


def inject_preapproval_into_system_prompt(system_prompt: str, preapproved: set[str]) -> str:
    """Append pre-approval instructions to the system prompt.

    When writes are pre-approved, the system prompt — which the model treats
    as authoritative — must override the cautious persona's tendency to re-ask.
    Placing this in the system prompt is stronger than a user-content hint
    because it outranks the conversation history's "STOP" tool results.
    """
    if not preapproved:
        return system_prompt
    tools = ", ".join(sorted(preapproved))
    return (
        f"{system_prompt}\n\n"
        f"# Pre-approved write operations\n"
        f"The user has already approved the following write operations: {tools}. "
        "Execute them directly without asking for confirmation again. "
        "Do not call `ask_user_question` for these operations."
    )
