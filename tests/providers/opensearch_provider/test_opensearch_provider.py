"""
Unit tests for the OpenSearch provider.

Tests cover:
  - Config validation (url, username/password, api_key)
  - Auth header generation (Basic Auth vs API key)
  - Pull mode: _alert_to_dto, _get_alerts
  - Push mode: _format_alert (webhook)
  - Query mode: _query, _run_dsl_query, _run_sql_query
  - STATUS_MAP and SEVERITY_MAP completeness
  - validate_scopes (cluster_read, alerting_read)
  - Edge cases: missing fields, unknown state/severity, empty results
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.opensearch_provider.opensearch_provider import (
    OpenSearchProvider,
    OpenSearchProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    url: str = "https://opensearch.example.com:9200",
    username: str = "admin",
    password: str = "admin",
    api_key: str = None,
    verify_ssl: bool = True,
) -> OpenSearchProvider:
    """Build an OpenSearchProvider with the given config."""
    auth = {
        "url": url,
        "username": username,
        "password": password,
        "verify_ssl": verify_ssl,
    }
    if api_key is not None:
        auth["api_key"] = api_key
    config = ProviderConfig(authentication=auth)
    ctx = ContextManager(tenant_id="test-tenant", workflow_id="test-workflow")
    return OpenSearchProvider(ctx, "opensearch-test", config)


def _active_alert() -> dict:
    """Simulate an OpenSearch Alerting alert in ACTIVE state."""
    return {
        "id": "alert-001",
        "monitor_id": "monitor-aaa",
        "monitor_name": "High CPU Monitor",
        "trigger_id": "trigger-bbb",
        "trigger_name": "CPU > 90%",
        "state": "ACTIVE",
        "severity": "1",
        "error_message": "",
        "start_time": "2026-03-28T10:00:00Z",
        "end_time": None,
    }


def _acknowledged_alert() -> dict:
    return {
        "id": "alert-002",
        "monitor_id": "monitor-ccc",
        "monitor_name": "Disk Space Monitor",
        "trigger_id": "trigger-ddd",
        "trigger_name": "Disk > 80%",
        "state": "ACKNOWLEDGED",
        "severity": "2",
        "error_message": "Disk usage exceeded threshold",
        "start_time": "2026-03-28T09:00:00Z",
        "end_time": None,
    }


def _completed_alert() -> dict:
    return {
        "id": "alert-003",
        "monitor_id": "monitor-eee",
        "monitor_name": "Memory Monitor",
        "trigger_id": "trigger-fff",
        "trigger_name": "Memory > 95%",
        "state": "COMPLETED",
        "severity": "3",
        "error_message": "",
        "start_time": "2026-03-27T08:00:00Z",
        "end_time": "2026-03-27T09:00:00Z",
    }


def _webhook_event() -> dict:
    """Simulate an OpenSearch Alerting webhook payload."""
    return {
        "id": "monitor-001",
        "name": "Error Rate Monitor",
        "trigger_name": "Error Rate > 5%",
        "severity": "2",
        "state": "active",
        "message": "Error rate has exceeded threshold of 5%",
        "index": "application-logs-*",
        "timestamp": "2026-03-28T11:00:00Z",
    }


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestOpenSearchProviderConfig:
    def test_valid_basic_auth_config(self):
        provider = _make_provider(username="admin", password="secret")
        assert provider.authentication_config.username == "admin"
        assert provider.authentication_config.password == "secret"
        assert provider.authentication_config.api_key is None

    def test_valid_api_key_config(self):
        provider = _make_provider(username=None, password=None, api_key="test-key-123")
        assert provider.authentication_config.api_key == "test-key-123"

    def test_missing_credentials_raises(self):
        config = ProviderConfig(
            authentication={
                "url": "https://opensearch.example.com",
                "username": None,
                "password": None,
                "api_key": None,
            }
        )
        ctx = ContextManager(tenant_id="test", workflow_id="test")
        provider = OpenSearchProvider(ctx, "test", config)
        with pytest.raises(ValueError, match="username.password or api_key"):
            provider.validate_config()

    def test_url_stored_correctly(self):
        provider = _make_provider(url="https://my-opensearch.corp.com:9200")
        assert "my-opensearch.corp.com" in str(provider.authentication_config.url)

    def test_verify_ssl_default_true(self):
        provider = _make_provider()
        assert provider.authentication_config.verify_ssl is True

    def test_verify_ssl_can_be_false(self):
        provider = _make_provider(verify_ssl=False)
        assert provider.authentication_config.verify_ssl is False


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------


class TestAuthHeaders:
    def test_basic_auth_returns_authorization_header(self):
        import base64
        provider = _make_provider(username="user", password="pass")
        headers = provider._get_auth_headers()
        assert "Authorization" in headers
        expected = base64.b64encode(b"user:pass").decode()
        assert f"Basic {expected}" in headers["Authorization"]

    def test_api_key_returns_apikey_header(self):
        provider = _make_provider(username=None, password=None, api_key="my-api-key")
        headers = provider._get_auth_headers()
        assert "Authorization" in headers
        assert "ApiKey my-api-key" in headers["Authorization"]

    def test_api_key_takes_precedence_over_basic_auth(self):
        """When both api_key and username/password are set, api_key takes precedence."""
        provider = _make_provider(username="user", password="pass", api_key="my-api-key")
        headers = provider._get_auth_headers()
        assert "ApiKey" in headers["Authorization"]
        assert "Basic" not in headers["Authorization"]


# ---------------------------------------------------------------------------
# Pull mode: _alert_to_dto
# ---------------------------------------------------------------------------


class TestAlertToDto:
    def test_active_alert_fires(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_active_alert())
        assert dto.status == AlertStatus.FIRING
        assert dto.severity == AlertSeverity.CRITICAL  # severity "1" = CRITICAL

    def test_acknowledged_alert_acknowledged(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_acknowledged_alert())
        assert dto.status == AlertStatus.ACKNOWLEDGED
        assert dto.severity == AlertSeverity.HIGH  # severity "2" = HIGH

    def test_completed_alert_resolved(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_completed_alert())
        assert dto.status == AlertStatus.RESOLVED
        assert dto.severity == AlertSeverity.WARNING  # severity "3" = WARNING

    def test_id_preserved(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_active_alert())
        assert dto.id == "alert-001"

    def test_name_combines_monitor_and_trigger(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_active_alert())
        assert "High CPU Monitor" in dto.name
        assert "CPU > 90%" in dto.name

    def test_name_without_trigger(self):
        provider = _make_provider()
        alert = _active_alert()
        del alert["trigger_name"]
        dto = provider._alert_to_dto(alert)
        assert dto.name == "High CPU Monitor"

    def test_source_is_opensearch(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_active_alert())
        assert "opensearch" in dto.source

    def test_service_is_monitor_name(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_active_alert())
        assert dto.service == "High CPU Monitor"

    def test_last_received_from_start_time_when_no_end_time(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_active_alert())
        assert "2026-03-28" in str(dto.lastReceived)

    def test_last_received_from_end_time_when_resolved(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_completed_alert())
        assert "2026-03-27" in str(dto.lastReceived)

    def test_labels_include_monitor_and_trigger(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_active_alert())
        assert dto.labels["monitor_name"] == "High CPU Monitor"
        assert dto.labels["trigger_name"] == "CPU > 90%"
        assert dto.labels["monitor_id"] == "monitor-aaa"
        assert dto.labels["trigger_id"] == "trigger-bbb"

    def test_description_from_error_message(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_acknowledged_alert())
        assert "Disk usage exceeded threshold" in dto.description

    def test_description_fallback_when_no_error_message(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_active_alert())
        assert "High CPU Monitor" in dto.description


# ---------------------------------------------------------------------------
# Pull mode: _get_alerts
# ---------------------------------------------------------------------------


class TestGetAlerts:
    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.get")
    def test_returns_list_of_alert_dtos(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "alerts": [_active_alert(), _acknowledged_alert()]
        }
        mock_get.return_value = mock_resp

        provider = _make_provider()
        alerts = provider._get_alerts()

        assert len(alerts) == 2
        assert all(isinstance(a, AlertDto) for a in alerts)

    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.get")
    def test_empty_alerts_returns_empty_list(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"alerts": []}
        mock_get.return_value = mock_resp

        provider = _make_provider()
        alerts = provider._get_alerts()
        assert alerts == []

    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.get")
    def test_url_contains_alerting_plugin_path(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"alerts": []}
        mock_get.return_value = mock_resp

        provider = _make_provider()
        provider._get_alerts()

        call_url = mock_get.call_args[0][0]
        assert "_plugins/_alerting/alerts" in call_url

    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.get")
    def test_get_alerts_raises_on_http_error(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.HTTPError("500 Internal Server Error")

        provider = _make_provider()
        with pytest.raises(req_lib.exceptions.HTTPError):
            provider._get_alerts()


# ---------------------------------------------------------------------------
# Query mode
# ---------------------------------------------------------------------------


class TestQueryMode:
    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.post")
    def test_dsl_query_with_index_returns_hits(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "hits": {
                "hits": [
                    {"_id": "1", "_source": {"message": "error occurred", "level": "ERROR"}},
                    {"_id": "2", "_source": {"message": "another error", "level": "CRITICAL"}},
                ]
            }
        }
        mock_post.return_value = mock_resp

        provider = _make_provider()
        results = provider._query(
            query={"query": {"match": {"level": "ERROR"}}},
            index="application-logs-*"
        )

        assert len(results) == 2

    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.post")
    def test_sql_query_without_index_returns_rows(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "schema": [{"name": "level"}, {"name": "count"}],
            "datarows": [["ERROR", 42], ["WARN", 15]],
        }
        mock_post.return_value = mock_resp

        provider = _make_provider()
        results = provider._query(query="SELECT level, count(*) FROM logs GROUP BY level")

        assert len(results) == 2
        assert results[0]["level"] == "ERROR"
        assert results[0]["count"] == 42

    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.post")
    def test_dsl_query_url_contains_search_endpoint(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"hits": {"hits": []}}
        mock_post.return_value = mock_resp

        provider = _make_provider()
        provider._run_dsl_query(
            query={"query": {"match_all": {}}},
            index="my-index"
        )

        call_url = mock_post.call_args[0][0]
        assert "my-index/_search" in call_url

    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.post")
    def test_sql_query_url_contains_sql_endpoint(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"schema": [], "datarows": []}
        mock_post.return_value = mock_resp

        provider = _make_provider()
        provider._run_sql_query(query="SELECT * FROM logs LIMIT 10")

        call_url = mock_post.call_args[0][0]
        assert "_plugins/_sql" in call_url

    def test_dsl_query_invalid_json_string_raises(self):
        provider = _make_provider()
        with pytest.raises(ValueError, match="Invalid DSL query JSON"):
            provider._run_dsl_query(query="not valid json", index="test")

    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.post")
    def test_dsl_query_accepts_string_json(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"hits": {"hits": []}}
        mock_post.return_value = mock_resp

        provider = _make_provider()
        results = provider._run_dsl_query(
            query='{"query": {"match_all": {}}}',
            index="my-index"
        )
        assert results == []


# ---------------------------------------------------------------------------
# Push mode: _format_alert (webhook)
# ---------------------------------------------------------------------------


class TestFormatAlert:
    def test_active_event_fires(self):
        dto = OpenSearchProvider._format_alert(_webhook_event())
        assert dto.status == AlertStatus.FIRING
        assert dto.severity == AlertSeverity.HIGH  # severity "2" = HIGH

    def test_name_combines_monitor_and_trigger(self):
        dto = OpenSearchProvider._format_alert(_webhook_event())
        assert "Error Rate Monitor" in dto.name
        assert "Error Rate > 5%" in dto.name

    def test_description_from_message(self):
        dto = OpenSearchProvider._format_alert(_webhook_event())
        assert "Error rate has exceeded" in dto.description

    def test_source_is_opensearch(self):
        dto = OpenSearchProvider._format_alert(_webhook_event())
        assert "opensearch" in dto.source

    def test_service_is_monitor_name(self):
        dto = OpenSearchProvider._format_alert(_webhook_event())
        assert dto.service == "Error Rate Monitor"

    def test_id_from_event(self):
        dto = OpenSearchProvider._format_alert(_webhook_event())
        assert dto.id == "monitor-001"

    def test_timestamp_preserved(self):
        dto = OpenSearchProvider._format_alert(_webhook_event())
        assert "2026-03-28" in str(dto.lastReceived)

    def test_labels_include_trigger_and_index(self):
        dto = OpenSearchProvider._format_alert(_webhook_event())
        assert dto.labels["trigger_name"] == "Error Rate > 5%"
        assert dto.labels["index"] == "application-logs-*"
        assert dto.labels["severity"] == "2"

    def test_completed_state_resolves(self):
        event = dict(_webhook_event())
        event["state"] = "completed"
        dto = OpenSearchProvider._format_alert(event)
        assert dto.status == AlertStatus.RESOLVED

    def test_acknowledged_state_acknowledged(self):
        event = dict(_webhook_event())
        event["state"] = "acknowledged"
        dto = OpenSearchProvider._format_alert(event)
        assert dto.status == AlertStatus.ACKNOWLEDGED

    def test_named_severity_critical(self):
        event = dict(_webhook_event())
        event["severity"] = "critical"
        dto = OpenSearchProvider._format_alert(event)
        assert dto.severity == AlertSeverity.CRITICAL

    def test_named_severity_medium_maps_warning(self):
        event = dict(_webhook_event())
        event["severity"] = "medium"
        dto = OpenSearchProvider._format_alert(event)
        assert dto.severity == AlertSeverity.WARNING

    def test_unknown_state_defaults_to_firing(self):
        event = dict(_webhook_event())
        event["state"] = "some_unknown_state"
        dto = OpenSearchProvider._format_alert(event)
        assert dto.status == AlertStatus.FIRING

    def test_missing_id_uses_monitor_id(self):
        event = dict(_webhook_event())
        del event["id"]
        event["monitor_id"] = "mon-xyz"
        dto = OpenSearchProvider._format_alert(event)
        assert "mon-xyz" in dto.id

    def test_missing_message_uses_fallback_description(self):
        event = dict(_webhook_event())
        del event["message"]
        dto = OpenSearchProvider._format_alert(event)
        assert "Error Rate Monitor" in dto.description


# ---------------------------------------------------------------------------
# STATUS_MAP and SEVERITY_MAP completeness
# ---------------------------------------------------------------------------


class TestMapsCompleteness:
    def test_status_map_active(self):
        assert OpenSearchProvider.STATUS_MAP["active"] == AlertStatus.FIRING

    def test_status_map_acknowledged(self):
        assert OpenSearchProvider.STATUS_MAP["acknowledged"] == AlertStatus.ACKNOWLEDGED

    def test_status_map_completed(self):
        assert OpenSearchProvider.STATUS_MAP["completed"] == AlertStatus.RESOLVED

    def test_status_map_deleted(self):
        assert OpenSearchProvider.STATUS_MAP["deleted"] == AlertStatus.RESOLVED

    def test_status_map_error(self):
        assert OpenSearchProvider.STATUS_MAP["error"] == AlertStatus.FIRING

    def test_severity_map_numeric_1_critical(self):
        assert OpenSearchProvider.SEVERITY_MAP["1"] == AlertSeverity.CRITICAL

    def test_severity_map_numeric_2_high(self):
        assert OpenSearchProvider.SEVERITY_MAP["2"] == AlertSeverity.HIGH

    def test_severity_map_numeric_3_warning(self):
        assert OpenSearchProvider.SEVERITY_MAP["3"] == AlertSeverity.WARNING

    def test_severity_map_numeric_4_info(self):
        assert OpenSearchProvider.SEVERITY_MAP["4"] == AlertSeverity.INFO

    def test_severity_map_numeric_5_low(self):
        assert OpenSearchProvider.SEVERITY_MAP["5"] == AlertSeverity.LOW

    def test_severity_map_named_critical(self):
        assert OpenSearchProvider.SEVERITY_MAP["critical"] == AlertSeverity.CRITICAL

    def test_severity_map_named_high(self):
        assert OpenSearchProvider.SEVERITY_MAP["high"] == AlertSeverity.HIGH

    def test_severity_map_named_medium(self):
        assert OpenSearchProvider.SEVERITY_MAP["medium"] == AlertSeverity.WARNING

    def test_severity_map_named_warning(self):
        assert OpenSearchProvider.SEVERITY_MAP["warning"] == AlertSeverity.WARNING

    def test_severity_map_named_info(self):
        assert OpenSearchProvider.SEVERITY_MAP["info"] == AlertSeverity.INFO

    def test_severity_map_named_low(self):
        assert OpenSearchProvider.SEVERITY_MAP["low"] == AlertSeverity.LOW


# ---------------------------------------------------------------------------
# validate_scopes
# ---------------------------------------------------------------------------


class TestValidateScopes:
    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.get")
    def test_valid_cluster_read_returns_true(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"cluster_name": "opensearch-test", "version": {}}
        mock_get.return_value = mock_resp

        provider = _make_provider()
        result = provider.validate_scopes()
        assert result["cluster_read"] is True

    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.get")
    def test_http_error_returns_error_string(self, mock_get):
        import requests as req_lib

        err_resp = MagicMock()
        err_resp.status_code = 401
        exc = req_lib.exceptions.HTTPError("401 Unauthorized")
        exc.response = err_resp
        mock_get.side_effect = exc

        provider = _make_provider()
        result = provider.validate_scopes()
        assert result["cluster_read"] is not True
        assert "401" in str(result["cluster_read"]) or "Unauthorized" in str(result["cluster_read"])

    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.get")
    def test_alerting_plugin_returns_true_when_accessible(self, mock_get):
        """Both cluster and alerting checks succeed."""
        def side_effect(url, *args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            if "alerting" in url:
                mock_resp.json.return_value = {"alerts": [], "totalAlerts": 0}
            else:
                mock_resp.json.return_value = {"cluster_name": "test-cluster"}
            return mock_resp

        mock_get.side_effect = side_effect
        provider = _make_provider()
        result = provider.validate_scopes()
        assert result["cluster_read"] is True
        assert result["alerting_read"] is True

    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.get")
    def test_alerting_plugin_not_installed_returns_error(self, mock_get):
        """Alerting plugin returns 404 — scope should show error string."""
        import requests as req_lib

        call_count = [0]

        def side_effect(url, *args, **kwargs):
            call_count[0] += 1
            mock_resp = MagicMock()
            if "alerting" in url:
                err_resp = MagicMock()
                err_resp.status_code = 404
                exc = req_lib.exceptions.HTTPError("404 Not Found")
                exc.response = err_resp
                raise exc
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"cluster_name": "test"}
            return mock_resp

        mock_get.side_effect = side_effect
        provider = _make_provider()
        result = provider.validate_scopes()
        assert result["cluster_read"] is True
        assert "not installed" in str(result["alerting_read"]).lower() or result["alerting_read"] is not True

    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.get")
    def test_validate_scopes_uses_root_endpoint_for_cluster_check(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {}
        mock_get.return_value = mock_resp

        provider = _make_provider()
        provider.validate_scopes()

        # First call should be to root endpoint
        first_call_url = mock_get.call_args_list[0][0][0]
        # Should end with just '/' or cluster root
        assert first_call_url.endswith("/") or "_cluster" in first_call_url or first_call_url.endswith(":9200/")

    @patch("keep.providers.opensearch_provider.opensearch_provider.requests.get")
    def test_validate_scopes_uses_ssl_setting(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {}
        mock_get.return_value = mock_resp

        provider = _make_provider(verify_ssl=False)
        provider.validate_scopes()

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("verify") is False
