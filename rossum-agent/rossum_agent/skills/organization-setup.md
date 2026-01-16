# Organization Setup Skill

**Goal**: Set up Rossum for new customers with correct document types and regional configurations.

## Queue Creation

| Scenario | Tool |
|----------|------|
| New customer onboarding | `create_queue_from_template` |
| Copy existing config | `create_queue` with custom schema |
| Empty queue | `create_queue` |

## Templates

| Template | Region/Type |
|----------|-------------|
| EU Demo Template | European invoices |
| US Demo Template | US invoices |
| UK Demo Template | UK invoices |
| CZ Demo Template | Czech invoices |
| Chinese Invoices (Fapiao) Demo Template | Chinese Fapiao |
| Credit Note Demo Template | Credit notes |
| Debit Note Demo Template | Debit notes |
| Purchase Order Demo Template | Purchase orders |
| Delivery Note Demo Template | Delivery notes |
| Proforma Invoice Demo Template | Proforma invoices |
| Certificates of Analysis Demo Template | Certificates of analysis |

Regional variants: `AP&R {Region} Demo Template`, `Tax Invoice {Region} Demo Template`

## Schema Customization

**Load `schema-pruning` skill** for bulk field removal, **`schema-patching` skill** for adding fields.

### Schema Pruning

Use `prune_schema_fields(schema_id, fields_to_keep=[...])` to remove unwanted fields in one call. Specify leaf field IDs only—parent containers (sections, multivalues, tuples) are preserved automatically. Alternatively, use `fields_to_remove` parameter to remove specific fields instead.

| Field status | Action |
|--------------|--------|
| Requested + exists in template | Keep |
| Requested + not in template | Add to correct section |
| In template + not requested | **Remove** |

**Section placement** (verify against actual schema):

| Field semantics | Typical section |
|-----------------|-----------------|
| Document ID, dates, order numbers | `basic_info_section` |
| Vendor/supplier info | Section with `sender_` prefixed fields |
| Customer/recipient info | Section with `recipient_` prefixed fields |
| Amounts, totals, tax | `amounts_section` |
| Line item columns | `line_items_section` (multivalue) |

## Constraints

- Match region to template (EU/US/UK/CZ/CN defaults differ)
- Templates include pre-configured engine
- No mermaid diagrams unless explicitly requested
- Customize via `update_schema` after creation
