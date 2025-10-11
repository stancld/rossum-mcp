#!/usr/bin/env python3
"""
Rossum MCP Server
Provides tools for uploading documents and retrieving annotations using Rossum API
"""

import os
import sys
import asyncio
import logging
import concurrent.futures
from collections.abc import Sequence
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from rossum_api import SyncRossumAPIClient
from rossum_api.dtos import Token

# Set up logging to a file (since stdout is used for MCP)
logging.basicConfig(
    filename="/tmp/rossum_mcp_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class RossumMCPServer:
    """MCP Server for Rossum API integration"""

    def __init__(self) -> None:
        self.server = Server("rossum-mcp-server")
        self.base_url = os.environ["ROSSUM_API_BASE_URL"]
        self.api_token = os.environ["ROSSUM_API_TOKEN"]

        self.client = SyncRossumAPIClient(
            base_url=self.base_url, credentials=Token(token=self.api_token)
        )

        self.setup_handlers()

    def _upload_document_sync(self, file_path: str, queue_id: int) -> dict:
        """Upload a document to Rossum (synchronous implementation).

        Args:
            file_path: Absolute path to the document file
            queue_id: Rossum queue ID where the document should be uploaded

        Returns:
            Dictionary containing task_id, task_status, queue_id, and message

        Raises:
            FileNotFoundError: If the specified file does not exist
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        task = self.client.upload_document(queue_id, [(str(path), path.name)])[0]

        return {
            "task_id": task.id,
            "task_status": task.status,
            "queue_id": queue_id,
            "message": "Document upload initiated. Use `list_annotations` to find the annotation ID for this queue.",
        }

    async def upload_document(self, file_path: str, queue_id: int) -> dict:
        """Upload a document to Rossum for processing (async wrapper).

        Args:
            file_path: Absolute path to the document file
            queue_id: Rossum queue ID where the document should be uploaded

        Returns:
            Dictionary containing task_id, task_status, queue_id, and message
        """
        import concurrent.futures

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(
                pool, self._upload_document_sync, file_path, queue_id
            )

    def _get_annotation_sync(
        self, annotation_id: int, sideloads: Sequence[str] = ()
    ) -> dict:
        """Retrieve annotation data from Rossum (synchronous implementation).

        Args:
            annotation_id: The annotation ID to retrieve
            sideloads: List of sideloads to include (e.g., ['content'])

        Returns:
            Dictionary containing annotation details including id, status, url, content, etc.
        """
        logger.debug(f"Retrieving annotation: annotation_id={annotation_id}")

        annotation = self.client.retrieve_annotation(annotation_id, sideloads)

        return {
            "id": annotation.id,
            "status": annotation.status,
            "url": annotation.url,
            "schema": annotation.schema,
            "modifier": annotation.modifier,
            "document": annotation.document,
            "content": annotation.content,
            "created_at": annotation.created_at,
            "modified_at": annotation.modified_at,
        }

    async def get_annotation(
        self, annotation_id: int, sideloads: Sequence[str] = ()
    ) -> dict:
        """Retrieve annotation data from Rossum (async wrapper)"""
        import concurrent.futures

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(
                pool, self._get_annotation_sync, annotation_id, sideloads
            )

    def _list_annotations_sync(self, queue_id: int, status: str | None = None) -> dict:
        """List annotations for a queue (synchronous implementation).

        Args:
            queue_id: Rossum queue ID to list annotations from
            status: Optional status filter (comma-separated)

        Returns:
            Dictionary containing count and results list of annotations
        """
        logger.debug(f"Listing annotations: queue_id={queue_id}, status={status}")

        # Build filter parameters
        params: dict = {"queue": queue_id, "page_size": 100}
        if status:
            params["status"] = status

        annotations_list = list(self.client.list_annotations(**params))

        return {
            "count": len(annotations_list),
            "results": [
                {
                    "id": ann.id,
                    "status": ann.status,
                    "url": ann.url,
                    "document": ann.document,
                    "created_at": ann.created_at,
                    "modified_at": ann.modified_at,
                }
                for ann in annotations_list
            ],
        }

    async def list_annotations(
        self,
        queue_id: int,
        status: str | None = "importing,to_review,confirmed,exported",
    ) -> dict:
        """List annotations for a queue with optional filtering (async wrapper).

        Args:
            queue_id: Rossum queue ID to list annotations from
            status: Optional status filter (comma-separated). Defaults to common statuses.

        Returns:
            Dictionary containing count and results list of annotations
        """
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(
                pool, self._list_annotations_sync, queue_id, status
            )

    def _get_queue_sync(self, queue_id: int) -> dict:
        """Retrieve queue details (synchronous implementation).

        Args:
            queue_id: Rossum queue ID to retrieve

        Returns:
            Dictionary containing queue details including schema_id
        """
        logger.debug(f"Retrieving queue: queue_id={queue_id}")

        queue = self.client.retrieve_queue(queue_id)

        return {
            "id": queue.id,
            "name": queue.name,
            "url": queue.url,
            "schema_id": queue.schema,
            "workspace": queue.workspace,
            "inbox": queue.inbox,
            "created_at": queue.created_at,
            "modified_at": queue.modified_at,
        }

    async def get_queue(self, queue_id: int) -> dict:
        """Retrieve queue details from Rossum (async wrapper)"""
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(pool, self._get_queue_sync, queue_id)

    def _get_schema_sync(self, schema_id: int) -> dict:
        """Retrieve schema details (synchronous implementation).

        Args:
            schema_id: Rossum schema ID to retrieve

        Returns:
            Dictionary containing schema details and content
        """
        logger.debug(f"Retrieving schema: schema_id={schema_id}")

        schema = self.client.retrieve_schema(schema_id)

        return {
            "id": schema.id,
            "name": schema.name,
            "url": schema.url,
            "content": schema.content,
        }

    async def get_schema(self, schema_id: int) -> dict:
        """Retrieve schema data from Rossum (async wrapper)"""
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(pool, self._get_schema_sync, schema_id)

    def _get_queue_schema_sync(self, queue_id: int) -> dict:
        """Retrieve complete schema for a queue (synchronous implementation).

        This convenience method combines queue and schema retrieval in a single call.

        Args:
            queue_id: Rossum queue ID

        Returns:
            Dictionary containing queue and schema details including schema content
        """
        logger.debug(f"Retrieving queue schema: queue_id={queue_id}")

        # First retrieve the queue to get the schema URL/ID
        queue = self.client.retrieve_queue(queue_id)

        # Extract schema ID from the schema URL
        # The schema field is a URL like "https://api.elis.rossum.ai/v1/schemas/12345"
        schema_url = queue.schema
        schema_id = int(schema_url.rstrip("/").split("/")[-1])

        # Now retrieve the schema
        schema = self.client.retrieve_schema(schema_id)

        return {
            "queue_id": queue.id,
            "queue_name": queue.name,
            "schema_id": schema.id,
            "schema_name": schema.name,
            "schema_url": schema.url,
            "schema_content": schema.content,
        }

    async def get_queue_schema(self, queue_id: int) -> dict:
        """Retrieve schema for a given queue (async wrapper)"""
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(
                pool, self._get_queue_schema_sync, queue_id
            )

    def setup_handlers(self) -> None:
        """Setup MCP protocol handlers.

        Registers the list_tools and call_tool handlers for the MCP server.
        These handlers define the available tools and their execution logic.
        """

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="upload_document",
                    description="Upload a document to Rossum for processing. Returns a task ID. IMPORTANT: To get the annotation ID for the uploaded document, you MUST call list_annotations with the queue_id used in this upload.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to the document file to upload",
                            },
                            "queue_id": {
                                "type": "integer",
                                "description": "Rossum queue ID where the document should be uploaded",
                            },
                        },
                        "required": ["file_path", "queue_id"],
                    },
                ),
                Tool(
                    name="get_annotation",
                    description="Retrieve full annotation data including extracted content for a specific annotation. After calling list_annotations to get annotation IDs, use this tool to retrieve each annotation's complete data one by one. The response includes the annotation status, URL, document reference, and extracted content.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "annotation_id": {
                                "type": "integer",
                                "description": "The annotation ID obtained from list_annotations",
                            },
                            "sideloads": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of sideloads to include. Use ['content'] to fetch annotation content with datapoints. Without this, only metadata is returned.",
                            },
                        },
                        "required": ["annotation_id"],
                    },
                ),
                Tool(
                    name="list_annotations",
                    description="List all annotations for a queue with optional filtering. IMPORTANT: After uploading documents, use this tool to get annotation IDs from the queue. The response contains a 'results' array with annotation IDs and their URLs. Use get_annotation to retrieve full details for each annotation one by one.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_id": {
                                "type": "integer",
                                "description": "Rossum queue ID to list annotations from (same queue_id used in upload_document)",
                            },
                            "status": {
                                "type": "string",
                                "description": "Filter by annotation status (e.g., 'importing', 'to_review', 'confirmed', 'exported'). These four are used as default.",
                            },
                        },
                        "required": ["queue_id"],
                    },
                ),
                Tool(
                    name="get_queue",
                    description="Retrieve queue details including the schema_id. Use this to get the schema_id associated with a queue, which can then be used to retrieve the schema with get_schema.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_id": {
                                "type": "integer",
                                "description": "Rossum queue ID to retrieve",
                            },
                        },
                        "required": ["queue_id"],
                    },
                ),
                Tool(
                    name="get_schema",
                    description="Retrieve schema details including the schema content/structure. Use get_queue first to obtain the schema_id for a given queue.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "schema_id": {
                                "type": "integer",
                                "description": "Rossum schema ID to retrieve (obtained from get_queue)",
                            },
                        },
                        "required": ["schema_id"],
                    },
                ),
                Tool(
                    name="get_queue_schema",
                    description="Retrieve the complete schema for a given queue in a single call. This tool automatically fetches the queue details, extracts the schema_id, and retrieves the full schema including its content. This is the recommended way to get a queue's schema.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "queue_id": {
                                "type": "integer",
                                "description": "Rossum queue ID for which to retrieve the schema",
                            },
                        },
                        "required": ["queue_id"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            import json
            import traceback

            try:
                logger.info(f"Tool called: {name} with arguments: {arguments}")

                match name:
                    case "upload_document":
                        result = await self.upload_document(
                            arguments["file_path"], arguments["queue_id"]
                        )
                    case "get_annotation":
                        result = await self.get_annotation(
                            arguments["annotation_id"],
                            sideloads=arguments.get("sideloads", ()),
                        )
                    case "list_annotations":
                        result = await self.list_annotations(
                            queue_id=arguments["queue_id"],
                            status=arguments.get("status"),
                        )
                    case "get_queue":
                        result = await self.get_queue(arguments["queue_id"])
                    case "get_schema":
                        result = await self.get_schema(arguments["schema_id"])
                    case "get_queue_schema":
                        result = await self.get_queue_schema(arguments["queue_id"])
                    case _:
                        raise ValueError(f"Unknown tool: {name}")

                logger.info(f"Tool {name} completed successfully")
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Tool {name} failed: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                error_result = {"error": str(e), "traceback": traceback.format_exc()}
                return [
                    TextContent(type="text", text=json.dumps(error_result, indent=2))
                ]

    async def run(self) -> None:
        """Start the MCP server.

        Runs the server using stdio transport for communication with MCP clients.
        """
        async with stdio_server() as (read_stream, write_stream):
            print("Rossum MCP Server running on stdio", file=sys.stderr)
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )


async def async_main() -> None:
    """Async main entry point.

    Creates and runs the RossumMCPServer instance.
    """
    server = RossumMCPServer()
    await server.run()


def main() -> None:
    """Main entry point for console script.

    This is the entry point used when running the server as a command-line tool.
    It initializes the async event loop and starts the server.
    """
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
