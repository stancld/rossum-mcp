## Prompt used for reaching our ultimate goal
1. Upload all invoices from `/Users/daniel.stancl/projects/rossum-mcp/examples/data` folder to Rossum to the queue 3901094.
    - Do not include documents from `knowledge` folder.
2. Once you send all annotations, wait for a few seconds.
3. Then, start checking annotation status. Once all are imported, return a list of all annotations_urls
4. Fetch the schema for the target queue.
5. Identify the schema field IDs for:
    - Line item description field
    - Line item total amount field
6. Retrieve all annotations in 'to_review' state from queue 3901094
7. For each document:
    - Extract all line items
    - Create a dictionary mapping {item_description: item_amount_total}
    - If multiple line items share the same description, sum their amounts
    - Print result for each document
8. Aggregate across all documents: sum amounts for each unique description
9. Return the final dictionary: {description: total_amount_across_all_docs}
10. Using the retrieved data, generate bar plot displaying revenue by services. Sort it in descending order. Store it interactive `revenue.html`.

Proceed step-by-step and show intermediate results after each major step.
