"""
Unit tests for the Mimir provider.

These tests verify:
  - Configuration validation (including multi-tenant tenant field)
  - Alert formatting from Alertmanager webhook payloads
  - Severity and status mapping
  - Multi-tenant header injection (X-Scope-OrgID)
  - simulate_alert() mock generation
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.mimir_provider.mimir_provider import (
    MimirProvider,
    MimirProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    url="http://mimir.example.com",
    username="",
    password="",
    tenant="",
    verify=True,
) -> MimirProvider:
    """Build a MimirProvider instance with the given config."""
    config = ProviderConfig(
        authentication={
            "url": url,
            "username": username,
            "password": password,
            "tenant": tenant,
            "verify": verify,
        }
    )
    ctx = ContextManager(tenant_id="test-tenant", workflow_id="test-workflow")
    return MimirProvider(ctx, "mimir-test", config)


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestMimirProviderConfig:
    def test_minimal_config(self):
        provider = _make_provider()
        assert provider.authentication_config.url == "http://mimir.example.com"
        assert provider.authentication_config.username == ""
        assert provider.authentication_config.password == ""
        assert provider.authentication_config.tenant == ""
        assert provider.authentication_config.verify is True

    def test_full_config(self):
        provider = _make_provider(
            url="https://mimir.corp.com",
            username="myuser",
            password="secret",
            tenant="my-team",
            verify=False,
        )
        cfg = provider.authentication_config
        assert str(cfg.url) == "https://mimir.corp.com"
        assert cfg.username == "myuser"
        assert cfg.password == "secret"
        assert cfg.tenant == "my-team"
        assert cfg.verify is False

    def test_invalid_url_raises(self):
        with pytest.raises(Exception):
            _make_provider(url="not-a-url")


# ---------------------------------------------------------------------------
# Header generation (multi-tenant)
# ---------------------------------------------------------------------------


class TestMimirHeaders:
    def test_no_tenant_no_header(self):
        provider = _make_provider(tenant="")
        headers = provider._get_headers()
        assert "X-Scope-OrgID" not in headers

    def test_tenant_adds_header(self):
        provider = _make_provider(tenant="acme-corp")
        headers = provider._get_headers()
        assert headers["X-Scope-OrgID"] == "acme-corp"


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


class TestMimirAuth:
    def test_no_credentials_returns_none(self):
        provider = _make_provider(username="", password="")
        assert provider._get_auth() is None

    def test_credentials_returns_basic_auth(self):
        from requests.auth import HTTPBasicAuth

        provider = _make_provider(username="user", password="pass")
        auth = provider._get_auth()
        assert isinstance(auth, HTTPBasicAuth)
        assert auth.username == "user"
        assert auth.password == "pass"


# ---------------------------------------------------------------------------
# _format_alert — Alertmanager webhook payload
# ---------------------------------------------------------------------------


class TestMimirFormatAlert:
    """Test _format_alert with various Alertmanager payloads."""

    def _make_alertmanager_payload(
        self,
        alertname="TestAlert",
        severity="critical",
        status="firing",
        fingerprint="abc123",
        description="Something went wrong",
        summary="Alert summary",
    ) -> dict:
        return {
            "version": "4",
            "groupKey": "{}:{alertname='TestAlert'}",
            "status": status,
            "receiver": "keep",
            "alerts": [
                {
                    "status": status,
                    "labels": {
                        "alertname": alertname,
                        "severity": severity,
                        "instance": "host1:9100",
                        "job": "node",
                    },
                    "annotations": {
                        "summary": summary,
                        "description": description,
                    },
                    "startsAt": "2024-01-01T00:00:00Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                    "fingerprint": fingerprint,
                }
            ],
        }

    def test_basic_firing_alert(self):
        payload = self._make_alertmanager_payload()
        alerts = MimirProvider._format_alert(payload)
        assert len(alerts) == 1
        alert = alerts[0]
        assert isinstance(alert, AlertDto)
        assert alert.name == "TestAlert"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING
        assert "mimir" in alert.source

    def test_resolved_alert(self):
        payload = self._make_alertmanager_payload(status="resolved")
        alerts = MimirProvider._format_alert(payload)
        assert alerts[0].status == AlertStatus.RESOLVED

    def test_severity_mapping_warning(self):
        payload = self._make_alertmanager_payload(severity="warning")
        alerts = MimirProvider._format_alert(payload)
        assert alerts[0].severity == AlertSeverity.WARNING

    def test_severity_mapping_info(self):
        payload = self._make_alertmanager_payload(severity="info")
        alerts = MimirProvider._format_alert(payload)
        assert alerts[0].severity == AlertSeverity.INFO

    def test_severity_mapping_unknown_defaults_to_info(self):
        payload = self._make_alertmanager_payload(severity="unknown-severity")
        alerts = MimirProvider._format_alert(payload)
        assert alerts[0].severity == AlertSeverity.INFO

    def test_description_from_annotations(self):
        payload = self._make_alertmanager_payload(description="Disk nearly full")
        alerts = MimirProvider._format_alert(payload)
        assert "Disk nearly full" in (alerts[0].description or "")

    def test_fingerprint_preserved(self):
        payload = self._make_alertmanager_payload(fingerprint="deadbeef")
        alerts = MimirProvider._format_alert(payload)
        assert alerts[0].fingerprint == "deadbeef"

    def test_multiple_alerts_in_one_payload(self):
        payload = {
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "AlertA", "severity": "critical"},
                    "annotations": {"summary": "A fires"},
                    "startsAt": "2024-01-01T00:00:00Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                    "fingerprint": "fp1",
                },
                {
                    "status": "resolved",
                    "labels": {"alertname": "AlertB", "severity": "warning"},
                    "annotations": {"summary": "B resolved"},
                    "startsAt": "2024-01-01T00:00:00Z",
                    "endsAt": "2024-01-01T01:00:00Z",
                    "fingerprint": "fp2",
                },
            ],
        }
        alerts = MimirProvider._format_alert(payload)
        assert len(alerts) == 2
        names = {a.name for a in alerts}
        assert "AlertA" in names
        assert "AlertB" in names

    def test_list_input_returned_as_is(self):
        """If _format_alert receives a list it should return it unchanged."""
        existing = [MagicMock(spec=AlertDto)]
        result = MimirProvider._format_alert(existing)
        assert result is existing

    def test_source_is_mimir(self):
        payload = self._make_alertmanager_payload()
        alert = MimirProvider._format_alert(payload)[0]
        assert alert.source == ["mimir"]

    def test_blank_fields_set_to_empty_string(self):
        """value, instance, job should default to '' to avoid template errors."""
        payload = {
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "Minimal"},
                    "annotations": {},
                    "startsAt": "2024-01-01T00:00:00Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                    "fingerprint": "fp3",
                }
            ],
        }
        alert = MimirProvider._format_alert(payload)[0]
        assert alert.value == ""
        assert alert.instance == ""
        assert alert.job == ""


# ---------------------------------------------------------------------------
# severity / status maps
# ---------------------------------------------------------------------------


class TestMimirMaps:
    def test_all_severities_mapped(self):
        expected = {
            "critical": AlertSeverity.CRITICAL,
            "error": AlertSeverity.HIGH,
            "high": AlertSeverity.HIGH,
            "warning": AlertSeverity.WARNING,
            "medium": AlertSeverity.WARNING,
            "info": AlertSeverity.INFO,
            "low": AlertSeverity.LOW,
        }
        assert MimirProvider.SEVERITIES_MAP == expected

    def test_all_statuses_mapped(self):
        assert MimirProvider.STATUS_MAP["firing"] == AlertStatus.FIRING
        assert MimirProvider.STATUS_MAP["resolved"] == AlertStatus.RESOLVED


# ---------------------------------------------------------------------------
# simulate_alert
# ---------------------------------------------------------------------------


class TestMimirSimulateAlert:
    def test_simulate_returns_dict(self):
        result = MimirProvider.simulate_alert()
        assert isinstance(result, dict)

    def test_simulate_contains_required_keys(self):
        result = MimirProvider.simulate_alert()
        assert "labels" in result
        assert "fingerprint" in result
        assert "status" in result
        assert "startsAt" in result

    def test_simulate_wrapped_format(self):
        result = MimirProvider.simulate_alert(to_wrap_with_provider_type=True)
        assert result["keep_source_type"] == "mimir"
        assert "event" in result

    def test_simulate_specific_alert_type(self):
        result = MimirProvider.simulate_alert(alert_type="HighCPUUsage")
        assert result["labels"]["alertname"] == "HighCPUUsage"

    def test_simulate_valid_status(self):
        from keep.api.models.alert import AlertStatus

        for _ in range(10):
            result = MimirProvider.simulate_alert()
            assert result["status"] in [
                AlertStatus.FIRING.value,
                AlertStatus.RESOLVED.value,
            ]


# ---------------------------------------------------------------------------
# validate_scopes (mocked HTTP)
# ---------------------------------------------------------------------------


class TestMimirValidateScopes:
    @patch("keep.providers.mimir_provider.mimir_provider.requests.get")
    def test_connectivity_ok(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"data": {"alerts": []}}
        mock_get.return_value = mock_resp

        provider = _make_provider()
        scopes = provider.validate_scopes()
        assert scopes["connectivity"] is True

    @patch("keep.providers.mimir_provider.mimir_provider.requests.get")
    def test_connectivity_fails(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        provider = _make_provider()
        scopes = provider.validate_scopes()
        assert scopes["connectivity"] == "Connection refused"


# ---------------------------------------------------------------------------
# _query (mocked HTTP)
# ---------------------------------------------------------------------------


class TestMimirQuery:
    @patch("keep.providers.mimir_provider.mimir_provider.requests.get")
    def test_query_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "success",
            "data": {"resultType": "vector", "result": []},
        }
        mock_get.return_value = mock_resp

        provider = _make_provider()
        result = provider._query("up")
        assert result["status"] == "success"

    @patch("keep.providers.mimir_provider.mimir_provider.requests.get")
    def test_query_failure_raises(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.content = b"bad query"
        mock_get.return_value = mock_resp

        provider = _make_provider()
        with pytest.raises(Exception, match="Mimir query failed"):
            provider._query("invalid{{{query")

    def test_empty_query_raises(self):
        provider = _make_provider()
        with pytest.raises(ValueError, match="Query is required"):
            provider._query("")

    @patch("keep.providers.mimir_provider.mimir_provider.requests.get")
    def test_query_includes_tenant_header(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "success", "data": {}}
        mock_get.return_value = mock_resp

        provider = _make_provider(tenant="engineering")
        provider._query("up")

        _, call_kwargs = mock_get.call_args
        assert call_kwargs.get("headers", {}).get("X-Scope-OrgID") == "engineering"

    @patch("keep.providers.mimir_provider.mimir_provider.requests.get")
    def test_query_no_tenant_header_when_empty(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "success", "data": {}}
        mock_get.return_value = mock_resp

        provider = _make_provider(tenant="")
        provider._query("up")

        _, call_kwargs = mock_get.call_args
        assert "X-Scope-OrgID" not in call_kwargs.get("headers", {})
