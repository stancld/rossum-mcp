# Set up multiple queue and warmup sorting inbox queue

1. Create three new queues in namespace `1777693` - Air Waybills, Certificates of Origin, Invoices.
2. Set up a single enum field on each queue with a name Document type (`document_type`).
3. Upload documents from folders air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to corresponding queues.
4. Annotate all uploaded documents with a correct Document type, and confirm the annotation.
5. Create a new queue in the same namespace - Inbox.
6. Set up inbox predict a single enum type `Document type`.
7. Set up the engine is trained from three created queues - Air Waybills, Certificates of Origin, Invoices.
8. Upload documents from folders air_waybill, certificate_of_origin, invoice in `examples/data/splitting_and_sorting/knowledge` to inbox queues.
9. Based on the file names and predicted values, generate a bar plot with correct/wrong for each document type.

Proceed step-by-step and show intermediate results after each major step.""
