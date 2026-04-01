"""Generate OpenAPI spec JSON from the FastAPI app.

SSE stream models (AgentQuestionItemSchema, QuestionOptionSchema, etc.) are not
referenced by any FastAPI endpoint, so FastAPI omits them from the auto-generated
schema.  We inject them manually via _SSE_EVENT_MODELS so that the TypeScript
client can consume the same types.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import TypeAdapter
from rossum_agent.api.main import app
from rossum_agent.api.models.schemas import (
    AgentQuestionItemSchema,
    DocumentContent,
    FileCreatedSchema,
    FinalAnswerSchema,
    MessageRequest,
    QuestionOptionSchema,
    TaskSnapshotTaskSchema,
)

# Models that must appear in the OpenAPI spec even though no endpoint
# references them directly (SSE event payloads, Depends()-injected bodies, etc.).
_SSE_EVENT_MODELS: list[type] = [
    QuestionOptionSchema,
    AgentQuestionItemSchema,
    TaskSnapshotTaskSchema,
    FinalAnswerSchema,
    FileCreatedSchema,
    MessageRequest,
    DocumentContent,
]


def main() -> None:
    default_path = Path(__file__).resolve().parent.parent / "rossum_agent" / "api" / "openapi.json"
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    spec = app.openapi()

    # Inject SSE event models into the schema
    schemas = spec.setdefault("components", {}).setdefault("schemas", {})
    for model in _SSE_EVENT_MODELS:
        adapter = TypeAdapter(model)
        schema = adapter.json_schema(ref_template="#/components/schemas/{model}")
        # Pull out nested $defs and merge them into the top-level schemas
        for def_name, def_schema in schema.pop("$defs", {}).items():
            schemas[def_name] = def_schema
        schemas[model.__name__] = schema

    # Inject requestBody for endpoints that use Depends() for body parsing,
    # which FastAPI cannot detect automatically.
    _OPERATION_REQUEST_BODIES: dict[str, str] = {
        "send_message_api_v1_chats__chat_id__messages_post": "MessageRequest",
    }
    for path_item in spec.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            op_id = operation.get("operationId", "")
            if op_id in _OPERATION_REQUEST_BODIES:
                operation["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{_OPERATION_REQUEST_BODIES[op_id]}"}
                        }
                    },
                }

    output_path.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"OpenAPI spec written to {output_path}")


if __name__ == "__main__":
    main()
