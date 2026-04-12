"""Tests for the automation setup copilot helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, Mock, patch

import httpx
from rossum_agent.tools.core import AgentContext, set_context
from rossum_agent.tools.python_helpers.copilot.automation_setup import (
    _build_automation_targets_url,
    _build_current_stats_url,
    _build_projections_url,
    get_automation_current_stats,
    get_automation_projections,
    list_automation_targets,
    save_automation_target,
)


class TestBuildUrls:
    def test_current_stats_url(self) -> None:
        url = _build_current_stats_url("https://elis.rossum.ai/api/v1", 123)
        assert url == "https://elis.rossum.ai/api/v1/queues/123/automation_setup_current_stats"

    def test_current_stats_url_trailing_slash(self) -> None:
        url = _build_current_stats_url("https://elis.rossum.ai/api/v1/", 123)
        assert url == "https://elis.rossum.ai/api/v1/queues/123/automation_setup_current_stats"

    def test_projections_url(self) -> None:
        url = _build_projections_url("https://elis.rossum.ai/api/v1", 456)
        assert url == "https://elis.rossum.ai/api/v1/queues/456/automation_setup_projections"

    def test_projections_url_trailing_slash(self) -> None:
        url = _build_projections_url("https://elis.rossum.ai/api/v1/", 456)
        assert url == "https://elis.rossum.ai/api/v1/queues/456/automation_setup_projections"

    def test_automation_targets_url(self) -> None:
        url = _build_automation_targets_url("https://elis.rossum.ai/api/v1", 789)
        assert url == "https://elis.rossum.ai/api/v1/queues/789/automation_targets"

    def test_automation_targets_url_trailing_slash(self) -> None:
        url = _build_automation_targets_url("https://elis.rossum.ai/api/v1/", 789)
        assert url == "https://elis.rossum.ai/api/v1/queues/789/automation_targets"


class TestGetAutomationCurrentStats:
    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.automation_setup.httpx.Client")
    def test_success(self, mock_client_class: MagicMock) -> None:
        api_response = {
            "estimated_error_rate": 0.05,
            "document_automation_rate": 0.72,
            "document_touchless_rate": 0.65,
            "document_blockers": [{"blocker": "low_score", "granularity": "datapoint", "document_count": 50}],
            "datapoint_statistics": [],
        }
        mock_response = MagicMock()
        mock_response.json.return_value = api_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = get_automation_current_stats(queue_id=123)

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["document_automation_rate"] == 0.72
        assert parsed["document_touchless_rate"] == 0.65

        get_url = mock_client.get.call_args[0][0]
        assert "queues/123/automation_setup_current_stats" in get_url

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        set_context(AgentContext())
        result = get_automation_current_stats(queue_id=123)

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "credentials not available" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.automation_setup.httpx.Client")
    def test_http_error(self, mock_client_class: MagicMock) -> None:
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        http_error = httpx.HTTPStatusError("503", request=Mock(), response=mock_response)

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = http_error
        mock_client_class.return_value = mock_client

        result = get_automation_current_stats(queue_id=123)

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "HTTP 503" in parsed["error"]


class TestGetAutomationProjections:
    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.automation_setup.httpx.Client")
    def test_success(self, mock_client_class: MagicMock) -> None:
        api_response = {
            "total_document_count": 1000,
            "used_document_count": 800,
            "baseline": {"document_automation_rate": 0.5},
            "projections": [{"document_automation_rate": 0.7}],
        }
        mock_response = MagicMock()
        mock_response.json.return_value = api_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        fields = [{"schema_id": "invoice_id", "error_rate_limit": 0.05}]
        result = get_automation_projections(queue_id=123, fields=fields)

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["total_document_count"] == 1000
        assert len(parsed["projections"]) == 1

        call_kwargs = mock_client.post.call_args
        sent_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert sent_json == {"fields": fields}

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.automation_setup.httpx.Client")
    def test_with_exclude_blockers(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"baseline": {}, "projections": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        fields = [{"schema_id": "amount", "error_rate_limit": 0.1}]
        get_automation_projections(
            queue_id=123,
            fields=fields,
            exclude_blockers=["error_message", "extension"],
        )

        call_kwargs = mock_client.post.call_args
        sent_params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert sent_params == {"exclude_blockers": "error_message,extension"}

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.automation_setup.httpx.Client")
    def test_without_exclude_blockers_passes_none(self, mock_client_class: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"baseline": {}, "projections": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        fields = [{"schema_id": "date", "error_rate_limit": 0.02}]
        get_automation_projections(queue_id=123, fields=fields)

        call_kwargs = mock_client.post.call_args
        sent_params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert sent_params is None

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        set_context(AgentContext())
        result = get_automation_projections(queue_id=123, fields=[])

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "credentials not available" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.automation_setup.httpx.Client")
    def test_http_error(self, mock_client_class: MagicMock) -> None:
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        http_error = httpx.HTTPStatusError("400", request=Mock(), response=mock_response)

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = http_error
        mock_client_class.return_value = mock_client

        result = get_automation_projections(queue_id=123, fields=[])

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "HTTP 400" in parsed["error"]


class TestListAutomationTargets:
    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.automation_setup.httpx.Client")
    def test_success(self, mock_client_class: MagicMock) -> None:
        api_response = {
            "results": [
                {
                    "automation_rate_target": 0.8,
                    "error_rate_target": 0.05,
                    "type": "automation_assistant_v1",
                    "datetime": "2026-03-01T00:00:00Z",
                    "datapoint_automation_targets": [],
                }
            ]
        }
        mock_response = MagicMock()
        mock_response.json.return_value = api_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = list_automation_targets(queue_id=456)

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["automation_rate_target"] == 0.8

        get_url = mock_client.get.call_args[0][0]
        assert "queues/456/automation_targets" in get_url

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        set_context(AgentContext())
        result = list_automation_targets(queue_id=456)

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "credentials not available" in parsed["error"]


class TestSaveAutomationTarget:
    def test_read_only_mode_blocked(self) -> None:
        set_context(AgentContext(mcp_mode="read-only"))
        result = save_automation_target(
            queue_id=789,
            automation_rate_target=0.8,
            error_rate_target=0.05,
            datapoint_automation_targets=[],
        )

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "read-write mode" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.automation_setup.httpx.Client")
    def test_success(self, mock_client_class: MagicMock) -> None:
        set_context(AgentContext(mcp_mode="read-write"))
        api_response = {
            "automation_rate_target": 0.8,
            "error_rate_target": 0.05,
            "type": "automation_assistant_v1",
            "datetime": "2026-03-18T12:00:00Z",
            "datapoint_automation_targets": [
                {"schema_id": "invoice_id", "error_rate_target": 0.03, "confidence_threshold": 0.9}
            ],
        }
        mock_response = MagicMock()
        mock_response.json.return_value = api_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        datapoint_targets = [{"schema_id": "invoice_id", "error_rate_target": 0.03, "confidence_threshold": 0.9}]
        result = save_automation_target(
            queue_id=789,
            automation_rate_target=0.8,
            error_rate_target=0.05,
            datapoint_automation_targets=datapoint_targets,
        )

        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["automation_rate_target"] == 0.8

        call_kwargs = mock_client.post.call_args
        sent_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert sent_json["automation_rate_target"] == 0.8
        assert sent_json["error_rate_target"] == 0.05
        assert sent_json["type"] == "automation_assistant_v1"
        assert sent_json["datapoint_automation_targets"] == datapoint_targets

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.automation_setup.httpx.Client")
    def test_legacy_thresholds_type(self, mock_client_class: MagicMock) -> None:
        set_context(AgentContext(mcp_mode="read-write"))
        mock_response = MagicMock()
        mock_response.json.return_value = {"type": "legacy_thresholds"}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        save_automation_target(
            queue_id=789,
            automation_rate_target=0.5,
            error_rate_target=0.1,
            datapoint_automation_targets=[],
            target_type="legacy_thresholds",
        )

        call_kwargs = mock_client.post.call_args
        sent_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert sent_json["type"] == "legacy_thresholds"

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials(self) -> None:
        set_context(AgentContext(mcp_mode="read-write"))
        result = save_automation_target(
            queue_id=789,
            automation_rate_target=0.8,
            error_rate_target=0.05,
            datapoint_automation_targets=[],
        )

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "credentials not available" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.automation_setup.httpx.Client")
    def test_http_error(self, mock_client_class: MagicMock) -> None:
        set_context(AgentContext(mcp_mode="read-write"))
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        http_error = httpx.HTTPStatusError("403", request=Mock(), response=mock_response)

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = http_error
        mock_client_class.return_value = mock_client

        result = save_automation_target(
            queue_id=789,
            automation_rate_target=0.8,
            error_rate_target=0.05,
            datapoint_automation_targets=[],
        )

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "HTTP 403" in parsed["error"]

    @patch.dict("os.environ", {"ROSSUM_API_BASE_URL": "https://api.rossum.ai/v1", "ROSSUM_API_TOKEN": "test_token"})
    @patch("rossum_agent.tools.python_helpers.copilot.automation_setup.httpx.Client")
    def test_generic_error(self, mock_client_class: MagicMock) -> None:
        set_context(AgentContext(mcp_mode="read-write"))
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = RuntimeError("connection failed")
        mock_client_class.return_value = mock_client

        result = save_automation_target(
            queue_id=789,
            automation_rate_target=0.8,
            error_rate_target=0.05,
            datapoint_automation_targets=[],
        )

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "connection failed" in parsed["error"]
