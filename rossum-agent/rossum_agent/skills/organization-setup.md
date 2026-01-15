# Organization Setup Skill

**Goal**: Set up Rossum for new customers with correct document types and regional configurations.

## Queue Creation Strategy

| Scenario | Recommended Tool |
|----------|------------------|
| New customer onboarding | `create_queue_from_template` (preferred) |
| Copying existing queue config | `create_queue` with custom schema |
| Empty queue for custom schema | `create_queue` |

**Always prefer `create_queue_from_template`** - templates include pre-configured schema, field mappings, and AI engine optimized for specific document types.

## Available Templates

| Template | Use Case |
|----------|----------|
| EU Demo Template | European invoices (general) |
| AP&R EU Demo Template | EU accounts payable & receivable |
| Tax Invoice EU Demo Template | EU tax invoices |
| US Demo Template | US invoices (general) |
| AP&R US Demo Template | US accounts payable & receivable |
| Tax Invoice US Demo Template | US tax invoices |
| UK Demo Template | UK invoices (general) |
| AP&R UK Demo Template | UK accounts payable & receivable |
| Tax Invoice UK Demo Template | UK tax invoices |
| CZ Demo Template | Czech invoices |
| Chinese Invoices (Fapiao) Demo Template | Chinese Fapiao invoices |
| Tax Invoice CN Demo Template | Chinese tax invoices |
| Purchase Order Demo Template | Purchase orders |
| Credit Note Demo Template | Credit notes |
| Debit Note Demo Template | Debit notes |
| Proforma Invoice Demo Template | Proforma invoices |
| Delivery Notes Demo Template | Delivery notes |
| Delivery Note Demo Template | Delivery note (singular) |
| Certificates of Analysis Demo Template | Certificates of analysis |
| Empty Organization Template | Blank starting point |

## Setup Workflow

1. **Identify document types** - Ask customer what documents they process
2. **Determine region** - Match to EU/US/UK/CZ/CN templates
3. **Create workspace** - Use `create_workspace` if needed
4. **Create queue from template** - Use `create_queue_from_template` with appropriate template
5. **Customize schema** - Modify if customer needs additional fields or remove redundant fields

## Example

```python
create_queue_from_template(
    name="ACME Corp - Invoices",
    template_name="EU Demo Template",
    workspace_id=123
)
```

## Key Constraints

- **Region matters** - EU/US/UK templates have different field defaults and tax handling
- **Template includes engine** - No need to manually assign engine when using templates
- **Schema is editable after creation** - Start with template, then customize via `update_schema`
