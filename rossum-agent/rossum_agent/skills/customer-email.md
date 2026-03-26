---
name: Customer Email
description: draft professional customer-facing emails summarizing investigation findings, changes, or resolutions
---

# Customer Email Skill

**Goal**: Draft professional customer-facing emails summarizing investigation findings, configuration changes, or issue resolutions.

## Workflow

1. Gather findings from the current chat context (tools used, entities inspected, changes made, issues found)
2. Structure into a professional email using the format below
3. Save via `write_file(file_path="customer_email.md", content=<email>)`

## Email Format

```
Subject: [Concise summary of topic]

Hello [Name],

[Opening — acknowledge the request or issue]

[Findings / changes / resolution — organized with bullet points or numbered steps]

[References — annotation/document/queue links if relevant]

[Next steps or closing ask]

Kind regards,
[Agent user's name] - The Rossum Team
```

## Tone & Style

| Principle | Detail |
|-----------|--------|
| Clarity | Simple language, no jargon unless the client is technical |
| Conciseness | Answer what was asked — no tangents or information overload |
| Professional authority | State facts confidently — never "usually," "it seems like," "my understanding is" |
| Solution-focused | Lead with what was done or what the client should do, not lengthy backstory |
| Empathy | Acknowledge frustration or impact when relevant, without over-apologizing |

## Confidentiality Constraints

Never include any of the following in customer emails:

| Prohibited | Examples |
|------------|----------|
| Internal tool references | Freshdesk tickets, Slack channels, Jira issues, internal dashboards |
| Internal process details | How the agent investigated, internal escalation paths, system internals |
| Other clients' data | Account details, configurations, or issues from other organizations |
| Unreleased features | Roadmap items, features behind feature flags, unannounced capabilities |
| Employee PII | Personal emails, phone numbers, full names of internal staff (unless approved) |
| Internal links | Links to Freshdesk, Slack, Jira, internal Google Docs, admin tools |

Safe to include: links to `knowledge-base.rossum.ai`, `rossum.app/api/docs`, the client's own Rossum UI URLs, and officially announced features.

## Referencing Rossum Entities

When the investigation involved specific Rossum objects, include references the client can act on:

| Entity | How to reference |
|--------|-----------------|
| Annotation/Document | Link to Rossum UI: `https://<base>/document/<annotation_id>` |
| Queue | Queue name and ID |
| Hook | Hook name (not internal URL) |
| Schema field | Field label and ID |
| Configuration change | What was changed and current state |

## Adapting to Context

| Scenario | Email focus |
|----------|-------------|
| Bug investigation | Root cause, current status, resolution or next steps |
| Configuration change | What was changed, why, how to verify |
| How-to question | Step-by-step answer, relevant doc links |
| Data analysis | Key findings, numbers, recommendations |
| Escalation | Summary of what was tried, what remains, who owns next step |

## Cross-Reference

- Documentation links: `search_knowledge_base` for client-facing articles
- Investigation context: review chat history for tools called and findings
