Annotation Status Workflow
===========================

When a document is uploaded, the annotation progresses through various states.
Understanding this workflow is crucial for agents and applications using the MCP server.

Annotation States
-----------------

1. **importing** - Initial state after upload. Document is being processed.
2. **to_review** - Extraction complete, ready for user validation.
3. **reviewing** - A user is currently reviewing the annotation.
4. **confirmed** - The annotation has been validated and confirmed.
5. **exporting** - The annotation is being exported.
6. **exported** - Final state for successfully processed documents.

Other possible states include: ``created``, ``failed_import``, ``split``, ``in_workflow``,
``rejected``, ``failed_export``, ``postponed``, ``deleted``, ``purged``.

Important Considerations
------------------------

**Important**: After uploading documents, agents should wait for annotations to transition
from ``importing`` to ``to_review`` (or ``confirmed``/``exported``) before considering them
fully processed. Use ``get_annotation`` to poll individual annotations or ``list_annotations``
to check the status of multiple documents in bulk.

Example Workflows
-----------------

Single Document Upload
^^^^^^^^^^^^^^^^^^^^^^

1. Upload a document:

.. code-block:: text

   Use upload_document with:
   - file_path: "/path/to/invoice.pdf"
   - queue_id: "12345"
   Response: { task_id: "67890", ... }

2. Wait for processing and check status:

.. code-block:: text

   Use list_annotations with:
   - queue_id: "12345"
   Find the annotation in the results

   Use get_annotation with:
   - annotation_id: "annotation_id_from_list"
   Check status field - wait until it's "to_review", "confirmed", or "exported"

Bulk Document Upload
^^^^^^^^^^^^^^^^^^^^

For agents uploading multiple documents:

1. Upload all documents in bulk:

.. code-block:: text

   For each file:
     Use upload_document with file_path and queue_id
     Store returned task_ids

2. Check status of all annotations:

.. code-block:: text

   Use list_annotations with:
   - queue_id: "12345"
   - status: "to_review" (or check all statuses)
   - ordering: "-created_at"

   This returns all annotations in the queue, allowing you to verify
   which documents have finished processing.

Error Handling
--------------

The server provides detailed error messages for common issues:

* Missing API token
* File not found
* Upload failures
* API errors

All errors are returned in the tool response with appropriate error messages and
stack traces for debugging.
