"""Tests for custom OpenAPI schema with SSE event documentation."""

from __future__ import annotations

from rossum_agent.api.main import (
    _MESSAGES_PATH,
    _SSE_EVENT_MODELS,
    _SSE_EVENT_REFS,
    _SSE_EVENTS,
    app,
)


def _get_fresh_schema() -> dict:
    """Force regeneration of the OpenAPI schema."""
    app.openapi_schema = None
    try:
        return app.openapi()
    finally:
        app.openapi_schema = None


class TestOpenAPISchema:
    def test_sse_event_models_in_components(self):
        schema = _get_fresh_schema()
        schemas = schema["components"]["schemas"]

        for model in _SSE_EVENT_MODELS:
            assert model.__name__ in schemas, f"{model.__name__} missing from OpenAPI schemas"

    def test_nested_defs_extracted_to_top_level(self):
        schema = _get_fresh_schema()
        schemas = schema["components"]["schemas"]

        # SubAgentTokenUsageDetail is referenced by TokenUsageBreakdown via $defs
        assert "SubAgentTokenUsageDetail" in schemas

    def test_no_leftover_defs_in_models(self):
        schema = _get_fresh_schema()
        schemas = schema["components"]["schemas"]

        for model in _SSE_EVENT_MODELS:
            model_schema = schemas[model.__name__]
            assert "$defs" not in model_schema, f"{model.__name__} still has $defs"

    def test_sse_event_union_schema(self):
        schema = _get_fresh_schema()
        schemas = schema["components"]["schemas"]

        assert "SSEEvent" in schemas
        sse_event = schemas["SSEEvent"]
        assert "oneOf" in sse_event

        refs = [entry["$ref"].split("/")[-1] for entry in sse_event["oneOf"]]
        assert refs == _SSE_EVENT_REFS

    def test_messages_endpoint_sse_response(self):
        schema = _get_fresh_schema()

        messages_post = schema["paths"][_MESSAGES_PATH]["post"]
        response_200 = messages_post["responses"]["200"]

        assert "text/event-stream" in response_200["content"]
        assert "SSE stream" in response_200["description"]
        # Response schema references the SSEEvent union
        sse_schema = response_200["content"]["text/event-stream"]["schema"]
        assert sse_schema == {"$ref": "#/components/schemas/SSEEvent"}

    def test_x_sse_events_extension(self):
        schema = _get_fresh_schema()

        messages_post = schema["paths"][_MESSAGES_PATH]["post"]
        x_sse_events = messages_post["x-sse-events"]

        assert x_sse_events == _SSE_EVENTS
        for event_name, event_spec in x_sse_events.items():
            assert "$ref" in event_spec, f"Event '{event_name}' missing $ref"
            assert "description" in event_spec, f"Event '{event_name}' missing description"

    def test_schema_is_cached(self):
        app.openapi_schema = None
        try:
            first = app.openapi()
            second = app.openapi()
            assert first is second
        finally:
            app.openapi_schema = None
