"""Tools for analyzing and visualizing Rossum hook dependencies and workflow trees."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from smolagents import tool


@tool
def analyze_hook_dependencies(hooks_json: str) -> str:
    """Analyze hook dependencies from a list of hooks and generate a dependency tree.

    This tool helps understand the workflow and execution order of hooks in a Rossum queue
    by analyzing their trigger events, types, and relationships.

    Args:
        hooks_json: JSON string containing hooks data from list_hooks MCP tool.
            Expected format: {"count": N, "results": [{"id": ..., "name": ..., "events": [...], ...}]}

    Returns:
        JSON string containing dependency analysis with:
        - execution_phases: Hooks grouped by trigger event
        - dependency_tree: Mermaid diagram representation
        - hook_details: Detailed information about each hook
        - workflow_summary: Overall workflow description

    Example:
        hooks_data = mcp.list_hooks(queue_id=12345)
        analysis = analyze_hook_dependencies(hooks_data)
        print(analysis)
    """
    try:
        # Parse input JSON
        hooks_data = json.loads(hooks_json)
        hooks = hooks_data.get("results", [])

        if not hooks:
            return json.dumps({"error": "No hooks found in the input data"})

        # Group hooks by trigger events
        event_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for hook in hooks:
            if not hook.get("active", True):
                continue  # Skip inactive hooks
            events = hook.get("events", [])
            for event in events:
                event_groups[event].append(
                    {
                        "id": hook.get("id"),
                        "name": hook.get("name"),
                        "type": hook.get("type"),
                        "queues": hook.get("queues", []),
                        "config": hook.get("config", {}),
                        "extension_source": hook.get("extension_source"),
                    }
                )

        # Define event execution order
        event_order = [
            "annotation_status.importing",
            "annotation_content.initialize",
            "annotation_content.started",
            "annotation_content.updated",
            "annotation_status.to_review",
            "annotation_status.changed",
            "annotation_content.confirm",
            "annotation_content.export",
            "annotation_status.exporting",
            "annotation_status.exported",
            "datapoint_value",
        ]

        # Build execution phases
        execution_phases = []
        for event in event_order:
            if event in event_groups:
                execution_phases.append(
                    {
                        "event": event,
                        "description": _get_event_description(event),
                        "hooks": event_groups[event],
                    }
                )

        # Add any additional events not in the standard order
        for event in sorted(event_groups.keys()):
            if event not in event_order:
                execution_phases.append(
                    {
                        "event": event,
                        "description": "Custom or specialized event",
                        "hooks": event_groups[event],
                    }
                )

        # Generate visual dependency tree (Mermaid diagram)
        dependency_tree = _generate_mermaid_diagram(execution_phases)

        # Generate workflow summary
        workflow_summary = _generate_workflow_summary(hooks, execution_phases)

        # Compile hook details
        hook_details = []
        for hook in hooks:
            hook_details.append(
                {
                    "id": hook.get("id"),
                    "name": hook.get("name"),
                    "type": hook.get("type"),
                    "active": hook.get("active", True),
                    "events": hook.get("events", []),
                    "queues": hook.get("queues", []),
                    "has_code": bool(hook.get("extension_source") or hook.get("config", {}).get("code")),
                }
            )

        result = {
            "total_hooks": len(hooks),
            "active_hooks": sum(1 for h in hooks if h.get("active", True)),
            "execution_phases": execution_phases,
            "dependency_tree": dependency_tree,
            "workflow_summary": workflow_summary,
            "hook_details": hook_details,
        }

        return json.dumps(result, indent=2)

    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON input: {e}"})
    except Exception as e:
        return json.dumps({"error": f"Analysis failed: {e}"})


@tool
def visualize_hook_tree(hooks_json: str) -> str:
    """Generate a Mermaid diagram of hook execution flow.

    Creates a visual Mermaid diagram showing how hooks are triggered
    throughout the document lifecycle in a Rossum queue.

    Args:
        hooks_json: JSON string containing hooks data from list_hooks MCP tool

    Returns:
        String containing Mermaid diagram syntax for rendering

    Example:
        hooks_data = mcp.list_hooks(queue_id=12345)
        tree = visualize_hook_tree(hooks_data)
        print(tree)
    """
    try:
        # First get the dependency analysis
        analysis = json.loads(analyze_hook_dependencies(hooks_json))

        if "error" in analysis:
            return analysis["error"]  # type: ignore[no-any-return]

        execution_phases = analysis["execution_phases"]
        return _generate_mermaid_diagram(execution_phases)

    except Exception as e:
        return f"Error generating tree visualization: {e}"


def _get_event_description(event: str) -> str:
    """Get human-readable description for a trigger event."""
    descriptions = {
        "annotation_status.importing": "Document is being imported into the system",
        "annotation_content.initialize": "Initial setup when annotation is first created",
        "annotation_content.started": "User starts working on the annotation",
        "annotation_content.updated": "Any field value or content is modified",
        "annotation_status.to_review": "Document moves to review state",
        "annotation_status.changed": "Annotation status changes to any state",
        "annotation_content.confirm": "User confirms the annotation",
        "annotation_content.export": "Annotation is being exported",
        "annotation_status.exporting": "Export process is in progress",
        "annotation_status.exported": "Document has been successfully exported",
        "datapoint_value": "Individual field value is modified",
    }
    return descriptions.get(event, "Custom trigger event")


def _generate_mermaid_diagram(execution_phases: list[dict[str, Any]]) -> str:
    """Generate Mermaid diagram syntax with color-coded hook types.

    Hook types are visually differentiated:
    - function: Blue rounded rectangle
    - webhook: Green hexagon
    - serverless_function: Purple rounded rectangle
    - email_notification: Orange rectangle
    - Other types: Gray rounded rectangle

    For large workflows (>20 total hooks), generates multiple diagrams:
    - High-level overview showing event flow with hook counts
    - Separate detailed diagram for each event

    For smaller workflows, renders as a single flow diagram.

    The output includes both the visual diagram and detailed hook information
    with proper anchor IDs so that clickable nodes navigate correctly.
    """
    # Count total hooks
    total_hooks = sum(len(phase["hooks"]) for phase in execution_phases)

    # Generate the diagram
    if total_hooks > 20:
        diagram = _generate_multi_tree_diagrams(execution_phases)
    else:
        clusters = _detect_workflow_clusters(execution_phases)
        if len(clusters) == 1:
            diagram = _generate_single_mermaid_flow(execution_phases)
        else:
            diagram = _generate_multi_cluster_mermaid(clusters)

    # Add detailed hook information with proper anchor IDs
    hook_details = _generate_hook_details_section(execution_phases)

    return f"{diagram}\n\n{hook_details}"


def _generate_multi_tree_diagrams(execution_phases: list[dict[str, Any]]) -> str:
    """Generate multiple diagrams for large workflows.

    Returns:
    - High-level overview with event flow and hook counts
    - Separate detailed diagram for each event
    """
    sections = []

    # 1. High-level overview
    sections.append("# Hook Dependency Overview\n")
    sections.append("## High-Level Workflow\n")
    sections.append(_generate_overview_diagram(execution_phases))
    sections.append("\n")

    # 2. Detailed per-event diagrams
    sections.append("## Detailed Hook Breakdown\n")
    for phase in execution_phases:
        event_name = phase["event"]
        hook_count = len(phase["hooks"])
        sections.append(f"### Event: {event_name} ({hook_count} hooks)\n")
        sections.append(f"*{phase['description']}*\n\n")
        sections.append(_generate_event_detail_diagram(phase))
        sections.append("\n")

    return "\n".join(sections)


def _generate_overview_diagram(execution_phases: list[dict[str, Any]]) -> str:
    """Generate high-level overview showing event flow with hook counts."""
    lines = ["```mermaid", "graph TD", "    Start[Document Upload]"]

    prev_node = "Start"
    for i, phase in enumerate(execution_phases, 1):
        event_node = f"Event{i}"
        event_label = phase["event"].replace(".", "_")

        # Count hooks by type
        hook_counts = defaultdict(int)
        for hook in phase["hooks"]:
            hook_type = hook.get("type", "unknown")
            hook_counts[hook_type] += 1

        # Build summary label
        total = len(phase["hooks"])
        if total == 0:
            count_text = "no hooks"
        else:
            type_parts = [f"{count} {htype}" for htype, count in sorted(hook_counts.items())]
            count_text = f"{total} hooks: {', '.join(type_parts)}"

        lines.append(f'    {prev_node} --> {event_node}["{event_label}<br/>{count_text}"]')

        # Style event nodes differently
        lines.append(f"    style {event_node} fill:#E8F4F8,stroke:#4A90E2,stroke-width:2px")

        prev_node = event_node

    lines.append(f"    {prev_node} --> End[Complete]")
    lines.append("    style End fill:#D4EDDA,stroke:#28A745,stroke-width:2px")
    lines.append("```")

    return "\n".join(lines)


def _generate_event_detail_diagram(phase: dict[str, Any]) -> str:
    """Generate detailed diagram for a single event showing all its hooks."""
    event_name = phase["event"]
    hooks = phase["hooks"]

    if not hooks:
        return "*No hooks configured for this event*\n"

    lines = ["```mermaid", "graph TD"]

    # Event node as starting point
    event_node = "EventTrigger"
    event_label = event_name.replace(".", "_")
    lines.append(f'    {event_node}["{event_label}"]')
    lines.append(f"    style {event_node} fill:#E8F4F8,stroke:#4A90E2,stroke-width:2px")
    lines.append("")

    # Add all hooks
    for i, hook in enumerate(hooks, 1):
        hook_node = f"Hook{i}"
        hook_lines = _generate_hook_node(event_node, hook_node, hook, indent="    ")
        lines.extend(hook_lines)

    lines.append("```")

    return "\n".join(lines)


def _detect_workflow_clusters(execution_phases: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Detect groups of related events (clusters) in the workflow.

    Events are considered related if they are consecutive in the standard lifecycle.
    A gap of 2+ events in the standard order creates a new cluster.
    """
    if not execution_phases:
        return []

    # Standard event order for reference
    event_order = [
        "annotation_status.importing",
        "annotation_content.initialize",
        "annotation_content.started",
        "annotation_content.updated",
        "annotation_status.to_review",
        "annotation_status.changed",
        "annotation_content.confirm",
        "annotation_content.export",
        "annotation_status.exporting",
        "annotation_status.exported",
        "datapoint_value",
    ]

    # Get positions of each event in the standard order
    phase_positions = []
    for phase in execution_phases:
        event = phase["event"]
        if event in event_order:
            phase_positions.append((event_order.index(event), phase))
        else:
            # Custom events get placed at the end
            phase_positions.append((len(event_order), phase))

    # Sort by position
    phase_positions.sort(key=lambda x: x[0])

    # Detect clusters based on gaps
    clusters: list[list[dict[str, Any]]] = []
    current_cluster: list[dict[str, Any]] = []
    prev_position = -1

    for position, phase in phase_positions:
        # If there's a gap of 2+ positions, start a new cluster
        if prev_position != -1 and position - prev_position > 2:
            if current_cluster:
                clusters.append(current_cluster)
            current_cluster = [phase]
        else:
            current_cluster.append(phase)
        prev_position = position

    # Add the last cluster
    if current_cluster:
        clusters.append(current_cluster)

    return clusters


