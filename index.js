#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import axios from "axios";
import FormData from "form-data";
import fs from "fs";

/**
 * Rossum MCP Server
 * Provides tools for uploading documents and retrieving annotations using Rossum API
 */

class RossumMCPServer {
  constructor() {
    this.server = new Server(
      {
        name: "rossum-mcp-server",
        version: "1.0.0",
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.baseUrl = process.env.ROSSUM_API_BASE_URL;
    this.apiToken = process.env.ROSSUM_API_TOKEN;

    if (!this.apiToken) {
      throw new Error("ROSSUM_API_TOKEN environment variable must be set");
    }

    this.setupHandlers();
  }

  /**
   * Upload a document to Rossum
   */
  async uploadDocument(filePath, queueId) {

    if (!fs.existsSync(filePath)) {
      throw new Error(`File not found: ${filePath}`);
    }

    const form = new FormData();
    form.append("content", fs.createReadStream(filePath));

    try {
      const response = await axios.post(
        `${this.baseUrl}/queues/${queueId}/upload`,
        form,
        {
          headers: {
            ...form.getHeaders(),
            Authorization: `Bearer ${this.apiToken}`,
          },
        }
      );

      return {
        annotation_id: response.data.results[0].annotation,
        document_id: response.data.results[0].document,
        queue_id: queueId,
        status: "uploaded",
      };
    } catch (error) {
      throw new Error(`Upload failed: ${error.response?.data?.message || error.message}`);
    }
  }

  /**
   * Retrieve annotation data from Rossum
   */
  async getAnnotation(annotationId) {
    try {
      const response = await axios.get(
        `${this.baseUrl}/annotations/${annotationId}`,
        {
          headers: {
            Authorization: `Bearer ${this.apiToken}`,
          },
        }
      );

      return {
        id: response.data.id,
        status: response.data.status,
        url: response.data.url,
        document: response.data.document,
        content: response.data.content,
        created_at: response.data.created_at,
        modified_at: response.data.modified_at,
      };
    } catch (error) {
      throw new Error(`Failed to retrieve annotation: ${error.response?.data?.message || error.message}`);
    }
  }

  /**
   * Setup MCP protocol handlers
   */
  setupHandlers() {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: "upload_document",
          description: "Upload a document to Rossum for processing. Returns annotation and document IDs.",
          inputSchema: {
            type: "object",
            properties: {
              file_path: {
                type: "string",
                description: "Absolute path to the document file to upload",
              },
              queue_id: {
                type: "string",
                description: "Rossum queue ID where the document should be uploaded",
              },
            },
            required: ["file_path", "queue_id"],
          },
        },
        {
          name: "get_annotation",
          description: "Retrieve annotation data for a previously uploaded document",
          inputSchema: {
            type: "object",
            properties: {
              annotation_id: {
                type: "string",
                description: "The annotation ID returned from upload_document",
              },
            },
            required: ["annotation_id"],
          },
        },
      ],
    }));

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      try {
        switch (request.params.name) {
          case "upload_document": {
            const { file_path, queue_id } = request.params.arguments;
            const result = await this.uploadDocument(file_path, queue_id);
            return {
              content: [
                {
                  type: "text",
                  text: JSON.stringify(result, null, 2),
                },
              ],
            };
          }

          case "get_annotation": {
            const { annotation_id } = request.params.arguments;
            const result = await this.getAnnotation(annotation_id);
            return {
              content: [
                {
                  type: "text",
                  text: JSON.stringify(result, null, 2),
                },
              ],
            };
          }

          default:
            throw new Error(`Unknown tool: ${request.params.name}`);
        }
      } catch (error) {
        return {
          content: [
            {
              type: "text",
              text: `Error: ${error.message}`,
            },
          ],
          isError: true,
        };
      }
    });
  }

  /**
   * Start the MCP server
   */
  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error("Rossum MCP Server running on stdio");
  }
}

// Start the server
const server = new RossumMCPServer();
server.run().catch(console.error);
