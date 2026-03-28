"""
Unit tests for the PRTG Network Monitor provider.

Tests cover:
  - Config validation (url, username, passhash/password)
  - Authentication param building (passhash preferred over password)
  - Pull mode: _sensor_to_dto, _get_alerts
  - Push mode: _format_alert (webhook)
  - STATUS_MAP and SEVERITY_MAP completeness
  - PRIORITY_MAP severity escalation in webhook mode
  - validate_scopes success and failure paths
  - Edge cases: missing fields, unknown status, empty results
"""

import pytest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.prtg_provider.prtg_provider import (
    PrtgProvider,
    PrtgProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    url: str = "https://prtg.example.com",
    username: str = "prtgadmin",
    passhash: str = "12345678",
    password: str = "",
    verify_ssl: bool = True,
) -> PrtgProvider:
    """Build a PrtgProvider with the given config."""
    config = ProviderConfig(
        authentication={
            "url": url,
            "username": username,
            "passhash": passhash,
            "password": password,
            "verify_ssl": verify_ssl,
        }
    )
    ctx = ContextManager(tenant_id="test-tenant", workflow_id="test-workflow")
    return PrtgProvider(ctx, "prtg-test", config)


def _down_sensor() -> dict:
    """Simulate a PRTG API sensor object in Down state."""
    return {
        "objid": 1001,
        "sensor": "CPU Load",
        "device": "Server-01",
        "group": "Production",
        "probe": "Local Probe",
        "status": "Down",
        "statusraw": 4,
        "message": "CPU Load is above threshold",
        "priority": "4",
        "lastvalue": "92 %",
        "lastdown": "2026-03-28 10:30:00",
        "lastup": "2026-03-28 09:00:00",
        "active": True,
    }


def _warning_sensor() -> dict:
    return {
        "objid": 1002,
        "sensor": "Disk Free",
        "device": "FileServer-02",
        "group": "Storage",
        "probe": "Remote Probe",
        "status": "Warning",
        "statusraw": 7,
        "message": "Disk space below 20%",
        "priority": "3",
        "lastvalue": "18 %",
        "lastdown": "",
        "lastup": "2026-03-28 08:00:00",
        "active": True,
    }


def _acknowledged_sensor() -> dict:
    return {
        "objid": 1003,
        "sensor": "Network Interface",
        "device": "Router-01",
        "group": "Network",
        "probe": "Local Probe",
        "status": "Down (Acknowledged)",
        "statusraw": 5,
        "message": "Interface down, under maintenance",
        "priority": "2",
        "lastvalue": "0 Mbit/s",
        "lastdown": "2026-03-27 22:00:00",
        "lastup": "2026-03-27 21:59:00",
        "active": True,
    }


def _paused_sensor() -> dict:
    return {
        "objid": 1004,
        "sensor": "Ping",
        "device": "TestHost",
        "group": "Dev",
        "probe": "Local Probe",
        "status": "Paused by User",
        "statusraw": 6,
        "message": "Paused for maintenance window",
        "priority": "2",
        "lastvalue": "No data",
        "lastdown": "",
        "lastup": "2026-03-28 07:00:00",
        "active": False,
    }


def _webhook_down_event() -> dict:
    """Simulate a PRTG webhook POST body for a Down sensor."""
    return {
        "sensor": "HTTP Check",
        "device": "WebServer-01",
        "group": "WebFarm",
        "probe": "Local Probe",
        "status": "Down",
        "message": "HTTP 503 Service Unavailable",
        "datetime": "2026-03-28 11:00:00",
        "sensor_id": "2001",
        "device_id": "3001",
        "group_id": "4001",
        "priority": "5",
        "lastvalue": "503",
    }


def _webhook_warning_event() -> dict:
    return {
        "sensor": "Memory",
        "device": "AppServer-03",
        "group": "AppServers",
        "probe": "Remote Probe",
        "status": "Warning",
        "message": "Memory usage above 80%",
        "datetime": "2026-03-28 12:00:00",
        "sensor_id": "2002",
        "device_id": "3002",
        "group_id": "4002",
        "priority": "3",
        "lastvalue": "83 %",
    }


