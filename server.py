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
        import concurrent.futures

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(
                pool, self._upload_document_sync, file_path, queue_id
            )

    def _get_annotation_sync(self, annotation_id: int) -> dict:
        logger.debug(f"Retrieving annotation: annotation_id={annotation_id}")

        annotation = self.client.retrieve_annotation(annotation_id)

        return {
            "id": annotation.id,
            "status": annotation.status,
            "url": annotation.url,
            "document": annotation.document,
            "content": annotation.content,
            "created_at": annotation.created_at,
            "modified_at": annotation.modified_at,
        }

    async def get_annotation(self, annotation_id: int) -> dict:
        """Retrieve annotation data from Rossum (async wrapper)"""
        import concurrent.futures

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(
                pool, self._get_annotation_sync, annotation_id
            )

    def _list_annotations_sync(self, queue_id: int, status: str | None = None) -> dict:
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
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(
                pool, self._list_annotations_sync, queue_id, status
            )

    def setup_handlers(self) -> None:
        """Setup MCP protocol handlers"""

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
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            import json
            import traceback

            try:
                logger.info(f"Tool called: {name} with arguments: {arguments}")

                if name == "upload_document":
                    result = await self.upload_document(
                        arguments["file_path"], arguments["queue_id"]
                    )
                elif name == "get_annotation":
                    result = await self.get_annotation(arguments["annotation_id"])
                elif name == "list_annotations":
                    result = await self.list_annotations(
                        queue_id=arguments["queue_id"], status=arguments.get("status")
                    )
                else:
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
        """Start the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            print("Rossum MCP Server running on stdio", file=sys.stderr)
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )


async def main() -> None:
    """Main entry point"""
    server = RossumMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
