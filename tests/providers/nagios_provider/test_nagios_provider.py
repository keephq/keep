"""
Tests for the Nagios provider.

Coverage:
  - _format_alert: host notifications, service notifications, all severity/status
    mappings, timestamp parsing, missing/empty fields
  - _parse_nagios_timestamp: Core long-date format, ISO-8601 passthrough, bad input
  - validate_config: valid config, webhook-only (empty) config
  - _get_alerts: skips API when credentials absent, handles XI API responses
  - validate_scopes: no-credentials case, successful probe, HTTP error
"""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest
import requests

# ---------------------------------------------------------------------------
# Import the real AlertDto classes first (they only need pydantic v1 + pytz).
# ---------------------------------------------------------------------------
from keep.api.models.alert import AlertSeverity, AlertStatus

# ---------------------------------------------------------------------------
# Now stub the heavy transitive dependencies so importing nagios_provider
# doesn't drag in starlette, sqlalchemy, opentelemetry, etc.
# Only stub leaf modules whose parent packages are already real modules.
# ---------------------------------------------------------------------------


def _ensure_real_parents(dotted: str) -> None:
    """Make sure every parent package of `dotted` exists as a real or stub package."""
    parts = dotted.split(".")
    for i in range(1, len(parts)):
        key = ".".join(parts[:i])
        if key not in sys.modules:
            parent = types.ModuleType(key)
            parent.__path__ = []
            parent.__package__ = key
            sys.modules[key] = parent


def _stub_module(dotted: str, **attrs) -> types.ModuleType:
    """Create a stub for `dotted` (and its parents if needed), with given attrs."""
    _ensure_real_parents(dotted)
    if dotted not in sys.modules:
        mod = types.ModuleType(dotted)
        mod.__path__ = []
        mod.__package__ = dotted
        sys.modules[dotted] = mod
    else:
        mod = sys.modules[dotted]
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


_stub_module("keep.contextmanager.contextmanager", ContextManager=MagicMock())
_stub_module("keep.providers.providers_factory", ProvidersFactory=MagicMock())

# Some base_provider sub-dependencies
for _dep in [
    "opentelemetry",
    "opentelemetry.trace",
    "opentelemetry.instrumentation",
    "opentelemetry.instrumentation.requests",
]:
    if _dep not in sys.modules:
        _stub_module(_dep)

# ---------------------------------------------------------------------------
# Now import the Nagios provider (parents keep.providers, keep.providers.base,
# keep.providers.models are real filesystem packages already handled above).
# ---------------------------------------------------------------------------
from keep.providers.nagios_provider.nagios_provider import (  # noqa: E402
    NagiosProvider,
    NagiosProviderAuthConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    nagios_url: str = "",
    api_key: str = "",
    verify_ssl: bool = True,
) -> NagiosProvider:
    """Return a NagiosProvider via object.__new__ — no DB/network needed."""
    cfg = MagicMock()
    cfg.authentication = {
        "nagios_url": nagios_url,
        "api_key": api_key,
        "verify_ssl": verify_ssl,
    }

    provider = object.__new__(NagiosProvider)
    provider.context_manager = MagicMock()
    provider.logger = MagicMock()
    provider.config = cfg
    provider.validate_config()
    return provider


# ---------------------------------------------------------------------------
# _format_alert — host notifications
# ---------------------------------------------------------------------------