def _webhook_up_event() -> dict:
    return {
        "sensor": "HTTP Check",
        "device": "WebServer-01",
        "group": "WebFarm",
        "probe": "Local Probe",
        "status": "Up",
        "message": "HTTP 200 OK",
        "datetime": "2026-03-28 11:30:00",
        "sensor_id": "2001",
        "device_id": "3001",
        "group_id": "4001",
        "priority": "3",
        "lastvalue": "200",
    }


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestPrtgProviderConfig:
    def test_valid_passhash_config(self):
        provider = _make_provider(passhash="abc123")
        assert provider.authentication_config.username == "prtgadmin"
        assert provider.authentication_config.passhash == "abc123"
        assert provider.authentication_config.url is not None

    def test_valid_password_config(self):
        provider = _make_provider(passhash="", password="mypassword")
        assert provider.authentication_config.password == "mypassword"
        assert provider.authentication_config.passhash == ""

    def test_missing_both_passhash_and_password_raises(self):
        config = ProviderConfig(
            authentication={
                "url": "https://prtg.example.com",
                "username": "admin",
                "passhash": "",
                "password": "",
            }
        )
        ctx = ContextManager(tenant_id="test", workflow_id="test")
        provider = PrtgProvider(ctx, "prtg-test", config)
        with pytest.raises(ValueError, match="Either 'passhash' or 'password'"):
            provider.validate_config()

    def test_url_stored_correctly(self):
        provider = _make_provider(url="https://my-prtg.corp.com")
        assert "my-prtg.corp.com" in str(provider.authentication_config.url)

    def test_verify_ssl_default_true(self):
        provider = _make_provider()
        assert provider.authentication_config.verify_ssl is True

    def test_verify_ssl_can_be_false(self):
        provider = _make_provider(verify_ssl=False)
        assert provider.authentication_config.verify_ssl is False


# ---------------------------------------------------------------------------
# Auth params
# ---------------------------------------------------------------------------


class TestAuthParams:
    def test_passhash_used_when_set(self):
        provider = _make_provider(passhash="myhash", password="mypass")
        params = provider._get_auth_params()
        assert "passhash" in params
        assert params["passhash"] == "myhash"
        assert "password" not in params

    def test_password_used_when_no_passhash(self):
        provider = _make_provider(passhash="", password="mypassword")
        params = provider._get_auth_params()
        assert "password" in params
        assert params["password"] == "mypassword"
        assert "passhash" not in params

    def test_username_always_present(self):
        provider = _make_provider(username="testuser")
        params = provider._get_auth_params()
        assert params["username"] == "testuser"


# ---------------------------------------------------------------------------
# Pull mode: _sensor_to_dto
# ---------------------------------------------------------------------------


