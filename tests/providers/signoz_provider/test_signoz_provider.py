"""
Unit tests for the SigNoz provider.

Tests cover:
  - validate_config: minimal config with host_url only
  - validate_config: with API key
  - validate_config: verify_ssl defaults to True
  - validate_config: verify_ssl can be set to False
  - _build_headers: includes SIGNOZ-API-KEY when api_key provided
  - _build_headers: no SIGNOZ-API-KEY when api_key is None
  - _get_base_url: strips trailing slash
  - _get_alerts: dict wrapper {"data": [...]}
  - _get_alerts: direct list response
  - _get_alerts: empty list response
  - _get_alerts: raises on HTTP error
  - _alert_dict_to_dto: severity critical
  - _alert_dict_to_dto: severity warning
  - _alert_dict_to_dto: severity info default
  - _alert_dict_to_dto: severity low
  - _alert_dict_to_dto: suppressed state
  - _alert_dict_to_dto: firing state
  - _alert_dict_to_dto: timestamp parsing (startsAt with Z suffix)
  - _alert_dict_to_dto: bad timestamp falls back to utcnow
  - _alert_dict_to_dto: source is signoz
  - _alert_dict_to_dto: description from annotations.description
  - _alert_dict_to_dto: description falls back to summary
  - _alert_dict_to_dto: description falls back to alertname
  - _parse_alertmanager_payload: Alertmanager envelope with alerts array
  - _parse_alertmanager_payload: resolved status
  - _parse_alertmanager_payload: multiple alerts
  - _parse_alertmanager_payload: flat payload (no alerts key)
  - _parse_alertmanager_payload: endsAt 0001-01-01 treated as null
  - _parse_alertmanager_payload: generatorURL propagated to url
  - _parse_alertmanager_payload: externalURL as fallback url
  - _parse_alertmanager_payload: {"data": {...}} unwrapping
  - _format_webhook_event: valid JSON bytes
  - _format_webhook_event: dict input (no parsing needed)
  - _format_webhook_event: invalid JSON bytes raises ValueError
  - _format_webhook_event: single alert returns AlertDto not list
  - _format_webhook_event: multiple alerts returns list
  - validate_scopes: 200 returns True
  - validate_scopes: 403 returns error string
  - validate_scopes: connection error returns error string
  - SEVERITIES_MAP completeness
  - STATUS_MAP completeness
  - Provider metadata: PROVIDER_DISPLAY_NAME, PROVIDER_CATEGORY
"""