def _generate_single_mermaid_flow(execution_phases: list[dict[str, Any]]) -> str:
    """Generate a single Mermaid flow diagram."""
    lines = ["```mermaid", "graph TD", "    Start[Document Upload]"]

    prev_node = "Start"
    hook_counter = 1

    for node_counter, phase in enumerate(execution_phases, start=1):
        # Create event node
        event_node = f"Event{node_counter}"
        event_label = phase["event"].replace(".", "_")
        lines.append(f"    {prev_node} --> {event_node}[{event_label}]")

        # Add hooks for this event
        for hook in phase["hooks"]:
            hook_node = f"Hook{hook_counter}"
            hook_lines = _generate_hook_node(event_node, hook_node, hook)
            lines.extend(hook_lines)
            hook_counter += 1

        prev_node = event_node

    lines.append(f"    {prev_node} --> End[Complete]")
    lines.append("```")

    return "\n".join(lines)


def _generate_multi_cluster_mermaid(clusters: list[list[dict[str, Any]]]) -> str:
    """Generate multiple Mermaid subgraphs for unrelated workflow clusters."""
    all_lines = ["```mermaid", "graph TD"]

    hook_counter = 1

    for cluster_idx, cluster in enumerate(clusters, 1):
        # Create subgraph for this cluster
        cluster_name = f"cluster{cluster_idx}"
        cluster_label = _get_cluster_label(cluster)

        all_lines.append(f'    subgraph {cluster_name}["{cluster_label}"]')

        # Generate flow for this cluster
        start_node = f"Start{cluster_idx}"
        all_lines.append(f"        {start_node}[Start]")

        prev_node = start_node

        for node_counter, phase in enumerate(cluster, start=1):
            event_node = f"Event{cluster_idx}_{node_counter}"
            event_label = phase["event"].replace(".", "_")
            all_lines.append(f"        {prev_node} --> {event_node}[{event_label}]")

            # Add hooks for this event
            for hook in phase["hooks"]:
                hook_node = f"Hook{hook_counter}"
                hook_lines = _generate_hook_node(event_node, hook_node, hook, indent="        ")
                all_lines.extend(hook_lines)
                hook_counter += 1

            prev_node = event_node

        end_node = f"End{cluster_idx}"
        all_lines.append(f"        {prev_node} --> {end_node}[Complete]")
        all_lines.append("    end")
        all_lines.append("")

    all_lines.append("```")
    return "\n".join(all_lines)