class TestSensorToDto:
    def test_down_sensor_critical_status(self):
        provider = _make_provider()
        dto = provider._sensor_to_dto(_down_sensor())
        assert dto.severity == AlertSeverity.CRITICAL
        assert dto.status == AlertStatus.FIRING

    def test_warning_sensor_warning_severity(self):
        provider = _make_provider()
        dto = provider._sensor_to_dto(_warning_sensor())
        assert dto.severity == AlertSeverity.WARNING
        assert dto.status == AlertStatus.FIRING

    def test_acknowledged_sensor_acknowledged_status(self):
        provider = _make_provider()
        dto = provider._sensor_to_dto(_acknowledged_sensor())
        assert dto.status == AlertStatus.ACKNOWLEDGED
        assert dto.severity == AlertSeverity.CRITICAL  # Down (Acknowledged) is still critical

    def test_paused_sensor_suppressed_status(self):
        provider = _make_provider()
        dto = provider._sensor_to_dto(_paused_sensor())
        assert dto.status == AlertStatus.SUPPRESSED
        assert dto.severity == AlertSeverity.INFO

    def test_name_composed_of_device_and_sensor(self):
        provider = _make_provider()
        dto = provider._sensor_to_dto(_down_sensor())
        assert "Server-01" in dto.name
        assert "CPU Load" in dto.name

    def test_sensor_id_is_string(self):
        provider = _make_provider()
        dto = provider._sensor_to_dto(_down_sensor())
        assert dto.id == "1001"

    def test_description_includes_message(self):
        provider = _make_provider()
        dto = provider._sensor_to_dto(_down_sensor())
        assert "CPU Load is above threshold" in dto.description

    def test_description_includes_last_value(self):
        provider = _make_provider()
        dto = provider._sensor_to_dto(_down_sensor())
        assert "92 %" in dto.description

    def test_description_no_last_value_when_no_data(self):
        provider = _make_provider()
        sensor = _paused_sensor()  # lastvalue = "No data"
        dto = provider._sensor_to_dto(sensor)
        assert "No data" not in dto.description

    def test_source_is_prtg(self):
        provider = _make_provider()
        dto = provider._sensor_to_dto(_down_sensor())
        assert "prtg" in dto.source

    def test_service_is_device_name(self):
        provider = _make_provider()
        dto = provider._sensor_to_dto(_down_sensor())
        assert dto.service == "Server-01"

    def test_labels_include_group_and_probe(self):
        provider = _make_provider()
        dto = provider._sensor_to_dto(_down_sensor())
        assert dto.labels["group"] == "Production"
        assert dto.labels["probe"] == "Local Probe"
        assert dto.labels["sensor"] == "CPU Load"
        assert dto.labels["device"] == "Server-01"

    def test_last_received_from_lastdown(self):
        provider = _make_provider()
        dto = provider._sensor_to_dto(_down_sensor())
        assert "2026-03-28" in str(dto.lastReceived)


# ---------------------------------------------------------------------------
# Pull mode: _get_alerts
# ---------------------------------------------------------------------------


