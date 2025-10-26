# Set up multiple queue and warmup sorting inbox queue

1. Create three new queues in workspace `1777693` - Air Waybills, Certificates of Origin, Invoices.
2. Set up the schema with a single enum field on each queue with a name Document type (`document_type`).
3. Upload documents from folders air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to corresponding queues.
4. Annotate all uploaded documents with a correct Document type, and confirm the annotation.
    - Beware document types are air_waybill, invoice and certificate_of_origin (lower-case, underscores).
5. Create a new engine in organization `1`, with type = 'extractor'.
6. Configure engine training queues to be - Air Waybills, Certificates of Origin, Invoices.
    - DO NOT copy knowledge.
    - Update Engine object.
7. Create a new schema with a single enum field `Document type`.
8. Create a new queue with the created engine and schema in the same workspace called: Inbox.
9. Upload documents from folders air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to inbox queues.
10. Based on the file names and predicted values, generate a pie plot with correct/wrong for each document type.
