"""
Unit tests for the Coroot provider.

Tests cover:
  - Config validation (api_key, username+password, both missing)
  - _map_pull_alert: firing alert
  - _map_pull_alert: resolved alert (resolved_at set)
  - _map_pull_alert: suppressed alert
  - _map_pull_alert: severity mapping (critical, warning, info, ok, unknown)
  - _map_pull_alert: application_id dict parsing
  - _map_pull_alert: unix timestamp conversion
  - _map_pull_alert: missing optional fields handled gracefully
  - _format_alert (webhook): FIRING status
  - _format_alert (webhook): RESOLVED status
  - _format_alert (webhook): SUPPRESSED status
  - _format_alert (webhook): severity mapping from webhook payload
  - _format_alert (webhook): application dict → service string
  - _format_alert (webhook): description built from summary + duration + resolved_by
  - _format_alert (webhook): labels include project_name, rule_name, etc.
  - _format_alert (webhook): detail array expansion in labels
  - _format_alert (webhook): stable ID generated via sha256
  - _format_alert (webhook): empty/missing fields handled gracefully
  - _format_alert (webhook): incident payload (status + application only)
  - SEVERITY_MAP completeness
  - STATUS_MAP completeness
"""

import pytest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.coroot_provider.coroot_provider import (
    CorootProvider,
    CorootProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    api_key: str = "test-api-key",
    host_url: str = "https://coroot.example.com",
    project_id: str = "default",
) -> CorootProvider:
    """Build a CorootProvider backed by API-key auth."""
    config = ProviderConfig(
        authentication={
            "host_url": host_url,
            "project_id": project_id,
            "api_key": api_key,
        }
    )
    ctx = ContextManager(tenant_id="test-tenant", workflow_id="test-workflow")
    return CorootProvider(ctx, "coroot-test", config)


def _firing_pull_alert() -> dict:
    """Simulated Coroot REST API alert (firing, critical)."""
    return {
        "id": "alert-abc123",
        "fingerprint": "sha256fingerprint",
        "rule_id": "rule-uuid-1",
        "rule_name": "High Error Rate",
        "project_id": "default",
        "application_id": {"Namespace": "production", "Kind": "Deployment", "Name": "api-server"},
        "severity": "critical",
        "summary": "Error rate exceeded 5% for 5 minutes",
        "details": [],
        "opened_at": 1711700000,
        "resolved_at": 0,
        "manually_resolved_at": 0,
        "suppressed": False,
        "resolved_by": "",
        "report": "SLO",
        "duration": 330,
    }


def _resolved_pull_alert() -> dict:
    alert = _firing_pull_alert()
    alert["resolved_at"] = 1711703600
    alert["severity"] = "info"
    return alert


def _suppressed_pull_alert() -> dict:
    alert = _firing_pull_alert()
    alert["suppressed"] = True
    alert["severity"] = "warning"
    return alert


def _firing_webhook_payload() -> dict:
    """Coroot webhook alert payload (AlertTemplateValues rendered with {{json .}})."""
    return {
        "status": "FIRING",
        "project_name": "My Project",
        "application": {"Namespace": "prod", "Kind": "Deployment", "Name": "api"},
        "rule_name": "High CPU Usage",
        "severity": "critical",
        "summary": "CPU usage exceeded 90%",
        "details": [
            {"name": "cpu", "value": "93%"},
            {"name": "threshold", "value": "90%"},
        ],
        "duration": "5m30s",
        "resolved_by": "",
        "url": "https://coroot.example.com/p/default/alerts/abc123",
    }


def _resolved_webhook_payload() -> dict:
    payload = _firing_webhook_payload()
    payload["status"] = "RESOLVED"
    payload["severity"] = "info"
    payload["resolved_by"] = "manual"
    return payload


# ---------------------------------------------------------------------------
# Config validation tests
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_api_key_auth_valid(self):
        provider = _make_provider(api_key="my-secret-key")
        provider.validate_config()
        assert provider.authentication_config.api_key == "my-secret-key"
        assert provider.authentication_config.host_url == "https://coroot.example.com"
        assert provider.authentication_config.project_id == "default"

    def test_username_password_auth_valid(self):
        config = ProviderConfig(
            authentication={
                "host_url": "https://coroot.example.com",
                "project_id": "default",
                "username": "admin",
                "password": "secret",
            }
        )
        ctx = ContextManager(tenant_id="t", workflow_id="w")
        provider = CorootProvider(ctx, "coroot", config)
        provider.validate_config()
        assert provider.authentication_config.username == "admin"
        assert provider.authentication_config.password == "secret"

    def test_missing_credentials_raises(self):
        config = ProviderConfig(
            authentication={
                "host_url": "https://coroot.example.com",
                "project_id": "default",
                # No api_key and no username/password
            }
        )
        ctx = ContextManager(tenant_id="t", workflow_id="w")
        provider = CorootProvider(ctx, "coroot", config)
        with pytest.raises(ValueError, match="api_key or username"):
            provider.validate_config()

    def test_verify_ssl_defaults_to_true(self):
        provider = _make_provider()
        provider.validate_config()
        assert provider.authentication_config.verify_ssl is True

    def test_verify_ssl_can_be_disabled(self):
        config = ProviderConfig(
            authentication={
                "host_url": "https://coroot.example.com",
                "project_id": "default",
                "api_key": "key",
                "verify_ssl": False,
            }
        )
        ctx = ContextManager(tenant_id="t", workflow_id="w")
        provider = CorootProvider(ctx, "coroot", config)
        provider.validate_config()
        assert provider.authentication_config.verify_ssl is False


