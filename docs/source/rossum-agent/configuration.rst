Configuration
=============

Environment Variables
---------------------

.. list-table::
   :header-rows: 1
   :widths: 35 10 55

   * - Variable
     - Required
     - Description
   * - ``ROSSUM_API_TOKEN``
     - Yes
     - Rossum API authentication token
   * - ``ROSSUM_API_BASE_URL``
     - Yes
     - API endpoint, e.g. ``https://api.elis.rossum.ai/v1``
   * - ``AWS_REGION``
     - No
     - AWS region for Bedrock (default: ``us-east-1``)
   * - ``AWS_BEDROCK_MODEL_ARN``
     - No
     - Custom ARN for Opus model
   * - ``AWS_BEDROCK_MODEL_ARN_SMALL``
     - No
     - Custom ARN for Haiku model
   * - ``POSTGRES_HOST`` / ``POSTGRES_PORT``
     - No
     - PostgreSQL connection (default: ``localhost:5432``)
   * - ``POSTGRES_DB`` / ``POSTGRES_USER`` / ``POSTGRES_PASSWORD``
     - No
     - PostgreSQL credentials (default: ``rossum_agent``/``rossum``/``rossum``)
   * - ``REDIS_HOST`` / ``REDIS_PORT``
     - No
     - Redis for change tracking (default: ``localhost:6379``)
   * - ``ROSSUM_MCP_MODE``
     - No
     - ``read-write`` (default) or ``read-only``
   * - ``ROSSUM_AGENT_PERSONA``
     - No
     - Agent persona: ``default`` or ``cautious``
   * - ``SLACK_BOT_TOKEN`` / ``SLACK_CHANNEL``
     - No
     - Slack integration for reports

Prompt Caching
--------------

The agent automatically applies Anthropic's ``cache_control`` breakpoints to reduce input token costs by up to 90%. Three breakpoints per request:

1. **System prompt** -- static across the conversation, cached once
2. **Last tool definition** -- stable per agent iteration
3. **Last message** -- moves forward with each turn to maximize cache reuse

Works transparently on AWS Bedrock -- no configuration needed. Token usage metrics are reported in the ``done`` SSE event.

Slash Commands
--------------

Messages starting with ``/`` are intercepted before reaching the agent and return instant responses without consuming tokens.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Command
     - Description
   * - ``/list-commands``
     - List all available slash commands
   * - ``/list-commits``
     - List configuration commits made in this chat (requires Redis)
   * - ``/list-skills``
     - List available agent skills with slugs and descriptions
   * - ``/list-mcp-tools``
     - List MCP tools grouped by category
   * - ``/list-agent-tools``
     - List built-in agent tools with descriptions

Commands are also discoverable via ``GET /api/v1/commands``.
