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
from rossum_agent.api.models.schemas import AgentQuestionItemSchema, QuestionOptionSchema, TaskSnapshotTaskSchema

# Models used in SSE events that must appear in the OpenAPI spec even though
# no endpoint references them directly.
_SSE_EVENT_MODELS: list[type] = [
    QuestionOptionSchema,
    AgentQuestionItemSchema,
    TaskSnapshotTaskSchema,
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

    output_path.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"OpenAPI spec written to {output_path}")


if __name__ == "__main__":
    main()