def _get_cluster_label(cluster: list[dict[str, Any]]) -> str:
    """Generate a descriptive label for a workflow cluster."""
    if not cluster:
        return "Workflow"

    first_event = cluster[0]["event"]
    last_event = cluster[-1]["event"]

    # Simplify event names for labels
    def simplify(event: str) -> str:
        return event.replace("annotation_", "").replace("_", " ").title()

    if len(cluster) == 1:
        return f"{simplify(first_event)}"
    return f"{simplify(first_event)} → {simplify(last_event)}"


def _wrap_text(text: str, max_length: int = 30) -> str:
    """Wrap text to fit in Mermaid diagram boxes using <br/> tags.

    Args:
        text: Text to wrap
        max_length: Maximum length per line before wrapping

    Returns:
        Text with <br/> tags inserted for line breaks
    """
    if len(text) <= max_length:
        return text

    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        word_length = len(word)
        # Add space length if not first word on line
        space_length = 1 if current_line else 0

        if current_length + space_length + word_length <= max_length:
            current_line.append(word)
            current_length += space_length + word_length
        else:
            # Start new line
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = word_length

    # Add remaining words
    if current_line:
        lines.append(" ".join(current_line))

    return "<br/>".join(lines)


def _generate_hook_node(parent_node: str, hook_node: str, hook: dict[str, Any], indent: str = "    ") -> list[str]:
    """Generate Mermaid lines for a hook node with appropriate styling.

    Returns a list of lines to be added to the diagram.
    """
    lines = []
    hook_type = hook.get("type", "unknown")
    # Escape parentheses and special characters in hook name
    hook_name = hook["name"].replace('"', "'")
    # Wrap the hook name to fit in diagram boxes
    wrapped_name = _wrap_text(hook_name, max_length=30)
    hook_label = f"{wrapped_name}<br/>[{hook_type}]"

    # Define shape and style based on hook type
    if hook_type == "function":
        # Blue rounded rectangle for Python functions
        lines.append(f'{indent}{parent_node} --> {hook_node}["{hook_label}"]')
        lines.append(f"{indent}style {hook_node} fill:#4A90E2,stroke:#2E5C8A,color:#fff")
    elif hook_type == "webhook":
        # Green hexagon for webhooks
        lines.append(f'{indent}{parent_node} --> {hook_node}{{{{"{hook_label}"}}}}')
        lines.append(f"{indent}style {hook_node} fill:#50C878,stroke:#2E7D4E,color:#fff")
    elif hook_type == "serverless_function":
        # Purple rounded rectangle for serverless
        lines.append(f'{indent}{parent_node} --> {hook_node}["{hook_label}"]')
        lines.append(f"{indent}style {hook_node} fill:#9B59B6,stroke:#6C3483,color:#fff")
    elif hook_type == "email_notification":
        # Orange rectangle for emails
        lines.append(f'{indent}{parent_node} --> {hook_node}["{hook_label}"]')
        lines.append(f"{indent}style {hook_node} fill:#FF8C42,stroke:#CC6F35,color:#fff")
    else:
        # Gray rounded rectangle for unknown types
        lines.append(f'{indent}{parent_node} --> {hook_node}["{hook_label}"]')
        lines.append(f"{indent}style {hook_node} fill:#95A5A6,stroke:#7F8C8D,color:#fff")

    return lines