# ---------------------------------------------------------------------------
# Pull mode: _map_pull_alert tests
# ---------------------------------------------------------------------------


class TestMapPullAlert:
    def setup_method(self):
        self.provider = _make_provider()
        self.provider.validate_config()

    def test_firing_critical_alert(self):
        raw = _firing_pull_alert()
        alert = self.provider._map_pull_alert(raw)
        assert alert is not None
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.name == "High Error Rate"
        assert "Error rate exceeded" in alert.description
        assert "coroot" in alert.source

    def test_resolved_alert(self):
        raw = _resolved_pull_alert()
        alert = self.provider._map_pull_alert(raw)
        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO

    def test_suppressed_alert(self):
        raw = _suppressed_pull_alert()
        alert = self.provider._map_pull_alert(raw)
        assert alert.status == AlertStatus.SUPPRESSED

    def test_severity_warning(self):
        raw = _firing_pull_alert()
        raw["severity"] = "warning"
        alert = self.provider._map_pull_alert(raw)
        assert alert.severity == AlertSeverity.WARNING

    def test_severity_info(self):
        raw = _firing_pull_alert()
        raw["severity"] = "info"
        alert = self.provider._map_pull_alert(raw)
        assert alert.severity == AlertSeverity.INFO

    def test_severity_ok(self):
        raw = _firing_pull_alert()
        raw["severity"] = "ok"
        alert = self.provider._map_pull_alert(raw)
        assert alert.severity == AlertSeverity.LOW

    def test_severity_unknown(self):
        raw = _firing_pull_alert()
        raw["severity"] = "unknown"
        alert = self.provider._map_pull_alert(raw)
        assert alert.severity == AlertSeverity.INFO

    def test_severity_unexpected_falls_back_to_info(self):
        raw = _firing_pull_alert()
        raw["severity"] = "super-critical"
        alert = self.provider._map_pull_alert(raw)
        assert alert.severity == AlertSeverity.INFO

    def test_application_id_dict_parsed(self):
        raw = _firing_pull_alert()
        alert = self.provider._map_pull_alert(raw)
        assert "production" in alert.service
        assert "Deployment" in alert.service
        assert "api-server" in alert.service

    def test_application_id_string(self):
        raw = _firing_pull_alert()
        raw["application_id"] = "custom-service"
        alert = self.provider._map_pull_alert(raw)
        assert alert.service == "custom-service"

    def test_unix_timestamp_converted(self):
        raw = _firing_pull_alert()
        raw["opened_at"] = 1711700000
        alert = self.provider._map_pull_alert(raw)
        assert "2024" in alert.lastReceived or "T" in alert.lastReceived

    def test_url_built_from_id(self):
        raw = _firing_pull_alert()
        alert = self.provider._map_pull_alert(raw)
        assert "alert-abc123" in alert.url
        assert "coroot.example.com" in alert.url

    def test_labels_contain_rule_info(self):
        raw = _firing_pull_alert()
        alert = self.provider._map_pull_alert(raw)
        assert alert.labels["rule_name"] == "High Error Rate"
        assert alert.labels["project_id"] == "default"
        assert alert.labels["fingerprint"] == "sha256fingerprint"

    def test_missing_id_uses_fallback(self):
        raw = _firing_pull_alert()
        del raw["id"]
        alert = self.provider._map_pull_alert(raw)
        assert alert.id.startswith("coroot-")

    def test_manually_resolved_at_treated_as_resolved(self):
        raw = _firing_pull_alert()
        raw["manually_resolved_at"] = 1711703600
        alert = self.provider._map_pull_alert(raw)
        assert alert.status == AlertStatus.RESOLVED

    def test_empty_application_id_dict(self):
        raw = _firing_pull_alert()
        raw["application_id"] = {}
        alert = self.provider._map_pull_alert(raw)
        # Should not raise; service will be empty or stripped
        assert alert is not None

    def test_none_application_id(self):
        raw = _firing_pull_alert()
        raw["application_id"] = None
        alert = self.provider._map_pull_alert(raw)
        assert alert is not None

    def test_zero_opened_at_uses_utcnow(self):
        raw = _firing_pull_alert()
        raw["opened_at"] = 0
        alert = self.provider._map_pull_alert(raw)
        assert "T" in alert.lastReceived  # ISO format