class TestFormatAlertHost:
    def test_host_problem(self):
        event = {
            "notification_type": "PROBLEM",
            "hostname": "web-01",
            "hoststate": "DOWN",
            "hostaddress": "10.0.0.1",
            "hostoutput": "CRITICAL - Host unreachable",
            "timestamp": "2024-01-15T10:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.name == "web-01"
        assert alert.id == "nagios-host-web-01"
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.source == ["nagios"]
        assert alert.hostname == "web-01"
        assert alert.description == "CRITICAL - Host unreachable"
        assert alert.pushed is True
        assert alert.notification_type == "PROBLEM"

    def test_host_recovery(self):
        event = {
            "notification_type": "RECOVERY",
            "hostname": "web-01",
            "hoststate": "UP",
            "hostaddress": "10.0.0.1",
            "hostoutput": "Host is UP",
            "timestamp": "2024-01-15T11:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO

    def test_host_unreachable(self):
        event = {
            "notification_type": "PROBLEM",
            "hostname": "db-01",
            "hoststate": "UNREACHABLE",
            "hostoutput": "Cannot route to host",
            "timestamp": "2024-01-15T10:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.HIGH

    def test_host_acknowledgement(self):
        event = {
            "notification_type": "ACKNOWLEDGEMENT",
            "hostname": "cache-01",
            "hoststate": "DOWN",
            "hostoutput": "Host is down",
            "timestamp": "2024-01-15T10:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.status == AlertStatus.ACKNOWLEDGED

    def test_host_downtime_start(self):
        event = {
            "notification_type": "DOWNTIMESTART",
            "hostname": "maint-host",
            "hoststate": "DOWN",
            "timestamp": "2024-01-15T10:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.status == AlertStatus.SUPPRESSED

    def test_host_flapping_start(self):
        event = {
            "notification_type": "FLAPPINGSTART",
            "hostname": "flappy-host",
            "hoststate": "UP",
            "timestamp": "2024-01-15T10:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.status == AlertStatus.FIRING

    def test_missing_fields_graceful(self):
        """_format_alert must not raise on a completely empty payload."""
        alert = NagiosProvider._format_alert({})

        assert alert.source == ["nagios"]
        assert alert.pushed is True
        assert alert.name == "unknown"

    def test_no_servicedesc_is_host_alert(self):
        event = {
            "notification_type": "PROBLEM",
            "hostname": "srv-01",
            "hoststate": "DOWN",
            "timestamp": "2024-01-15T10:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.servicedesc is None
        assert alert.hoststate == "DOWN"


# ---------------------------------------------------------------------------
# _format_alert — service notifications
# ---------------------------------------------------------------------------


class TestFormatAlertService:
    def test_service_critical(self):
        event = {
            "notification_type": "PROBLEM",
            "hostname": "app-01",
            "hostaddress": "10.0.0.2",
            "servicedesc": "HTTP",
            "servicestate": "CRITICAL",
            "serviceoutput": "HTTP CRITICAL: Status line: 503",
            "timestamp": "2024-01-15T10:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.name == "app-01/HTTP"
        assert alert.id == "nagios-svc-app-01-HTTP"
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.servicedesc == "HTTP"
        assert alert.servicestate == "CRITICAL"
        assert alert.description == "HTTP CRITICAL: Status line: 503"

    def test_service_warning(self):
        event = {
            "notification_type": "PROBLEM",
            "hostname": "app-01",
            "servicedesc": "Disk",
            "servicestate": "WARNING",
            "serviceoutput": "DISK WARNING - free space: 20%",
            "timestamp": "2024-01-15T10:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING

    def test_service_ok_recovery(self):
        event = {
            "notification_type": "RECOVERY",
            "hostname": "app-01",
            "servicedesc": "HTTP",
            "servicestate": "OK",
            "serviceoutput": "HTTP OK: 200",
            "timestamp": "2024-01-15T11:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO

    def test_service_unknown(self):
        event = {
            "notification_type": "PROBLEM",
            "hostname": "app-01",
            "servicedesc": "NRPE",
            "servicestate": "UNKNOWN",
            "timestamp": "2024-01-15T10:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.FIRING

    def test_service_acknowledgement(self):
        event = {
            "notification_type": "ACKNOWLEDGEMENT",
            "hostname": "app-01",
            "servicedesc": "DB Connections",
            "servicestate": "CRITICAL",
            "timestamp": "2024-01-15T10:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.status == AlertStatus.ACKNOWLEDGED

    def test_fingerprint_set(self):
        event = {
            "notification_type": "PROBLEM",
            "hostname": "web-01",
            "servicedesc": "HTTP",
            "servicestate": "CRITICAL",
            "timestamp": "2024-01-15T10:00:00",
        }
        alert = NagiosProvider._format_alert(event)

        assert alert.fingerprint is not None
        assert len(alert.fingerprint) > 0


# ---------------------------------------------------------------------------
# _parse_nagios_timestamp
# ---------------------------------------------------------------------------


class TestParseNagiosTimestamp:
    def test_iso_passthrough(self):
        ts = "2024-01-15T10:00:00"
        result = NagiosProvider._parse_nagios_timestamp(ts)
        assert result == ts

    def test_iso_with_z(self):
        ts = "2024-01-15T10:00:00Z"
        result = NagiosProvider._parse_nagios_timestamp(ts)
        assert result == ts

    def test_nagios_core_long_date(self):
        """$LONGDATETIME$ = "Mon Jan 15 10:00:00 UTC 2024"."""
        ts = "Mon Jan 15 10:00:00 UTC 2024"
        result = NagiosProvider._parse_nagios_timestamp(ts)
        assert "2024" in result

    def test_nagios_core_long_date_single_digit_day(self):
        """$LONGDATETIME$ with double-space before single-digit day."""
        ts = "Mon Jan  1 10:00:00 UTC 2024"
        result = NagiosProvider._parse_nagios_timestamp(ts)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_simple_datetime(self):
        ts = "2024-01-15 10:00:00"
        result = NagiosProvider._parse_nagios_timestamp(ts)
        assert "2024" in result

    def test_empty_string_returns_current(self):
        result = NagiosProvider._parse_nagios_timestamp("")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_none_returns_current(self):
        result = NagiosProvider._parse_nagios_timestamp(None)
        assert isinstance(result, str)

    def test_unparseable_returns_raw(self):
        ts = "not-a-date"
        result = NagiosProvider._parse_nagios_timestamp(ts)
        assert result == ts


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


class TestValidateConfig:
    def test_webhook_only_empty_credentials(self):
        provider = _make_provider()
        assert provider.authentication_config.nagios_url == ""
        assert provider.authentication_config.api_key == ""
        assert provider.authentication_config.verify_ssl is True

    def test_full_credentials(self):
        provider = _make_provider(
            nagios_url="https://nagios.example.com/nagiosxi",
            api_key="secret-key",
            verify_ssl=False,
        )
        assert provider.authentication_config.nagios_url == "https://nagios.example.com/nagiosxi"
        assert provider.authentication_config.api_key == "secret-key"
        assert provider.authentication_config.verify_ssl is False


# ---------------------------------------------------------------------------
# _get_alerts — pull mode
# ---------------------------------------------------------------------------


class TestGetAlerts:
    def test_no_credentials_returns_empty(self):
        provider = _make_provider()
        alerts = provider._get_alerts()
        assert alerts == []

    def test_pulls_host_and_service_status(self):
        provider = _make_provider(
            nagios_url="https://nagios.example.com/nagiosxi",
            api_key="key",
        )

        host_response = MagicMock()
        host_response.json.return_value = {
            "hoststatus": [
                {
                    "name": "web-01",
                    "current_state": "1",
                    "last_check": "2024-01-15T10:00:00",
                    "status_information": "Host unreachable",
                }
            ]
        }
        host_response.raise_for_status = MagicMock()

        svc_response = MagicMock()
        svc_response.json.return_value = {
            "servicestatus": [
                {
                    "host_name": "web-01",
                    "name": "HTTP",
                    "current_state": "2",
                    "last_check": "2024-01-15T10:00:00",
                    "status_information": "HTTP 503",
                }
            ]
        }
        svc_response.raise_for_status = MagicMock()

        with patch("requests.get", side_effect=[host_response, svc_response]):
            alerts = provider._get_alerts()

        assert len(alerts) == 2
        host_alert = next(a for a in alerts if "HTTP" not in a.name)
        svc_alert = next(a for a in alerts if "HTTP" in a.name)

        assert host_alert.status == AlertStatus.FIRING
        assert host_alert.severity == AlertSeverity.CRITICAL
        assert svc_alert.status == AlertStatus.FIRING
        assert svc_alert.severity == AlertSeverity.CRITICAL

    def test_api_error_returns_empty(self):
        provider = _make_provider(
            nagios_url="https://nagios.example.com/nagiosxi",
            api_key="key",
        )

        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
            alerts = provider._get_alerts()

        assert alerts == []

    def test_host_state_up_is_resolved(self):
        provider = _make_provider(
            nagios_url="https://nagios.example.com/nagiosxi",
            api_key="key",
        )

        host_response = MagicMock()
        host_response.json.return_value = {
            "hoststatus": [
                {
                    "name": "healthy-host",
                    "current_state": "0",
                    "last_check": "2024-01-15T10:00:00",
                    "status_information": "OK",
                }
            ]
        }
        host_response.raise_for_status = MagicMock()

        svc_response = MagicMock()
        svc_response.json.return_value = {"servicestatus": []}
        svc_response.raise_for_status = MagicMock()

        with patch("requests.get", side_effect=[host_response, svc_response]):
            alerts = provider._get_alerts()

        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.RESOLVED

    def test_service_state_ok_is_resolved(self):
        provider = _make_provider(
            nagios_url="https://nagios.example.com/nagiosxi",
            api_key="key",
        )

        host_response = MagicMock()
        host_response.json.return_value = {"hoststatus": []}
        host_response.raise_for_status = MagicMock()

        svc_response = MagicMock()
        svc_response.json.return_value = {
            "servicestatus": [
                {
                    "host_name": "web-01",
                    "name": "HTTP",
                    "current_state": "0",
                    "last_check": "2024-01-15T10:00:00",
                    "status_information": "HTTP OK",
                }
            ]
        }
        svc_response.raise_for_status = MagicMock()

        with patch("requests.get", side_effect=[host_response, svc_response]):
            alerts = provider._get_alerts()

        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.RESOLVED
        assert alerts[0].severity == AlertSeverity.INFO


# ---------------------------------------------------------------------------
# validate_scopes
# ---------------------------------------------------------------------------


class TestValidateScopes:
    def test_no_credentials(self):
        provider = _make_provider()
        scopes = provider.validate_scopes()
        assert "api_access" in scopes
        assert scopes["api_access"] is not True

    def test_successful_probe(self):
        provider = _make_provider(
            nagios_url="https://nagios.example.com/nagiosxi",
            api_key="key",
        )
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            scopes = provider.validate_scopes()

        assert scopes["api_access"] is True

    def test_http_error(self):
        provider = _make_provider(
            nagios_url="https://nagios.example.com/nagiosxi",
            api_key="bad-key",
        )
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        http_err = requests.exceptions.HTTPError(response=mock_response)

        with patch("requests.get", side_effect=http_err):
            scopes = provider.validate_scopes()

        assert "403" in str(scopes["api_access"])

    def test_connection_error(self):
        provider = _make_provider(
            nagios_url="https://nagios.example.com/nagiosxi",
            api_key="key",
        )
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
            scopes = provider.validate_scopes()

        assert scopes["api_access"] is not True


# ---------------------------------------------------------------------------
# dispose
# ---------------------------------------------------------------------------


class TestDispose:
    def test_dispose_does_not_raise(self):
        provider = _make_provider()
        provider.dispose()


# ---------------------------------------------------------------------------
# Severity / Status maps completeness
# ---------------------------------------------------------------------------


class TestMappings:
    def test_all_service_states_mapped_in_severities(self):
        for state in ("ok", "warning", "critical", "unknown"):
            assert state in NagiosProvider.SEVERITIES_MAP

    def test_all_service_states_mapped_in_status(self):
        for state in ("ok", "warning", "critical", "unknown"):
            assert state in NagiosProvider.STATUS_MAP

    def test_all_host_states_mapped_in_severities(self):
        for state in ("up", "down", "unreachable"):
            assert state in NagiosProvider.SEVERITIES_MAP

    def test_all_host_states_mapped_in_status(self):
        for state in ("up", "down", "unreachable"):
            assert state in NagiosProvider.STATUS_MAP

    def test_notification_types_in_status_map(self):
        for ntype in ("problem", "recovery", "acknowledgement", "flappingstart", "flappingstop"):
            assert ntype in NagiosProvider.STATUS_MAP

    def test_severity_values_are_alert_severity(self):
        for val in NagiosProvider.SEVERITIES_MAP.values():
            assert isinstance(val, AlertSeverity)

    def test_status_values_are_alert_status(self):
        for val in NagiosProvider.STATUS_MAP.values():
            assert isinstance(val, AlertStatus)