class TestGetAlerts:
    @patch("keep.providers.prtg_provider.prtg_provider.requests.get")
    def test_returns_list_of_alert_dtos(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "sensors": [_down_sensor(), _warning_sensor()]
        }
        mock_get.return_value = mock_resp

        provider = _make_provider()
        alerts = provider._get_alerts()

        assert len(alerts) == 2
        assert all(isinstance(a, AlertDto) for a in alerts)

    @patch("keep.providers.prtg_provider.prtg_provider.requests.get")
    def test_empty_sensors_returns_empty_list(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"sensors": []}
        mock_get.return_value = mock_resp

        provider = _make_provider()
        alerts = provider._get_alerts()
        assert alerts == []

    @patch("keep.providers.prtg_provider.prtg_provider.requests.get")
    def test_api_url_contains_table_json(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"sensors": []}
        mock_get.return_value = mock_resp

        provider = _make_provider()
        provider._get_alerts()

        call_url = mock_get.call_args[0][0]
        assert "table.json" in call_url

    @patch("keep.providers.prtg_provider.prtg_provider.requests.get")
    def test_api_url_includes_passhash(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"sensors": []}
        mock_get.return_value = mock_resp

        provider = _make_provider(passhash="testhash")
        provider._get_alerts()

        call_params = mock_get.call_args[1]["params"]
        assert "passhash" in call_params
        assert call_params["passhash"] == "testhash"

    @patch("keep.providers.prtg_provider.prtg_provider.requests.get")
    def test_get_alerts_raises_on_http_error(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.HTTPError("401 Unauthorized")

        provider = _make_provider()
        with pytest.raises(req_lib.exceptions.HTTPError):
            provider._get_alerts()


# ---------------------------------------------------------------------------
# Push mode: _format_alert (webhook)
# ---------------------------------------------------------------------------


class TestFormatAlert:
    def test_down_webhook_critical_severity(self):
        dto = PrtgProvider._format_alert(_webhook_down_event())
        assert dto.severity == AlertSeverity.CRITICAL
        assert dto.status == AlertStatus.FIRING

    def test_warning_webhook_warning_severity(self):
        dto = PrtgProvider._format_alert(_webhook_warning_event())
        assert dto.severity == AlertSeverity.WARNING
        assert dto.status == AlertStatus.FIRING

    def test_up_webhook_resolved_status(self):
        dto = PrtgProvider._format_alert(_webhook_up_event())
        assert dto.status == AlertStatus.RESOLVED
        assert dto.severity == AlertSeverity.INFO

    def test_name_device_slash_sensor(self):
        dto = PrtgProvider._format_alert(_webhook_down_event())
        assert "WebServer-01" in dto.name
        assert "HTTP Check" in dto.name

    def test_id_contains_sensor_id_and_datetime(self):
        dto = PrtgProvider._format_alert(_webhook_down_event())
        assert "2001" in dto.id

    def test_source_is_prtg(self):
        dto = PrtgProvider._format_alert(_webhook_down_event())
        assert "prtg" in dto.source

    def test_service_is_device(self):
        dto = PrtgProvider._format_alert(_webhook_down_event())
        assert dto.service == "WebServer-01"

    def test_labels_include_all_fields(self):
        dto = PrtgProvider._format_alert(_webhook_down_event())
        assert dto.labels["sensor"] == "HTTP Check"
        assert dto.labels["device"] == "WebServer-01"
        assert dto.labels["group"] == "WebFarm"
        assert dto.labels["probe"] == "Local Probe"
        assert dto.labels["sensor_id"] == "2001"
        assert dto.labels["device_id"] == "3001"
        assert dto.labels["group_id"] == "4001"

    def test_description_includes_message(self):
        dto = PrtgProvider._format_alert(_webhook_down_event())
        assert "503 Service Unavailable" in dto.description

    def test_description_includes_last_value(self):
        dto = PrtgProvider._format_alert(_webhook_down_event())
        assert "503" in dto.description

    def test_priority_5_stars_maps_to_critical(self):
        """Down sensor with 5-star priority stays CRITICAL (already max)."""
        event = _webhook_down_event()
        event["priority"] = "*****"
        dto = PrtgProvider._format_alert(event)
        assert dto.severity == AlertSeverity.CRITICAL

    def test_priority_5_escalates_warning_to_critical(self):
        """Warning sensor with priority 5 (critical) should be escalated to CRITICAL."""
        event = _webhook_warning_event()
        event["priority"] = "5"
        dto = PrtgProvider._format_alert(event)
        assert dto.severity == AlertSeverity.CRITICAL

    def test_priority_1_star_warning_event_stays_warning(self):
        """Priority 1 (LOW) should not downgrade a Warning status severity."""
        event = _webhook_warning_event()
        event["priority"] = "1"
        dto = PrtgProvider._format_alert(event)
        # Priority is lower than status-derived WARNING — no downgrade
        assert dto.severity == AlertSeverity.WARNING

    def test_paused_webhook_suppressed(self):
        event = _webhook_down_event()
        event["status"] = "Paused"
        dto = PrtgProvider._format_alert(event)
        assert dto.status == AlertStatus.SUPPRESSED

    def test_unknown_status_fires_as_firing(self):
        event = _webhook_down_event()
        event["status"] = "SomeUnknownStatus"
        dto = PrtgProvider._format_alert(event)
        assert dto.status == AlertStatus.FIRING

    def test_missing_sensor_id_generates_id(self):
        event = _webhook_down_event()
        del event["sensor_id"]
        dto = PrtgProvider._format_alert(event)
        assert dto.id is not None
        assert len(dto.id) > 0

    def test_datetime_preserved_in_last_received(self):
        dto = PrtgProvider._format_alert(_webhook_down_event())
        assert "2026-03-28" in str(dto.lastReceived)


# ---------------------------------------------------------------------------
# STATUS_MAP and SEVERITY_MAP completeness
# ---------------------------------------------------------------------------


class TestMapsCompleteness:
    def test_status_map_down_fires(self):
        assert PrtgProvider.STATUS_MAP["down"] == AlertStatus.FIRING

    def test_status_map_up_resolves(self):
        assert PrtgProvider.STATUS_MAP["up"] == AlertStatus.RESOLVED

    def test_status_map_paused_suppresses(self):
        assert PrtgProvider.STATUS_MAP["paused"] == AlertStatus.SUPPRESSED
        assert PrtgProvider.STATUS_MAP["paused by user"] == AlertStatus.SUPPRESSED
        assert PrtgProvider.STATUS_MAP["paused by schedule"] == AlertStatus.SUPPRESSED
        assert PrtgProvider.STATUS_MAP["paused by dependency"] == AlertStatus.SUPPRESSED
        assert PrtgProvider.STATUS_MAP["paused until"] == AlertStatus.SUPPRESSED

    def test_status_map_unknown_pending(self):
        assert PrtgProvider.STATUS_MAP["unknown"] == AlertStatus.PENDING

    def test_severity_down_critical(self):
        assert PrtgProvider.SEVERITY_MAP["down"] == AlertSeverity.CRITICAL

    def test_severity_warning_warning(self):
        assert PrtgProvider.SEVERITY_MAP["warning"] == AlertSeverity.WARNING

    def test_severity_unusual_warning(self):
        assert PrtgProvider.SEVERITY_MAP["unusual"] == AlertSeverity.WARNING

    def test_severity_partial_down_high(self):
        assert PrtgProvider.SEVERITY_MAP["partial down"] == AlertSeverity.HIGH

    def test_priority_map_numeric(self):
        assert PrtgProvider.PRIORITY_MAP["5"] == AlertSeverity.CRITICAL
        assert PrtgProvider.PRIORITY_MAP["4"] == AlertSeverity.HIGH
        assert PrtgProvider.PRIORITY_MAP["3"] == AlertSeverity.WARNING
        assert PrtgProvider.PRIORITY_MAP["2"] == AlertSeverity.INFO
        assert PrtgProvider.PRIORITY_MAP["1"] == AlertSeverity.LOW

    def test_priority_map_star_encoded(self):
        assert PrtgProvider.PRIORITY_MAP["*****"] == AlertSeverity.CRITICAL
        assert PrtgProvider.PRIORITY_MAP["***"] == AlertSeverity.WARNING
        assert PrtgProvider.PRIORITY_MAP["*"] == AlertSeverity.LOW


# ---------------------------------------------------------------------------
# validate_scopes
# ---------------------------------------------------------------------------


class TestValidateScopes:
    @patch("keep.providers.prtg_provider.prtg_provider.requests.get")
    def test_valid_credentials_returns_true(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"version": "24.0"}
        mock_get.return_value = mock_resp

        provider = _make_provider()
        result = provider.validate_scopes()
        assert result["api_access"] is True

    @patch("keep.providers.prtg_provider.prtg_provider.requests.get")
    def test_http_error_returns_error_string(self, mock_get):
        import requests as req_lib

        err_resp = MagicMock()
        err_resp.status_code = 401
        exc = req_lib.exceptions.HTTPError("401 Unauthorized")
        exc.response = err_resp
        mock_get.side_effect = exc

        provider = _make_provider()
        result = provider.validate_scopes()
        assert result["api_access"] is not True
        assert "401" in str(result["api_access"]) or "Unauthorized" in str(result["api_access"])

    @patch("keep.providers.prtg_provider.prtg_provider.requests.get")
    def test_connection_error_returns_error_string(self, mock_get):
        import requests as req_lib

        mock_get.side_effect = req_lib.exceptions.ConnectionError("Connection refused")

        provider = _make_provider()
        result = provider.validate_scopes()
        assert result["api_access"] is not True

    @patch("keep.providers.prtg_provider.prtg_provider.requests.get")
    def test_validate_scopes_uses_getstatus_endpoint(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {}
        mock_get.return_value = mock_resp

        provider = _make_provider()
        provider.validate_scopes()

        call_url = mock_get.call_args[0][0]
        assert "getstatus.json" in call_url

    @patch("keep.providers.prtg_provider.prtg_provider.requests.get")
    def test_validate_scopes_uses_ssl_verify_setting(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {}
        mock_get.return_value = mock_resp

        provider = _make_provider(verify_ssl=False)
        provider.validate_scopes()

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["verify"] is False