import datetime
import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.signoz_provider.signoz_provider import (
    SignozProvider,
    SignozProviderAuthConfig,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_provider(
    host_url: str = "https://signoz.example.com",
    api_key: str | None = "test-pat-key",
    verify_ssl: bool = True,
) -> SignozProvider:
    auth: dict = {"host_url": host_url, "verify_ssl": verify_ssl}
    if api_key is not None:
        auth["api_key"] = api_key
    config = ProviderConfig(authentication=auth)
    ctx = ContextManager(tenant_id="test-tenant", workflow_id="test-wf")
    return SignozProvider(ctx, "signoz-test", config)


def _alertmanager_alert(
    alertname: str = "HighCPU",
    severity: str = "critical",
    status: str = "firing",
    fingerprint: str = "deadbeef",
    service: str = "frontend",
) -> dict:
    return {
        "status": status,
        "labels": {
            "alertname": alertname,
            "severity": severity,
            "service": service,
        },
        "annotations": {
            "description": f"{alertname} exceeded threshold",
            "summary": f"{alertname} alert",
        },
        "startsAt": "2024-06-01T12:00:00Z",
        "endsAt": "0001-01-01T00:00:00Z",
        "fingerprint": fingerprint,
        "generatorURL": "https://signoz.example.com/alerts/42",
    }


def _alertmanager_envelope(
    status: str = "firing",
    num_alerts: int = 1,
) -> dict:
    alerts = [
        _alertmanager_alert(
            alertname=f"Alert{i}",
            status=status,
            fingerprint=f"fp-{i}",
        )
        for i in range(num_alerts)
    ]
    return {
        "version": "4",
        "receiver": "keep",
        "status": status,
        "alerts": alerts,
        "groupLabels": {"alertname": "HighCPU"},
        "commonLabels": {"env": "production"},
        "commonAnnotations": {},
        "externalURL": "https://signoz.example.com",
    }


def _mock_response(status_code: int = 200, json_data: object = None) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data if json_data is not None else []
    mock.text = ""
    if status_code >= 400:
        http_err = requests.exceptions.HTTPError(response=mock)
        mock.raise_for_status.side_effect = http_err
    else:
        mock.raise_for_status.return_value = None
    return mock


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


def test_validate_config_minimal():
    config = ProviderConfig(authentication={"host_url": "http://localhost:3301"})
    ctx = ContextManager(tenant_id="t", workflow_id="w")
    p = SignozProvider(ctx, "p", config)
    assert p.authentication_config.host_url == "http://localhost:3301"
    assert p.authentication_config.api_key is None
    assert p.authentication_config.verify_ssl is True


def test_validate_config_with_api_key():
    provider = _make_provider(api_key="my-secret-key")
    assert provider.authentication_config.api_key == "my-secret-key"


def test_validate_config_verify_ssl_default():
    provider = _make_provider(verify_ssl=True)
    assert provider.authentication_config.verify_ssl is True


def test_validate_config_verify_ssl_false():
    provider = _make_provider(verify_ssl=False)
    assert provider.authentication_config.verify_ssl is False


# ---------------------------------------------------------------------------
# _build_headers
# ---------------------------------------------------------------------------


def test_build_headers_with_api_key():
    provider = _make_provider(api_key="mytoken")
    headers = provider._build_headers()
    assert headers["SIGNOZ-API-KEY"] == "mytoken"


def test_build_headers_without_api_key():
    provider = _make_provider(api_key=None)
    headers = provider._build_headers()
    assert "SIGNOZ-API-KEY" not in headers


def test_build_headers_content_type():
    provider = _make_provider()
    headers = provider._build_headers()
    assert headers.get("Content-Type") == "application/json"


def test_build_headers_empty_api_key_excluded():
    """Empty string api_key should not add SIGNOZ-API-KEY header."""
    provider = _make_provider(api_key="")
    headers = provider._build_headers()
    assert "SIGNOZ-API-KEY" not in headers


# ---------------------------------------------------------------------------
# _get_base_url
# ---------------------------------------------------------------------------


def test_get_base_url_strips_trailing_slash():
    provider = _make_provider(host_url="https://signoz.example.com/")
    assert not provider._get_base_url().endswith("/")


def test_get_base_url_no_slash():
    provider = _make_provider(host_url="https://signoz.example.com")
    assert provider._get_base_url() == "https://signoz.example.com"


# ---------------------------------------------------------------------------
# _get_alerts (pull mode)
# ---------------------------------------------------------------------------


def test_get_alerts_dict_wrapper():
    provider = _make_provider()
    raw = _alertmanager_alert()
    with patch("requests.get", return_value=_mock_response(200, {"data": [raw]})):
        alerts = provider._get_alerts()
    assert len(alerts) == 1
    assert alerts[0].name == "HighCPU"


def test_get_alerts_dict_wrapper_alerts_key():
    provider = _make_provider()
    raw = _alertmanager_alert()
    with patch("requests.get", return_value=_mock_response(200, {"alerts": [raw]})):
        alerts = provider._get_alerts()
    assert len(alerts) == 1


def test_get_alerts_direct_list():
    provider = _make_provider()
    raw = _alertmanager_alert()
    with patch("requests.get", return_value=_mock_response(200, [raw])):
        alerts = provider._get_alerts()
    assert len(alerts) == 1


def test_get_alerts_empty_list():
    provider = _make_provider()
    with patch("requests.get", return_value=_mock_response(200, [])):
        alerts = provider._get_alerts()
    assert alerts == []


def test_get_alerts_raises_on_http_error():
    provider = _make_provider()
    with patch("requests.get", return_value=_mock_response(403)):
        with pytest.raises(requests.exceptions.HTTPError):
            provider._get_alerts()


def test_get_alerts_multiple_alerts():
    provider = _make_provider()
    raws = [
        _alertmanager_alert("Alert1", "critical", "firing", "fp1"),
        _alertmanager_alert("Alert2", "warning", "firing", "fp2"),
    ]
    with patch("requests.get", return_value=_mock_response(200, raws)):
        alerts = provider._get_alerts()
    assert len(alerts) == 2


# ---------------------------------------------------------------------------
# _alert_dict_to_dto
# ---------------------------------------------------------------------------


def test_alert_dict_to_dto_severity_critical():
    provider = _make_provider()
    raw = _alertmanager_alert(severity="critical")
    dto = provider._alert_dict_to_dto(raw)
    assert dto.severity == AlertSeverity.CRITICAL


def test_alert_dict_to_dto_severity_warning():
    provider = _make_provider()
    raw = _alertmanager_alert(severity="warning")
    dto = provider._alert_dict_to_dto(raw)
    assert dto.severity == AlertSeverity.WARNING


def test_alert_dict_to_dto_severity_info_default():
    provider = _make_provider()
    raw = _alertmanager_alert(severity="info")
    dto = provider._alert_dict_to_dto(raw)
    assert dto.severity == AlertSeverity.INFO


def test_alert_dict_to_dto_severity_unknown_defaults_info():
    provider = _make_provider()
    raw = {"labels": {"alertname": "T"}, "annotations": {}}
    dto = provider._alert_dict_to_dto(raw)
    assert dto.severity == AlertSeverity.INFO


def test_alert_dict_to_dto_severity_low():
    provider = _make_provider()
    raw = _alertmanager_alert(severity="low")
    dto = provider._alert_dict_to_dto(raw)
    assert dto.severity == AlertSeverity.LOW


def test_alert_dict_to_dto_suppressed_state():
    provider = _make_provider()
    raw = _alertmanager_alert()
    raw["status"] = {"state": "suppressed"}
    dto = provider._alert_dict_to_dto(raw)
    assert dto.status == AlertStatus.SUPPRESSED


def test_alert_dict_to_dto_firing_state():
    provider = _make_provider()
    raw = _alertmanager_alert(status="firing")
    dto = provider._alert_dict_to_dto(raw)
    assert dto.status == AlertStatus.FIRING


def test_alert_dict_to_dto_timestamp_parsed():
    provider = _make_provider()
    raw = _alertmanager_alert()
    raw["startsAt"] = "2024-06-01T12:30:00Z"
    dto = provider._alert_dict_to_dto(raw)
    assert dto.startedAt is not None


def test_alert_dict_to_dto_bad_timestamp_fallback():
    provider = _make_provider()
    raw = {"labels": {"alertname": "T"}, "annotations": {}, "startsAt": "NOT-A-DATE"}
    dto = provider._alert_dict_to_dto(raw)
    assert dto.startedAt is not None


def test_alert_dict_to_dto_source_is_signoz():
    provider = _make_provider()
    raw = _alertmanager_alert()
    dto = provider._alert_dict_to_dto(raw)
    assert "signoz" in dto.source


def test_alert_dict_to_dto_description_from_description():
    provider = _make_provider()
    raw = _alertmanager_alert()
    raw["annotations"] = {"description": "detailed description", "summary": "summary"}
    dto = provider._alert_dict_to_dto(raw)
    assert dto.description == "detailed description"


def test_alert_dict_to_dto_description_fallback_to_summary():
    provider = _make_provider()
    raw = _alertmanager_alert()
    raw["annotations"] = {"summary": "just a summary"}
    dto = provider._alert_dict_to_dto(raw)
    assert dto.description == "just a summary"


def test_alert_dict_to_dto_description_fallback_to_alertname():
    provider = _make_provider()
    raw = {"labels": {"alertname": "MyAlert"}, "annotations": {}}
    dto = provider._alert_dict_to_dto(raw)
    assert dto.description == "MyAlert"


def test_alert_dict_to_dto_fingerprint_used():
    provider = _make_provider()
    raw = _alertmanager_alert(fingerprint="unique-fp-123")
    dto = provider._alert_dict_to_dto(raw)
    assert dto.fingerprint == "unique-fp-123"


# ---------------------------------------------------------------------------
# _parse_alertmanager_payload (static / webhook)
# ---------------------------------------------------------------------------


def test_parse_alertmanager_envelope_firing():
    envelope = _alertmanager_envelope("firing")
    alerts = SignozProvider._parse_alertmanager_payload(envelope)
    assert len(alerts) == 1
    assert alerts[0].status == AlertStatus.FIRING
    assert alerts[0].name == "Alert0"


def test_parse_alertmanager_envelope_resolved():
    envelope = _alertmanager_envelope("resolved", 1)
    envelope["alerts"][0]["status"] = "resolved"
    alerts = SignozProvider._parse_alertmanager_payload(envelope)
    assert alerts[0].status == AlertStatus.RESOLVED


def test_parse_alertmanager_multiple_alerts():
    envelope = _alertmanager_envelope("firing", 3)
    alerts = SignozProvider._parse_alertmanager_payload(envelope)
    assert len(alerts) == 3


def test_parse_alertmanager_flat_payload():
    """No 'alerts' key — treat the whole dict as one alert."""
    flat = {
        "status": "firing",
        "labels": {"alertname": "FlatAlert", "severity": "warning"},
        "annotations": {"description": "flat alert"},
        "startsAt": "2024-01-01T00:00:00Z",
        "fingerprint": "flat-fp",
    }
    alerts = SignozProvider._parse_alertmanager_payload(flat)
    assert len(alerts) == 1
    assert alerts[0].name == "FlatAlert"


def test_parse_alertmanager_ends_at_null_epoch():
    """endsAt 0001-01-01 should be treated as null."""
    alert = _alertmanager_alert(status="firing")
    alert["endsAt"] = "0001-01-01T00:00:00Z"
    envelope = {"alerts": [alert]}
    alerts = SignozProvider._parse_alertmanager_payload(envelope)
    assert alerts[0].endedAt is None


def test_parse_alertmanager_generator_url_propagated():
    alert = _alertmanager_alert()
    alert["generatorURL"] = "https://signoz.example.com/alerts/99"
    envelope = {"alerts": [alert]}
    alerts = SignozProvider._parse_alertmanager_payload(envelope)
    assert alerts[0].url == "https://signoz.example.com/alerts/99"


def test_parse_alertmanager_external_url_fallback():
    alert = _alertmanager_alert()
    del alert["generatorURL"]
    envelope = {
        "alerts": [alert],
        "externalURL": "https://fallback.example.com",
    }
    alerts = SignozProvider._parse_alertmanager_payload(envelope)
    assert alerts[0].url == "https://fallback.example.com"


def test_parse_alertmanager_data_wrapper():
    """Payload wrapped as {"data": {...}} should be unwrapped."""
    inner = _alertmanager_envelope("firing")
    wrapped = {"data": inner}
    alerts = SignozProvider._parse_alertmanager_payload(wrapped)
    assert len(alerts) >= 1


def test_parse_alertmanager_severity_high():
    alert = _alertmanager_alert(severity="error")
    envelope = {"alerts": [alert]}
    alerts = SignozProvider._parse_alertmanager_payload(envelope)
    assert alerts[0].severity == AlertSeverity.HIGH


def test_parse_alertmanager_source_signoz():
    envelope = _alertmanager_envelope("firing")
    alerts = SignozProvider._parse_alertmanager_payload(envelope)
    assert "signoz" in alerts[0].source


# ---------------------------------------------------------------------------
# _format_webhook_event
# ---------------------------------------------------------------------------


def test_format_webhook_event_bytes():
    provider = _make_provider()
    payload = _alertmanager_envelope("firing")
    raw_bytes = json.dumps(payload).encode()
    result = provider._format_webhook_event("tenant", "provider", raw_bytes)
    # Single alert in envelope -> returns AlertDto directly
    assert isinstance(result, AlertDto)
    assert result.status == AlertStatus.FIRING


def test_format_webhook_event_dict():
    provider = _make_provider()
    payload = _alertmanager_envelope("firing")
    result = provider._format_webhook_event("tenant", "provider", payload)
    assert isinstance(result, AlertDto)


def test_format_webhook_event_invalid_json_raises():
    provider = _make_provider()
    with pytest.raises(ValueError, match="Invalid JSON"):
        provider._format_webhook_event("t", "p", b"this is not json")


def test_format_webhook_event_multiple_alerts_returns_list():
    provider = _make_provider()
    payload = _alertmanager_envelope("firing", num_alerts=2)
    result = provider._format_webhook_event("tenant", "provider", payload)
    assert isinstance(result, list)
    assert len(result) == 2


def test_format_webhook_event_resolved():
    provider = _make_provider()
    payload = _alertmanager_envelope("resolved")
    payload["alerts"][0]["status"] = "resolved"
    result = provider._format_webhook_event("tenant", "provider", payload)
    assert isinstance(result, AlertDto)
    assert result.status == AlertStatus.RESOLVED


# ---------------------------------------------------------------------------
# validate_scopes
# ---------------------------------------------------------------------------


def test_validate_scopes_200():
    provider = _make_provider()
    with patch("requests.get", return_value=_mock_response(200, [])):
        scopes = provider.validate_scopes()
    assert scopes.get("alerts:read") is True


def test_validate_scopes_204():
    provider = _make_provider()
    mock = MagicMock()
    mock.status_code = 204
    mock.text = ""
    with patch("requests.get", return_value=mock):
        scopes = provider.validate_scopes()
    assert scopes.get("alerts:read") is True


def test_validate_scopes_403():
    provider = _make_provider()
    mock = MagicMock()
    mock.status_code = 403
    mock.text = "Forbidden"
    with patch("requests.get", return_value=mock):
        scopes = provider.validate_scopes()
    assert scopes.get("alerts:read") != True
    assert "403" in str(scopes.get("alerts:read"))


def test_validate_scopes_connection_error():
    provider = _make_provider()
    with patch("requests.get", side_effect=Exception("connection refused")):
        scopes = provider.validate_scopes()
    assert "connection refused" in str(scopes.get("alerts:read"))


# ---------------------------------------------------------------------------
# SEVERITIES_MAP / STATUS_MAP completeness
# ---------------------------------------------------------------------------


def test_severities_map_critical():
    assert SignozProvider.SEVERITIES_MAP["critical"] == AlertSeverity.CRITICAL


def test_severities_map_warning():
    assert SignozProvider.SEVERITIES_MAP["warning"] == AlertSeverity.WARNING


def test_severities_map_info():
    assert SignozProvider.SEVERITIES_MAP["info"] == AlertSeverity.INFO


def test_severities_map_low():
    assert SignozProvider.SEVERITIES_MAP["low"] == AlertSeverity.LOW


def test_severities_map_error_is_high():
    assert SignozProvider.SEVERITIES_MAP["error"] == AlertSeverity.HIGH


def test_status_map_firing():
    assert SignozProvider.STATUS_MAP["firing"] == AlertStatus.FIRING


def test_status_map_resolved():
    assert SignozProvider.STATUS_MAP["resolved"] == AlertStatus.RESOLVED


def test_status_map_pending():
    assert SignozProvider.STATUS_MAP["pending"] == AlertStatus.PENDING


def test_status_map_inactive_is_resolved():
    assert SignozProvider.STATUS_MAP["inactive"] == AlertStatus.RESOLVED


def test_status_map_suppressed():
    assert SignozProvider.STATUS_MAP["suppressed"] == AlertStatus.SUPPRESSED


def test_severities_map_contains_priority_levels():
    """p1-p5 priority levels should all be present."""
    for k in ("p1", "p2", "p3", "p4", "p5"):
        assert k in SignozProvider.SEVERITIES_MAP


# ---------------------------------------------------------------------------
# Provider metadata
# ---------------------------------------------------------------------------


def test_provider_display_name():
    assert SignozProvider.PROVIDER_DISPLAY_NAME == "SigNoz"


def test_provider_category_monitoring():
    assert "Monitoring" in SignozProvider.PROVIDER_CATEGORY


def test_provider_scopes_not_empty():
    assert len(SignozProvider.PROVIDER_SCOPES) > 0


def test_provider_tags_observability():
    assert "observability" in SignozProvider.PROVIDER_TAGS


def test_provider_webhook_markdown_contains_url_placeholder():
    assert "{keep_webhook_api_url}" in SignozProvider.webhook_markdown
