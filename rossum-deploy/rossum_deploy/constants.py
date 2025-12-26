from __future__ import annotations

from rossum_api.domain_logic.resources import Resource

from rossum_deploy.models import ObjectType

OBJECT_FOLDERS = {
    ObjectType.WORKSPACE: "workspaces",
    ObjectType.QUEUE: "queues",
    ObjectType.SCHEMA: "schemas",
    ObjectType.INBOX: "inboxes",
    ObjectType.HOOK: "hooks",
    ObjectType.CONNECTOR: "connectors",
    ObjectType.ENGINE: "engines",
    ObjectType.EMAIL_TEMPLATE: "email_templates",
    ObjectType.RULE: "rules",
}

OBJECT_TYPE_TO_RESOURCE = {
    ObjectType.WORKSPACE: Resource.Workspace,
    ObjectType.QUEUE: Resource.Queue,
    ObjectType.SCHEMA: Resource.Schema,
    ObjectType.INBOX: Resource.Inbox,
    ObjectType.HOOK: Resource.Hook,
    ObjectType.CONNECTOR: Resource.Connector,
    ObjectType.ENGINE: Resource.Engine,
    ObjectType.EMAIL_TEMPLATE: Resource.EmailTemplate,
    ObjectType.RULE: Resource.Rule,
}

IGNORED_FIELDS = {
    "url",  # Auto-generated, differs between environments
    "modified_at",  # Metadata, changes on any update
    "modified_by",  # Metadata, user who made changes
    "created_at",  # Metadata, creation timestamp
    "counts",  # Runtime statistics
    "users",  # User assignments differ between environments
    "status",  # Runtime state
    "triggers",  # Auto-created by API for email templates, not copied
}

# Fields to ignore during comparison for specific object types
# These are remapped during deploy, so comparing source vs target values is meaningless
TYPE_SPECIFIC_IGNORED_FIELDS: dict[ObjectType, set[str]] = {
    ObjectType.EMAIL_TEMPLATE: {"queue"},  # Remapped to target queue during deploy
    ObjectType.INBOX: {"queue", "queues", "email", "email_hash"},  # Immutable/auto-generated after creation
    ObjectType.QUEUE: {"inbox", "webhooks", "hooks"},  # inbox immutable; webhooks/hooks are URL refs that differ
    ObjectType.HOOK: {"queues", "run_after", "token_owner"},  # Workspace-specific URL references
}

DIFFABLE_TYPES = [
    ObjectType.WORKSPACE,
    ObjectType.QUEUE,
    ObjectType.SCHEMA,
    ObjectType.INBOX,
    ObjectType.HOOK,
    ObjectType.CONNECTOR,
    ObjectType.ENGINE,
    ObjectType.EMAIL_TEMPLATE,
    ObjectType.RULE,
]

PUSHABLE_TYPES = DIFFABLE_TYPES