def _generate_hook_details_section(execution_phases: list[dict[str, Any]]) -> str:
    """Generate detailed hook information section with proper anchor IDs.

    This creates markdown sections for each hook that can be linked to from
    the Mermaid diagram nodes.
    """
    lines = ["---", "", "## Hook Details", ""]

    hook_counter = 1
    for phase in execution_phases:
        for hook in phase["hooks"]:
            # Create anchor ID matching the Mermaid node ID
            hook_node_id = f"hook{hook_counter}"
            hook_name = hook.get("name", "Unknown")
            hook_type = hook.get("type", "unknown")
            hook_id = hook.get("id", "N/A")

            # Add heading with anchor
            lines.append(f'<a id="{hook_node_id}"></a>')
            lines.append(f"### {hook_name}")
            lines.append("")

            # Add hook details
            lines.append(f"- **Type:** `{hook_type}`")
            lines.append(f"- **Hook ID:** {hook_id}")
            lines.append(f"- **Triggered by:** `{phase['event']}`")
            lines.append(f"- **Description:** {phase['description']}")

            # Add queue information if available
            if queues := hook.get("queues"):
                queue_links = ", ".join([f"`{q}`" for q in queues])
                lines.append(f"- **Queues:** {queue_links}")

            # Add config info if available
            if config_keys := list(hook.get("config")):
                lines.append(f"- **Configuration:** {', '.join(f'`{k}`' for k in config_keys)}")

            lines.append("")
            hook_counter += 1

    return "\n".join(lines)