# ---------------------------------------------------------------------------
# _get_alerts integration (mocked HTTP)
# ---------------------------------------------------------------------------


class TestGetAlerts:
    def test_get_alerts_calls_api(self):
        provider = _make_provider()
        provider.validate_config()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "alerts": [_firing_pull_alert()]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, "_get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_response
            mock_get_session.return_value = mock_session

            alerts = provider._get_alerts()

        assert len(alerts) == 1
        assert alerts[0].name == "High Error Rate"

    def test_get_alerts_handles_empty_list(self):
        provider = _make_provider()
        provider.validate_config()

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"alerts": []}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, "_get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_response
            mock_get_session.return_value = mock_session

            alerts = provider._get_alerts()

        assert alerts == []

    def test_get_alerts_handles_flat_response(self):
        """Coroot may return flat {alerts: [...]} without data wrapper."""
        provider = _make_provider()
        provider.validate_config()

        mock_response = MagicMock()
        mock_response.json.return_value = {"alerts": [_firing_pull_alert()]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, "_get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_response
            mock_get_session.return_value = mock_session

            alerts = provider._get_alerts()

        assert len(alerts) == 1

    def test_get_alerts_propagates_request_exception(self):
        import requests

        provider = _make_provider()
        provider.validate_config()

        with patch.object(provider, "_get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_session.get.side_effect = requests.ConnectionError("Network error")
            mock_get_session.return_value = mock_session

            with pytest.raises(requests.ConnectionError):
                provider._get_alerts()

    def test_session_uses_api_key_header(self):
        """Session must include X-API-Key header when api_key is set."""
        provider = _make_provider(api_key="super-secret-key")
        provider.validate_config()

        # Invalidate cached session to force re-creation
        provider._session = None

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"alerts": []}}
        mock_response.raise_for_status = MagicMock()

        with patch("requests.Session") as mock_session_cls:
            mock_sess = MagicMock()
            mock_session_cls.return_value = mock_sess
            mock_sess.get.return_value = mock_response

            provider._get_alerts()

            mock_sess.headers.update.assert_called_once_with(
                {"X-API-Key": "super-secret-key"}
            )


# ---------------------------------------------------------------------------
# Push mode: _format_alert (webhook) tests
# ---------------------------------------------------------------------------


