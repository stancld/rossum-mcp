"""Tests for the suggest_rule and evaluate_rules tools."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, Mock, patch

import httpx
from rossum_agent.tools.core import AgentContext, set_context
from rossum_agent.tools.python_helpers.copilot.rule import (
    _build_annotation_content_url,
    _build_annotation_url,
    _build_evaluate_rules_url,
    _build_queue_url,
    _build_suggest_rule_url,
    evaluate_rules,
    suggest_rule,
)


class TestBuildSuggestRuleUrl:
    def test_appends_internal_path(self) -> None:
        url = _build_suggest_rule_url("https://elis.rossum.ai/api/v1")
        assert url == "https://elis.rossum.ai/api/v1/internal/rules/suggest_rule"

    def test_handles_trailing_slash(self) -> None:
        url = _build_suggest_rule_url("https://elis.rossum.ai/api/v1/")
        assert url == "https://elis.rossum.ai/api/v1/internal/rules/suggest_rule"


class TestBuildQueueUrl:
    def test_builds_queue_url(self) -> None:
        url = _build_queue_url("https://elis.rossum.ai/api/v1", 2519495)
        assert url == "https://elis.rossum.ai/api/v1/queues/2519495"

    def test_handles_trailing_slash(self) -> None:
        url = _build_queue_url("https://elis.rossum.ai/api/v1/", 2519495)
        assert url == "https://elis.rossum.ai/api/v1/queues/2519495"


class TestBuildEvaluateRulesUrl:
    def test_appends_internal_path(self) -> None:
        url = _build_evaluate_rules_url("https://elis.rossum.ai/api/v1")
        assert url == "https://elis.rossum.ai/api/v1/internal/rules/evaluate_rules"

    def test_handles_trailing_slash(self) -> None:
        url = _build_evaluate_rules_url("https://elis.rossum.ai/api/v1/")
        assert url == "https://elis.rossum.ai/api/v1/internal/rules/evaluate_rules"


class TestBuildAnnotationUrls:
    def test_builds_annotation_url(self) -> None:
        url = _build_annotation_url("https://elis.rossum.ai/api/v1", 34532441)
        assert url == "https://elis.rossum.ai/api/v1/annotations/34532441"

    def test_builds_annotation_content_url(self) -> None:
        url = _build_annotation_content_url("https://elis.rossum.ai/api/v1", 34532441)
        assert url == "https://elis.rossum.ai/api/v1/annotations/34532441/content"


class TestSuggestRule:
    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.rule.httpx.Client")
    def test_successful_suggestion(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "name": "Total amount threshold",
                    "trigger_condition": "field.amount_total > 400",
                    "trigger_condition_summary": "Total exceeds 400",
                    "actions": [
                        {
                            "id": "total_too_high",
                            "type": "show_message",
                            "event": "validation",
                            "payload": {
                                "type": "error",
                                "content": "Total amount exceeds 400.",
                                "schema_id": "amount_total",
                            },
                        }
                    ],
                    "enabled": True,
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = suggest_rule(
            user_query="Show error when total amount exceeds 400",
            queue_id=123456,
        )

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["name"] == "Total amount threshold"
        assert parsed["trigger_condition"] == "field.amount_total > 400"
        assert parsed["trigger_condition_summary"] == "Total exceeds 400"
        assert len(parsed["actions"]) == 1
        assert parsed["actions"][0]["type"] == "show_message"
        assert parsed["enabled"] is True

        # Verify the API was called with queue URL, not schema_content
        call_kwargs = mock_client.post.call_args
        sent_payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert sent_payload["queue"] == "https://api.rossum.ai/v1/queues/123456"
        assert sent_payload["user_query"] == "Show error when total amount exceeds 400"
        assert "schema_content" not in sent_payload

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.rule.httpx.Client")
    def test_no_suggestions(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = suggest_rule(
            user_query="Some query",
            queue_id=123456,
        )

        parsed = json.loads(result)
        assert parsed["status"] == "no_suggestions"

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        set_context(AgentContext())
        result = suggest_rule(
            user_query="Some query",
            queue_id=123456,
        )

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "credentials not available" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.rule.httpx.Client")
    def test_http_error(self, mock_client_class: MagicMock) -> None:
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        http_error = httpx.HTTPStatusError("403", request=Mock(), response=mock_response)

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = http_error
        mock_client_class.return_value = mock_client

        result = suggest_rule(user_query="Some query", queue_id=123456)

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "HTTP 403" in parsed["error"]


class TestEvaluateRules:
    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.rule.httpx.Client")
    def test_successful_evaluation(self, mock_client_class: MagicMock) -> None:
        annotation_content = [{"schema_id": "amount_total", "value": "498.0"}]
        eval_result = {
            "messages": [],
            "condition_values": [[True]],
            "actions": [{"type": "show_message", "payload": {"type": "error", "content": "Total exceeds 400."}}],
        }

        mock_content_response = MagicMock()
        mock_content_response.json.return_value = {"results": annotation_content}
        mock_content_response.raise_for_status = MagicMock()

        mock_eval_response = MagicMock()
        mock_eval_response.json.return_value = eval_result

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_content_response
        mock_client.post.return_value = mock_eval_response
        mock_client_class.return_value = mock_client

        schema_rules = [
            {"name": "Total check", "trigger_condition": "field.amount_total >= 400", "actions": [], "enabled": True}
        ]
        result = evaluate_rules(queue_id=123456, annotation_id=34532441, schema_rules=schema_rules)

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["condition_values"] == [[True]]
        assert len(parsed["actions"]) == 1

        # Verify content was fetched from the right URL
        mock_client.get.assert_called_once()
        get_url = mock_client.get.call_args[0][0]
        assert "annotations/34532441/content" in get_url

        # Verify evaluate_rules was called with correct payload
        post_kwargs = mock_client.post.call_args.kwargs
        payload = post_kwargs.get("json") or mock_client.post.call_args[1].get("json")
        assert payload["queue"] == "https://api.rossum.ai/v1/queues/123456"
        assert payload["annotation"] == "https://api.rossum.ai/v1/annotations/34532441"
        assert payload["annotation_content"] == annotation_content
        assert payload["schema_rules"] == schema_rules

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.rule.httpx.Client")
    def test_annotation_content_is_list(self, mock_client_class: MagicMock) -> None:
        annotation_content = [{"schema_id": "amount_total", "value": "498.0"}]
        eval_result = {"condition_values": [[False]], "actions": [], "messages": []}

        mock_content_response = MagicMock()
        mock_content_response.json.return_value = annotation_content  # returns a list, not a dict
        mock_content_response.raise_for_status = MagicMock()

        mock_eval_response = MagicMock()
        mock_eval_response.json.return_value = eval_result

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_content_response
        mock_client.post.return_value = mock_eval_response
        mock_client_class.return_value = mock_client

        schema_rules = [{"name": "Check", "trigger_condition": "True", "actions": [], "enabled": True}]
        result = evaluate_rules(queue_id=123456, annotation_id=34532441, schema_rules=schema_rules)

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["condition_values"] == [[False]]

        post_kwargs = mock_client.post.call_args.kwargs
        payload = post_kwargs.get("json") or mock_client.post.call_args[1].get("json")
        assert payload["annotation_content"] == annotation_content

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        set_context(AgentContext())
        result = evaluate_rules(queue_id=123456, annotation_id=34532441, schema_rules=[])

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "credentials not available" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.rule.httpx.Client")
    def test_http_error_on_content_fetch(self, mock_client_class: MagicMock) -> None:
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        http_error = httpx.HTTPStatusError("404", request=Mock(), response=mock_response)

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = http_error
        mock_client_class.return_value = mock_client

        result = evaluate_rules(queue_id=123456, annotation_id=34532441, schema_rules=[])

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "HTTP 404" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.rule.httpx.Client")
    def test_http_error_on_evaluate_post(self, mock_client_class: MagicMock) -> None:
        mock_content_response = MagicMock()
        mock_content_response.json.return_value = {"results": []}
        mock_content_response.raise_for_status = MagicMock()

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        http_error = httpx.HTTPStatusError("500", request=Mock(), response=mock_response)

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_content_response
        mock_client.post.side_effect = http_error
        mock_client_class.return_value = mock_client

        result = evaluate_rules(queue_id=123456, annotation_id=34532441, schema_rules=[])

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "HTTP 500" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.rule.httpx.Client")
    def test_generic_error(self, mock_client_class: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = RuntimeError("connection failed")
        mock_client_class.return_value = mock_client

        result = evaluate_rules(queue_id=123456, annotation_id=34532441, schema_rules=[])

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "connection failed" in parsed["error"]