def _generate_workflow_summary(hooks: list[dict[str, Any]], execution_phases: list[dict[str, Any]]) -> str:
    """Generate a text summary of the workflow."""
    active_hooks = [h for h in hooks if h.get("active", True)]
    inactive_hooks = [h for h in hooks if not h.get("active", True)]

    summary_parts = [
        f"Total hooks: {len(hooks)} ({len(active_hooks)} active, {len(inactive_hooks)} inactive)",
        f"Trigger events covered: {len(execution_phases)}",
    ]

    # Count hook types
    type_counts: dict[str, int] = defaultdict(int)
    for hook in active_hooks:
        hook_type = hook.get("type", "unknown")
        type_counts[hook_type] += 1

    if type_counts:
        type_summary = ", ".join([f"{count} {htype}" for htype, count in type_counts.items()])
        summary_parts.append(f"Hook types: {type_summary}")

    # Identify key workflow stages
    key_stages = []
    for phase in execution_phases:
        if phase["hooks"]:
            key_stages.append(phase["event"])

    if key_stages:
        summary_parts.append(f"Key workflow stages: {', '.join(key_stages[:5])}")
        if len(key_stages) > 5:
            summary_parts.append(f"... and {len(key_stages) - 5} more")

    return " | ".join(summary_parts)


@tool
def explain_hook_execution_order(hooks_json: str) -> str:
    """Explain the execution order and timing of hooks in plain language.

    Provides a narrative explanation of when and why each hook executes,
    helping users understand the automation workflow.

    Args:
        hooks_json: JSON string containing hooks data from list_hooks MCP tool

    Returns:
        Plain text explanation of hook execution flow and dependencies

    Example:
        hooks_data = mcp.list_hooks(queue_id=12345)
        explanation = explain_hook_execution_order(hooks_data)
        print(explanation)
    """
    try:
        analysis = json.loads(analyze_hook_dependencies(hooks_json))

        if "error" in analysis:
            return analysis["error"]  # type: ignore[no-any-return]

        execution_phases = analysis["execution_phases"]

        lines = [
            "HOOK EXECUTION FLOW EXPLANATION",
            "=" * 50,
            "",
            f"This queue has {analysis['active_hooks']} active hooks configured across "
            f"{len(execution_phases)} different trigger events.",
            "",
            "Here's how the hooks execute throughout the document lifecycle:",
            "",
        ]

        for i, phase in enumerate(execution_phases, 1):
            lines.append(f"{i}. {phase['event'].upper()}")
            lines.append(f"   When: {phase['description']}")

            if phase["hooks"]:
                lines.append(f"   Hooks triggered ({len(phase['hooks'])}):")
                for hook in phase["hooks"]:
                    hook_type_desc = "Python function" if hook["type"] == "function" else "Webhook call"
                    lines.append(f"   - {hook['name']} ({hook_type_desc})")
            else:
                lines.append("   No hooks configured for this event")

            lines.append("")

        # Add workflow insights
        lines.append("WORKFLOW INSIGHTS")
        lines.append("-" * 50)
        lines.append("")

        # Identify automation patterns
        init_hooks = [p for p in execution_phases if "initialize" in p["event"]]
        if init_hooks and init_hooks[0]["hooks"]:
            lines.append(
                f"• Initial automation: {len(init_hooks[0]['hooks'])} hook(s) run when "
                "documents first arrive to set up data"
            )

        update_hooks = [p for p in execution_phases if "updated" in p["event"]]
        if update_hooks and update_hooks[0]["hooks"]:
            lines.append(
                f"• Real-time validation: {len(update_hooks[0]['hooks'])} hook(s) monitor changes as users annotate"
            )

        confirm_hooks = [p for p in execution_phases if "confirm" in p["event"] or "export" in p["event"]]
        if confirm_hooks:
            total_confirm = sum(len(p["hooks"]) for p in confirm_hooks)
            if total_confirm > 0:
                lines.append(f"• Pre-export processing: {total_confirm} hook(s) run final checks before export")

        return "\n".join(lines)

    except Exception as e:
        return f"Error explaining execution order: {e}"