class TestFormatAlert:
    def test_firing_webhook(self):
        payload = _firing_webhook_payload()
        alert = CorootProvider._format_alert(payload)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.name == "High CPU Usage"

    def test_resolved_webhook(self):
        payload = _resolved_webhook_payload()
        alert = CorootProvider._format_alert(payload)
        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO

    def test_suppressed_status(self):
        payload = _firing_webhook_payload()
        payload["status"] = "SUPPRESSED"
        alert = CorootProvider._format_alert(payload)
        assert alert.status == AlertStatus.SUPPRESSED

    def test_inhibited_mapped_to_suppressed(self):
        payload = _firing_webhook_payload()
        payload["status"] = "INHIBITED"
        alert = CorootProvider._format_alert(payload)
        assert alert.status == AlertStatus.SUPPRESSED

    def test_ok_status_mapped_to_resolved(self):
        payload = _firing_webhook_payload()
        payload["status"] = "OK"
        alert = CorootProvider._format_alert(payload)
        assert alert.status == AlertStatus.RESOLVED

    def test_severity_warning(self):
        payload = _firing_webhook_payload()
        payload["severity"] = "warning"
        alert = CorootProvider._format_alert(payload)
        assert alert.severity == AlertSeverity.WARNING

    def test_severity_info(self):
        payload = _firing_webhook_payload()
        payload["severity"] = "info"
        alert = CorootProvider._format_alert(payload)
        assert alert.severity == AlertSeverity.INFO

    def test_severity_ok(self):
        payload = _firing_webhook_payload()
        payload["severity"] = "ok"
        alert = CorootProvider._format_alert(payload)
        assert alert.severity == AlertSeverity.LOW

    def test_severity_unknown(self):
        payload = _firing_webhook_payload()
        payload["severity"] = "unknown"
        alert = CorootProvider._format_alert(payload)
        assert alert.severity == AlertSeverity.INFO

    def test_severity_missing_defaults_to_info(self):
        payload = _firing_webhook_payload()
        del payload["severity"]
        alert = CorootProvider._format_alert(payload)
        assert alert.severity == AlertSeverity.INFO

    def test_application_dict_parsed_to_service(self):
        payload = _firing_webhook_payload()
        alert = CorootProvider._format_alert(payload)
        assert "prod" in alert.service
        assert "Deployment" in alert.service
        assert "api" in alert.service

    def test_application_string(self):
        payload = _firing_webhook_payload()
        payload["application"] = "custom-service"
        alert = CorootProvider._format_alert(payload)
        assert alert.service == "custom-service"

    def test_description_includes_summary(self):
        payload = _firing_webhook_payload()
        alert = CorootProvider._format_alert(payload)
        assert "CPU usage exceeded 90%" in alert.description

    def test_description_includes_duration(self):
        payload = _firing_webhook_payload()
        alert = CorootProvider._format_alert(payload)
        assert "5m30s" in alert.description

    def test_description_includes_resolved_by(self):
        payload = _resolved_webhook_payload()
        alert = CorootProvider._format_alert(payload)
        assert "manual" in alert.description

    def test_url_preserved(self):
        payload = _firing_webhook_payload()
        alert = CorootProvider._format_alert(payload)
        assert alert.url == "https://coroot.example.com/p/default/alerts/abc123"

    def test_labels_contain_rule_name(self):
        payload = _firing_webhook_payload()
        alert = CorootProvider._format_alert(payload)
        assert alert.labels["rule_name"] == "High CPU Usage"
        assert alert.labels["project_name"] == "My Project"

    def test_labels_contain_status_raw(self):
        payload = _firing_webhook_payload()
        alert = CorootProvider._format_alert(payload)
        assert alert.labels["status_raw"] == "FIRING"

    def test_detail_array_expanded_in_labels(self):
        payload = _firing_webhook_payload()
        alert = CorootProvider._format_alert(payload)
        # Details should be flattened into labels
        assert any("cpu" in k or "cpu" in v for k, v in alert.labels.items())

    def test_stable_id_generated(self):
        payload = _firing_webhook_payload()
        alert1 = CorootProvider._format_alert(payload)
        alert2 = CorootProvider._format_alert(payload)
        assert alert1.id == alert2.id
        assert alert1.id.startswith("coroot-")

    def test_id_differs_for_different_rules(self):
        payload1 = _firing_webhook_payload()
        payload2 = _firing_webhook_payload()
        payload2["rule_name"] = "Different Rule"
        alert1 = CorootProvider._format_alert(payload1)
        alert2 = CorootProvider._format_alert(payload2)
        assert alert1.id != alert2.id

    def test_source_is_coroot(self):
        payload = _firing_webhook_payload()
        alert = CorootProvider._format_alert(payload)
        assert "coroot" in alert.source

    def test_empty_payload_handled(self):
        alert = CorootProvider._format_alert({})
        assert alert is not None
        assert alert.status == AlertStatus.FIRING

    def test_missing_application_handled(self):
        payload = _firing_webhook_payload()
        del payload["application"]
        alert = CorootProvider._format_alert(payload)
        assert alert is not None

    def test_missing_rule_name_uses_project_name(self):
        payload = _firing_webhook_payload()
        del payload["rule_name"]
        alert = CorootProvider._format_alert(payload)
        assert "My Project" in alert.name or alert.name == "Coroot Alert (My Project)"

    def test_incident_payload(self):
        """Incident payloads have status + application but no rule_name/severity."""
        payload = {
            "status": "FIRING",
            "application": {"Namespace": "prod", "Kind": "Deployment", "Name": "db"},
            "url": "https://coroot.example.com/p/default/incidents/xyz",
        }
        alert = CorootProvider._format_alert(payload)
        assert alert.status == AlertStatus.FIRING
        assert "prod" in alert.service or "db" in alert.service


# ---------------------------------------------------------------------------
# Class-level map completeness
# ---------------------------------------------------------------------------


class TestMapCompleteness:
    def test_severity_map_covers_all_coroot_severities(self):
        """All known Coroot severity strings must be in SEVERITY_MAP."""
        for sev in ("critical", "warning", "info", "ok", "unknown"):
            assert sev in CorootProvider.SEVERITY_MAP, f"Missing: {sev}"

    def test_status_map_covers_main_statuses(self):
        for st in ("FIRING", "RESOLVED", "SUPPRESSED"):
            assert st in CorootProvider.STATUS_MAP, f"Missing: {st}"

    def test_all_severity_map_values_are_alert_severity(self):
        for k, v in CorootProvider.SEVERITY_MAP.items():
            assert isinstance(
                v, AlertSeverity
            ), f"SEVERITY_MAP[{k!r}] is not AlertSeverity"

    def test_all_status_map_values_are_alert_status(self):
        for k, v in CorootProvider.STATUS_MAP.items():
            assert isinstance(
                v, AlertStatus
            ), f"STATUS_MAP[{k!r}] is not AlertStatus"
