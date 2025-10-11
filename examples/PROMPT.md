## Prompt used for reaching our ultimate goal

Upload all invoices from /Users/daniel.stancl/projects/rossum-mcp/examples/data folder to Rossum to the queue 3901094. Once you send all annotations, wait for a few seconds. Then, start checking annotation status. Once all are imported, return a list of all annotations_urls. You should create separate python execution session for each individual task to keep everything atomic.


## Prompt used to testing the schema retrieval followed by retrieval of all line items across all docs
1. Fetch the schema for queue 3901094
2. Identify the schema field IDs for:
    - Line item description field
    - Line item total amount field
3. Retrieve all annotations in 'to_review' state from queue 3901094
4. For each document:
    - Extract all line items
    - Create a dictionary mapping {item_description: item_amount_total}
    - If multiple line items share the same description, sum their amounts
    - Print result for each document
5. Aggregate across all documents: sum amounts for each unique description
6. Return the final dictionary: {description: total_amount_across_all_docs}

Proceed step-by-step and show intermediate results after each major step.

## Prompt for plot generation

Using the provided data, generate bar plot displaying revenue by services. Sort it in descending order. Store it interactive `revenue.html`.

Data:
```
{'API Integration Development': 26992.25, 'System Architecture Design': 59209.98, 'DevOps Automation Setup': 21064.31, 'Code Review and Optimization': 28266.449999999997, 'Database Design and
Migration': 47037.86, 'Software Development Services': 26441.66, 'Security Audit Services': 16695.22, 'Cloud Infrastructure Consulting': 23659.550000000003, 'Performance Testing': 9997.68, 'Technical
Documentation': 10884.769999999999}
