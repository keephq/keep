"""
Unit tests for the Cribl provider.

Tests cover:
  - validate_config: all optional fields default correctly
  - validate_config: api_key is accepted
  - validate_config: username/password are accepted
  - validate_config: worker_group defaults to "default"
  - _get_auth_headers: uses api_key when present
  - _get_auth_headers: calls _login when no api_key and no cached token
  - _login: stores and returns token
  - validate_scopes: 200 returns True
  - validate_scopes: no api_url returns error string
  - validate_scopes: HTTP error returns error string
  - validate_scopes: connection error returns error string
  - _format_single_event: single log event mapping
  - _format_single_event: infrastructure alert (critical severity)
  - _format_single_event: resolved/cleared status
  - _format_single_event: severity debug maps to LOW
  - _format_single_event: severity warning maps to WARNING
  - _format_single_event: unix timestamp in seconds
  - _format_single_event: unix timestamp in milliseconds
  - _format_single_event: name fallback chain (title -> source -> _raw)
  - _format_single_event: description fallback chain (message -> msg -> _raw)
  - _format_single_event: source is always ["cribl"]
  - _format_single_event: labels include known fields
  - _format_single_event: id fallback to hash
  - _format_single_event: empty event returns None
  - _format_alert: single event object
  - _format_alert: array of events (batch)
  - _format_alert: wrapped object with "events" key
  - _format_alert: wrapped object with "results" key
  - _format_alert: wrapped object with "records" key
  - _format_alert: wrapped object with "items" key
  - _format_alert: unknown/empty object falls back gracefully
  - _get_alerts: no api_url returns empty list
  - _get_alerts: worker health with unhealthy worker creates alert
  - _get_alerts: worker health with ok status skips
  - _get_alerts: pipeline jobs with failed status creates alert
  - _get_alerts: pipeline jobs with ok status skips
  - _get_alerts: worker health API error is logged and skipped
  - _get_alerts: pipeline jobs API error is logged and skipped
  - SEVERITY_MAP completeness
  - STATUS_MAP completeness
  - Provider metadata: PROVIDER_DISPLAY_NAME, PROVIDER_CATEGORY, PROVIDER_TAGS
  - webhook_markdown contains placeholder text
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.cribl_provider.alerts_mock import (
    CRIBL_BATCH_EVENTS,
    CRIBL_INFRA_ALERT,
    CRIBL_MINIMAL_RAW_EVENT,
    CRIBL_RESOLVED_EVENT,
    CRIBL_SINGLE_LOG_EVENT,
    CRIBL_WRAPPED_EVENTS,
)
from keep.providers.cribl_provider.cribl_provider import (
    CriblProvider,
    CriblProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    api_url: str = "",
    api_key: str = "",
    username: str = "",
    password: str = "",
    worker_group: str = "default",
) -> CriblProvider:
    auth: dict = {
        "api_url": api_url,
        "api_key": api_key,
        "username": username,
        "password": password,
        "worker_group": worker_group,
    }
    config = ProviderConfig(authentication=auth)
    ctx = ContextManager(tenant_id="test-tenant", workflow_id="test-wf")
    return CriblProvider(ctx, "cribl-test", config)


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


def test_validate_config_defaults():
    provider = _make_provider()
    cfg = provider.authentication_config
    assert cfg.api_url == ""
    assert cfg.api_key == ""
    assert cfg.username == ""
    assert cfg.password == ""
    assert cfg.worker_group == "default"


def test_validate_config_with_api_key():
    provider = _make_provider(
        api_url="https://cribl.example.com", api_key="tok123"
    )
    cfg = provider.authentication_config
    assert cfg.api_key == "tok123"
    assert str(cfg.api_url) == "https://cribl.example.com"


def test_validate_config_username_password():
    provider = _make_provider(username="test-user", password="test-placeholder")  # noqa: S106
    cfg = provider.authentication_config
    assert cfg.username == "test-user"
    assert cfg.password == "test-placeholder"


def test_validate_config_worker_group_custom():
    provider = _make_provider(worker_group="us-west")
    assert provider.authentication_config.worker_group == "us-west"


# ---------------------------------------------------------------------------
# _get_auth_headers
# ---------------------------------------------------------------------------


def test_get_auth_headers_api_key():
    provider = _make_provider(api_key="bearer-tok")
    headers = provider._get_auth_headers()
    assert headers["Authorization"] == "Bearer bearer-tok"


def test_get_auth_headers_calls_login_when_no_api_key():
    provider = _make_provider(username="test-user", password="test-placeholder")  # noqa: S106
    with patch.object(provider, "_login", return_value="login-tok") as mock_login:
        headers = provider._get_auth_headers()
    mock_login.assert_called_once()
    assert headers["Authorization"] == "Bearer login-tok"


def test_get_auth_headers_uses_cached_token():
    provider = _make_provider(username="test-user", password="test-placeholder")  # noqa: S106
    provider._access_token = "cached-tok"
    with patch.object(provider, "_login") as mock_login:
        headers = provider._get_auth_headers()
    mock_login.assert_not_called()
    assert headers["Authorization"] == "Bearer cached-tok"


# ---------------------------------------------------------------------------
# _login
# ---------------------------------------------------------------------------


def test_login_stores_token():
    provider = _make_provider(
        api_url="https://cribl.example.com",
        username="test-user",
        password="test-placeholder",  # noqa: S106
    )
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"token": "login-jwt"}
    mock_resp.raise_for_status = MagicMock()
    with patch("requests.post", return_value=mock_resp) as mock_post:
        token = provider._login()
    assert token == "login-jwt"
    assert provider._access_token == "login-jwt"
    mock_post.assert_called_once()


# ---------------------------------------------------------------------------
# validate_scopes
# ---------------------------------------------------------------------------


def test_validate_scopes_no_api_url():
    provider = _make_provider()
    result = provider.validate_scopes()
    assert result["system:read"] != True
    assert "api_url" in str(result["system:read"])


def test_validate_scopes_success():
    provider = _make_provider(
        api_url="https://cribl.example.com", api_key="tok"
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("requests.get", return_value=mock_resp):
        result = provider.validate_scopes()
    assert result["system:read"] is True


def test_validate_scopes_http_403():
    provider = _make_provider(
        api_url="https://cribl.example.com", api_key="bad-tok"
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Forbidden"
    with patch("requests.get", return_value=mock_resp):
        result = provider.validate_scopes()
    assert "403" in str(result["system:read"])


def test_validate_scopes_connection_error():
    provider = _make_provider(
        api_url="https://cribl.example.com", api_key="tok"
    )
    with patch("requests.get", side_effect=requests.ConnectionError("refused")):
        result = provider.validate_scopes()
    assert "refused" in str(result["system:read"])


# ---------------------------------------------------------------------------
# _format_single_event
# ---------------------------------------------------------------------------


def test_format_single_event_log_event():
    dto = CriblProvider._format_single_event(CRIBL_SINGLE_LOG_EVENT)
    assert dto is not None
    assert isinstance(dto, AlertDto)
    assert dto.id == "evt-001"
    assert dto.name == "High error rate detected"
    assert dto.severity == AlertSeverity.HIGH  # "error" -> HIGH
    assert dto.status == AlertStatus.FIRING
    assert dto.source == ["cribl"]


def test_format_single_event_critical_infra_alert():
    dto = CriblProvider._format_single_event(CRIBL_INFRA_ALERT)
    assert dto is not None
    assert dto.severity == AlertSeverity.CRITICAL
    assert dto.status == AlertStatus.FIRING  # "active" -> FIRING


def test_format_single_event_resolved():
    dto = CriblProvider._format_single_event(CRIBL_RESOLVED_EVENT)
    assert dto is not None
    assert dto.status == AlertStatus.RESOLVED  # "cleared" -> RESOLVED
    assert dto.severity == AlertSeverity.INFO


def test_format_single_event_warning_severity():
    event = {**CRIBL_BATCH_EVENTS[0]}  # CPU spike - warning
    dto = CriblProvider._format_single_event(event)
    assert dto.severity == AlertSeverity.WARNING


def test_format_single_event_debug_severity():
    event = {"id": "dbg-1", "name": "Debug event", "severity": "debug"}
    dto = CriblProvider._format_single_event(event)
    assert dto.severity == AlertSeverity.LOW


def test_format_single_event_unix_timestamp_seconds():
    event = {"id": "ts-1", "name": "TS test", "timestamp": 1700000000}
    dto = CriblProvider._format_single_event(event)
    assert dto is not None
    assert "2023" in dto.lastReceived  # Unix 1700000000 is in 2023


def test_format_single_event_unix_timestamp_milliseconds():
    event = {"id": "ts-ms-1", "name": "TS ms test", "timestamp": 1700000000000}
    dto = CriblProvider._format_single_event(event)
    assert dto is not None
    assert "2023" in dto.lastReceived


def test_format_single_event_name_fallback_title():
    event = {"id": "n-1", "title": "Title fallback"}
    dto = CriblProvider._format_single_event(event)
    assert dto.name == "Title fallback"


def test_format_single_event_name_fallback_source():
    event = {"id": "n-2", "source": "source-fallback"}
    dto = CriblProvider._format_single_event(event)
    assert dto.name == "source-fallback"


def test_format_single_event_name_fallback_raw():
    event = {"_raw": "this is a raw log line that is very long exceeds 80 chars " + "x" * 50}
    dto = CriblProvider._format_single_event(event)
    assert len(dto.name) <= 80


def test_format_single_event_description_from_message():
    event = {"id": "d-1", "name": "test", "message": "msg content"}
    dto = CriblProvider._format_single_event(event)
    assert dto.description == "msg content"


def test_format_single_event_description_from_msg():
    event = {"id": "d-2", "name": "test", "msg": "short msg"}
    dto = CriblProvider._format_single_event(event)
    assert dto.description == "short msg"


def test_format_single_event_source_always_cribl():
    dto = CriblProvider._format_single_event(CRIBL_SINGLE_LOG_EVENT)
    assert dto.source == ["cribl"]


def test_format_single_event_labels_include_host():
    dto = CriblProvider._format_single_event(CRIBL_SINGLE_LOG_EVENT)
    assert "host" in dto.labels
    assert dto.labels["host"] == "web-01.example.com"


def test_format_single_event_labels_include_pipeline():
    dto = CriblProvider._format_single_event(CRIBL_SINGLE_LOG_EVENT)
    assert "pipeline" in dto.labels
    assert dto.labels["pipeline"] == "error-detector"


def test_format_single_event_id_fallback_hash():
    event = {"name": "no id event", "severity": "info"}
    dto = CriblProvider._format_single_event(event)
    assert dto is not None
    assert dto.id is not None
    assert len(dto.id) > 0


def test_format_single_event_empty_returns_none():
    result = CriblProvider._format_single_event({})
    assert result is None


# ---------------------------------------------------------------------------
# _format_alert
# ---------------------------------------------------------------------------


def test_format_alert_single_event():
    result = CriblProvider._format_alert(CRIBL_SINGLE_LOG_EVENT)
    assert isinstance(result, AlertDto)
    assert result.id == "evt-001"


def test_format_alert_batch_array():
    result = CriblProvider._format_alert(CRIBL_BATCH_EVENTS)
    assert isinstance(result, list)
    assert len(result) == 3


def test_format_alert_wrapped_events_key():
    result = CriblProvider._format_alert(CRIBL_WRAPPED_EVENTS)
    assert isinstance(result, list)
    assert len(result) == 2


def test_format_alert_wrapped_results_key():
    payload = {"results": list(CRIBL_BATCH_EVENTS)}
    result = CriblProvider._format_alert(payload)
    assert isinstance(result, list)
    assert len(result) == 3


def test_format_alert_wrapped_records_key():
    payload = {"records": [CRIBL_SINGLE_LOG_EVENT]}
    result = CriblProvider._format_alert(payload)
    assert isinstance(result, list)
    assert len(result) == 1


def test_format_alert_wrapped_items_key():
    payload = {"items": [CRIBL_INFRA_ALERT, CRIBL_RESOLVED_EVENT]}
    result = CriblProvider._format_alert(payload)
    assert isinstance(result, list)
    assert len(result) == 2


def test_format_alert_unknown_object_falls_back():
    result = CriblProvider._format_alert({"arbitrary": "key", "x": 1})
    assert result is not None


def test_format_alert_minimal_raw_event():
    result = CriblProvider._format_alert(CRIBL_MINIMAL_RAW_EVENT)
    assert isinstance(result, AlertDto)
    assert result.source == ["cribl"]


# ---------------------------------------------------------------------------
# _get_alerts (pull mode)
# ---------------------------------------------------------------------------


def test_get_alerts_no_api_url_returns_empty():
    provider = _make_provider()
    alerts = provider._get_alerts()
    assert alerts == []


def test_get_alerts_unhealthy_worker():
    provider = _make_provider(
        api_url="https://cribl.example.com", api_key="tok"
    )
    worker_resp = MagicMock()
    worker_resp.raise_for_status = MagicMock()
    worker_resp.json.return_value = [
        {"id": "w1", "hostname": "worker-1", "status": "error"}
    ]
    job_resp = MagicMock()
    job_resp.raise_for_status = MagicMock()
    job_resp.json.return_value = []

    with patch("requests.get", side_effect=[worker_resp, job_resp]):
        alerts = provider._get_alerts()

    assert len(alerts) >= 1
    assert any("unhealthy" in a.name.lower() for a in alerts)


def test_get_alerts_healthy_worker_skipped():
    provider = _make_provider(
        api_url="https://cribl.example.com", api_key="tok"
    )
    worker_resp = MagicMock()
    worker_resp.raise_for_status = MagicMock()
    worker_resp.json.return_value = [
        {"id": "w1", "hostname": "worker-1", "status": "running"}
    ]
    job_resp = MagicMock()
    job_resp.raise_for_status = MagicMock()
    job_resp.json.return_value = []

    with patch("requests.get", side_effect=[worker_resp, job_resp]):
        alerts = provider._get_alerts()

    assert len(alerts) == 0


def test_get_alerts_failed_pipeline_job():
    provider = _make_provider(
        api_url="https://cribl.example.com", api_key="tok"
    )
    worker_resp = MagicMock()
    worker_resp.raise_for_status = MagicMock()
    worker_resp.json.return_value = []

    job_resp = MagicMock()
    job_resp.raise_for_status = MagicMock()
    job_resp.json.return_value = [
        {"id": "job-1", "pipelineId": "error-pipeline", "status": "failed"}
    ]

    with patch("requests.get", side_effect=[worker_resp, job_resp]):
        alerts = provider._get_alerts()

    assert len(alerts) >= 1
    assert any("failed" in a.name.lower() for a in alerts)


def test_get_alerts_ok_pipeline_job_skipped():
    provider = _make_provider(
        api_url="https://cribl.example.com", api_key="tok"
    )
    worker_resp = MagicMock()
    worker_resp.raise_for_status = MagicMock()
    worker_resp.json.return_value = []

    job_resp = MagicMock()
    job_resp.raise_for_status = MagicMock()
    job_resp.json.return_value = [
        {"id": "job-ok", "pipelineId": "ok-pipeline", "status": "completed"}
    ]

    with patch("requests.get", side_effect=[worker_resp, job_resp]):
        alerts = provider._get_alerts()

    assert len(alerts) == 0


def test_get_alerts_worker_api_error_is_skipped():
    provider = _make_provider(
        api_url="https://cribl.example.com", api_key="tok"
    )
    job_resp = MagicMock()
    job_resp.raise_for_status = MagicMock()
    job_resp.json.return_value = []

    with patch(
        "requests.get",
        side_effect=[requests.ConnectionError("timeout"), job_resp],
    ):
        alerts = provider._get_alerts()

    assert isinstance(alerts, list)


def test_get_alerts_pipeline_api_error_is_skipped():
    provider = _make_provider(
        api_url="https://cribl.example.com", api_key="tok"
    )
    worker_resp = MagicMock()
    worker_resp.raise_for_status = MagicMock()
    worker_resp.json.return_value = []

    with patch(
        "requests.get",
        side_effect=[worker_resp, requests.ConnectionError("timeout")],
    ):
        alerts = provider._get_alerts()

    assert isinstance(alerts, list)


# ---------------------------------------------------------------------------
# SEVERITY_MAP / STATUS_MAP completeness
# ---------------------------------------------------------------------------


def test_severity_map_has_critical():
    assert CriblProvider.SEVERITY_MAP["critical"] == AlertSeverity.CRITICAL


def test_severity_map_has_error():
    assert CriblProvider.SEVERITY_MAP["error"] == AlertSeverity.HIGH


def test_severity_map_has_warning():
    assert CriblProvider.SEVERITY_MAP["warning"] == AlertSeverity.WARNING
    assert CriblProvider.SEVERITY_MAP["warn"] == AlertSeverity.WARNING


def test_severity_map_has_info():
    assert CriblProvider.SEVERITY_MAP["info"] == AlertSeverity.INFO


def test_severity_map_has_debug_and_low():
    assert CriblProvider.SEVERITY_MAP["debug"] == AlertSeverity.LOW
    assert CriblProvider.SEVERITY_MAP["low"] == AlertSeverity.LOW


def test_status_map_has_firing():
    assert CriblProvider.STATUS_MAP["firing"] == AlertStatus.FIRING
    assert CriblProvider.STATUS_MAP["active"] == AlertStatus.FIRING
    assert CriblProvider.STATUS_MAP["failed"] == AlertStatus.FIRING


def test_status_map_has_resolved():
    assert CriblProvider.STATUS_MAP["resolved"] == AlertStatus.RESOLVED
    assert CriblProvider.STATUS_MAP["ok"] == AlertStatus.RESOLVED
    assert CriblProvider.STATUS_MAP["cleared"] == AlertStatus.RESOLVED


def test_status_map_has_suppressed():
    assert CriblProvider.STATUS_MAP["suppressed"] == AlertStatus.SUPPRESSED


# ---------------------------------------------------------------------------
# Provider metadata
# ---------------------------------------------------------------------------


def test_provider_display_name():
    assert CriblProvider.PROVIDER_DISPLAY_NAME == "Cribl"


def test_provider_category():
    assert "Monitoring" in CriblProvider.PROVIDER_CATEGORY


def test_provider_tags():
    assert "alert" in CriblProvider.PROVIDER_TAGS


def test_webhook_markdown_contains_placeholder():
    assert "{keep_webhook_api_url}" in CriblProvider.webhook_markdown
    assert "{api_key}" in CriblProvider.webhook_markdown


def test_provider_scopes_defined():
    assert len(CriblProvider.PROVIDER_SCOPES) >= 1
    scope_names = [s.name for s in CriblProvider.PROVIDER_SCOPES]
    assert "system:read" in scope_names
