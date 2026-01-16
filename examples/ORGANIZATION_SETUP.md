# Set up a new customer

Workspace: 1417456
Region: EU

## Tasks:

1. Create two new queues: Invoices and Credit Notes.
2. Update schemas w.r.t. ## Schemas section
3. Add field to Invoices queue.
    - Field name: The Net Terms
    - Section: basic_info_section
    - Logic: Compute 'Due Date' - 'Issue Date' and categorize it as 'Net 15', 'Net 30' and 'Outstanding'
4. Implement **duplicate document detection** in `Invoices` queue.
    - Match: Document ID
    - User token owner: morgan-accuracy@elis.rossum.ai
    - Trigger actions: ["initialize", "started", "user_update", "updated"]
    - Message: "Duplicate detected! Invoice ID already exists in annotation: %ANNOTATION_ID%"
    - Otherwise, default settings.
5. Add business validations with these 3 checks:
    - Total amount is smaller than 400. Error message: "Total amount is larger than allowed 400."
    - Sum of all total amount line items equals total amount. Error message: "Sum of all total amount line items does not equal total amount."
    - All line items it holds: "quantity x unit price = total amount"
6. Add extension for e-mail notification upon document status is changed to 'to_review'.
    - Recipient: Dan Stancl (daniel.stancl@rossum.ai)
    - Document should be templated from some generic message informing user about successful document upload.
7. Update Invoice queue UI settings to display the following fields:
    - status
    - original file name
    - details
    - Document ID
    - Due Date
    - The Net Terms
    - Total Amount
    - Vendor Name
    - Received at
8. Finally, verify the setup by uploading a sample invoice and checking if the setup is working as expected.
    - Use provided invoice and upload it twice to the `Invoices` queue (with 5 seconds delay between uploads)

## Schemas

### Invoices
| Field | Type | Table field |
|-------|------| ----------- |
| Document ID | String | No |
| Issue Date | Date | No |
| Due Date | Date | No |
| Vendor Name | String | No |
| Vendor Address | String, multiline | No |
| Customer Name | String | No |
| Customer Address | String, multiline | No |
| Total Amount | Float | No |
| Total Tax | Float | No |
| Currency | String | No |
| Code | String, multiline | Yes |
| Description | String, multiline | Yes |
| Quantity | Integer | Yes |
| Unit Price | Float | Yes |
| Total | Float | Yes |

Constraints:
- No payment intsructions fields
- No customer delivery address / name fields

### Credit notes
- Keep it as it is
