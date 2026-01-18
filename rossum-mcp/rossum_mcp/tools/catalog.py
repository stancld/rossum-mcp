"""Tool catalog for dynamic tool discovery.

Provides lightweight metadata for all MCP tools organized by category.
This is the single source of truth for tool categorization - the agent
fetches this catalog from MCP to avoid data duplication.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolInfo:
    """Lightweight tool metadata for catalog."""

    name: str
    description: str


@dataclass
class ToolCategory:
    """A category of related tools."""

    name: str
    description: str
    tools: list[ToolInfo]
    keywords: list[str]


# Tool catalog organized by functional category
# Keywords enable automatic pre-loading based on user request text
TOOL_CATALOG: dict[str, ToolCategory] = {
    "annotations": ToolCategory(
        name="annotations",
        description="Document processing: upload, retrieve, update, and confirm annotations",
        tools=[
            ToolInfo("upload_document", "Upload document to queue"),
            ToolInfo("get_annotation", "Retrieve annotation with extracted data"),
            ToolInfo("list_annotations", "List annotations for a queue"),
            ToolInfo("start_annotation", "Start annotation (to_review -> reviewing)"),
            ToolInfo("bulk_update_annotation_fields", "Bulk update annotation fields"),
            ToolInfo("confirm_annotation", "Confirm annotation (-> confirmed)"),
        ],
        keywords=["annotation", "document", "upload", "extract", "confirm", "review"],
    ),
    "queues": ToolCategory(
        name="queues",
        description="Queue management: create, configure, and list document processing queues",
        tools=[
            ToolInfo("get_queue", "Retrieve queue details"),
            ToolInfo("list_queues", "List all queues"),
            ToolInfo("get_queue_schema", "Get queue's schema"),
            ToolInfo("get_queue_engine", "Get queue's AI engine"),
            ToolInfo("create_queue", "Create a queue"),
            ToolInfo("update_queue", "Update queue settings"),
            ToolInfo("get_queue_template_names", "List available queue templates"),
            ToolInfo("create_queue_from_template", "Create queue from template"),
        ],
        keywords=["queue", "inbox", "connector"],
    ),
    "schemas": ToolCategory(
        name="schemas",
        description="Schema management: define and modify document field structures",
        tools=[
            ToolInfo("get_schema", "Retrieve schema details"),
            ToolInfo("list_schemas", "List all schemas"),
            ToolInfo("update_schema", "Update schema"),
            ToolInfo("create_schema", "Create new schema"),
            ToolInfo("patch_schema", "Add/update/remove schema fields"),
            ToolInfo("get_schema_tree_structure", "Get lightweight schema tree"),
            ToolInfo("prune_schema_fields", "Bulk remove schema fields"),
        ],
        keywords=["schema", "field", "datapoint", "section", "multivalue", "tuple"],
    ),
    "engines": ToolCategory(
        name="engines",
        description="AI engine management: create and configure extraction/splitting engines",
        tools=[
            ToolInfo("get_engine", "Retrieve engine details"),
            ToolInfo("list_engines", "List all engines"),
            ToolInfo("update_engine", "Update engine settings"),
            ToolInfo("create_engine", "Create new engine"),
            ToolInfo("create_engine_field", "Create engine field mapping"),
            ToolInfo("get_engine_fields", "List engine fields"),
        ],
        keywords=["engine", "ai", "extractor", "splitter", "training"],
    ),
    "hooks": ToolCategory(
        name="hooks",
        description="Extensions/webhooks: create and manage automation hooks",
        tools=[
            ToolInfo("get_hook", "Retrieve hook details with code"),
            ToolInfo("list_hooks", "List all hooks for a queue"),
            ToolInfo("create_hook", "Create new hook"),
            ToolInfo("update_hook", "Update hook configuration"),
            ToolInfo("list_hook_logs", "View hook execution logs"),
            ToolInfo("list_hook_templates", "List Rossum Store templates"),
            ToolInfo("create_hook_from_template", "Create hook from template"),
        ],
        keywords=["hook", "extension", "webhook", "automation", "function", "serverless"],
    ),
    "email_templates": ToolCategory(
        name="email_templates",
        description="Email templates: configure automated email responses",
        tools=[
            ToolInfo("get_email_template", "Retrieve email template"),
            ToolInfo("list_email_templates", "List email templates"),
            ToolInfo("create_email_template", "Create email template"),
        ],
        keywords=["email", "template", "notification", "rejection"],
    ),
    "document_relations": ToolCategory(
        name="document_relations",
        description="Document relations: manage export/einvoice document links",
        tools=[
            ToolInfo("get_document_relation", "Retrieve document relation"),
            ToolInfo("list_document_relations", "List document relations"),
        ],
        keywords=["document relation", "export", "einvoice"],
    ),
    "relations": ToolCategory(
        name="relations",
        description="Annotation relations: manage edit/attachment/duplicate links",
        tools=[
            ToolInfo("get_relation", "Retrieve relation details"),
            ToolInfo("list_relations", "List annotation relations"),
        ],
        keywords=["relation", "duplicate", "attachment", "edit"],
    ),
    "rules": ToolCategory(
        name="rules",
        description="Validation rules: manage schema validation rules",
        tools=[
            ToolInfo("get_rule", "Retrieve rule details"),
            ToolInfo("list_rules", "List validation rules"),
        ],
        keywords=["rule", "validation", "constraint"],
    ),
    "users": ToolCategory(
        name="users",
        description="User management: list users and roles",
        tools=[
            ToolInfo("get_user", "Retrieve user details"),
            ToolInfo("list_users", "List users with filters"),
            ToolInfo("list_user_roles", "List available user roles"),
        ],
        keywords=["user", "role", "permission", "token_owner"],
    ),
    "workspaces": ToolCategory(
        name="workspaces",
        description="Workspace management: organize queues into workspaces",
        tools=[
            ToolInfo("get_workspace", "Retrieve workspace details"),
            ToolInfo("list_workspaces", "List all workspaces"),
            ToolInfo("create_workspace", "Create new workspace"),
        ],
        keywords=["workspace", "organization"],
    ),
}


def get_catalog_summary() -> str:
    """Get a compact text summary of all tool categories for the system prompt."""
    lines = ["Available MCP tool categories (use `list_tool_categories` for details):"]
    for category in TOOL_CATALOG.values():
        tool_names = ", ".join(t.name for t in category.tools)
        lines.append(f"- **{category.name}**: {category.description} [{tool_names}]")
    return "\n".join(lines)
