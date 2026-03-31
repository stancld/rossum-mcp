"""Tests for OpenAPI schema generation."""

from __future__ import annotations

from rossum_agent.api.main import app


def _get_fresh_schema() -> dict:
    app.openapi_schema = None
    try:
        return app.openapi()
    finally:
        app.openapi_schema = None


class TestOpenAPISchema:
    def test_messages_endpoint_exists(self):
        schema = _get_fresh_schema()
        messages_path = "/api/v1/chats/{chat_id}/messages"
        assert messages_path in schema["paths"]
        assert "post" in schema["paths"][messages_path]

    def test_schema_is_cached(self):
        app.openapi_schema = None
        try:
            first = app.openapi()
            second = app.openapi()
            assert first is second
        finally:
            app.openapi_schema = None

    def test_health_endpoint_exists(self):
        schema = _get_fresh_schema()
        assert "/api/v1/health" in schema["paths"]

    def test_chats_endpoint_exists(self):
        schema = _get_fresh_schema()
        assert "/api/v1/chats" in schema["paths"]
