"""
Unit tests for NagiosxiProvider with mocked HTTP responses.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider():
    """Create a NagiosxiProvider instance with a dummy config."""
    from keep.providers.nagiosxi_provider.nagiosxi_provider import NagiosxiProvider

    context_manager = ContextManager(tenant_id="test", workflow_id="test")
    config = ProviderConfig(
        description="Nagios XI Provider Test",
        authentication={
            "host_url": "https://nagios.example.com/nagios",
            "api_key": "test-api-key-123",
        },
    )
    return NagiosxiProvider(context_manager, provider_id="nagiosxi", config=config)


# ---------------------------------------------------------------------------
# Sample API responses (based on Nagios XI REST API format)
# ---------------------------------------------------------------------------

SAMPLE_HOST_STATUS_RESPONSE = {
    "hoststatus": [
        {
            "host_object_id": "123",
            "host_name": "web-server-01",
            "alias": "Web Server 01",
            "address": "192.168.1.10",
            "current_state": "0",
            "output": "PING OK - Packet loss = 0%, RTA = 0.45 ms",
            "long_output": "",
            "perf_data": "rta=0.450000ms;3000.000;5000.000;0; pl=0%;80;100;0;",
            "check_command": "check_ping!100.0,20%!500.0,60%",
            "status": "up",
            "last_check": "1747353600",
            "max_check_attempts": "3",
            "current_check_attempt": "1",
            "state_type": "1",
            "problem_has_been_acknowledged": "0",
            "is_flapping": "0",
            "scheduled_downtime_depth": "0",
        },
        {
            "host_object_id": "124",
            "host_name": "db-server-01",
            "alias": "Database Server 01",
            "address": "192.168.1.20",
            "current_state": "1",
            "output": "CRITICAL - Host Unreachable (192.168.1.20)",
            "long_output": "",
            "perf_data": "",
            "check_command": "check_ping!100.0,20%!500.0,60%",
            "status": "down",
            "last_check": "1747353660",
            "max_check_attempts": "3",
            "current_check_attempt": "3",
            "state_type": "1",
            "problem_has_been_acknowledged": "1",
            "is_flapping": "0",
            "scheduled_downtime_depth": "0",
        },
        {
            "host_object_id": "125",
            "host_name": "mail-server-01",
            "alias": "Mail Server",
            "address": "192.168.1.30",
            "current_state": "2",
            "output": "UNREACHABLE - Host unreachable",
            "long_output": "",
            "perf_data": "",
            "check_command": "check_ping!100.0,20%!500.0,60%",
            "status": "unreachable",
            "last_check": "1747353720",
            "max_check_attempts": "3",
            "current_check_attempt": "2",
            "state_type": "0",
            "problem_has_been_acknowledged": "0",
            "is_flapping": "1",
            "scheduled_downtime_depth": "1",
        },
    ]
}

SAMPLE_SERVICE_STATUS_RESPONSE = {
    "servicestatus": [
        {
            "host_object_id": "123",
            "host_name": "web-server-01",
            "service_object_id": "456",
            "service_description": "HTTP",
            "description": "HTTP",
            "current_state": "0",
            "output": "HTTP OK: HTTP/1.1 200 OK - 0.003s response time",
            "long_output": "",
            "perf_data": "time=0.003152s;;;0.000000;10.000000",
            "check_command": "check_http",
            "last_check": "1747353600",
            "max_check_attempts": "3",
            "current_check_attempt": "1",
            "state_type": "1",
            "problem_has_been_acknowledged": "0",
            "is_flapping": "0",
            "scheduled_downtime_depth": "0",
        },
        {
            "host_object_id": "123",
            "host_name": "web-server-01",
            "service_object_id": "457",
            "service_description": "Disk /",
            "description": "Disk /",
            "current_state": "1",
            "output": "DISK WARNING - free space: / 8192 MB (15% inode=98%);",
            "long_output": "",
            "perf_data": "/=45056MB;;;0;524288",
            "check_command": "check_disk!20%!10%!/",
            "last_check": "1747353600",
            "max_check_attempts": "3",
            "current_check_attempt": "2",
            "state_type": "1",
            "problem_has_been_acknowledged": "0",
            "is_flapping": "0",
            "scheduled_downtime_depth": "0",
        },
        {
            "host_object_id": "124",
            "host_name": "db-server-01",
            "service_object_id": "458",
            "service_description": "MySQL",
            "description": "MySQL",
            "current_state": "2",
            "output": "CRITICAL - Could not connect to MySQL on db-server-01",
            "long_output": "Connection refused",
            "perf_data": "",
            "check_command": "check_mysql",
            "last_check": "1747353660",
            "max_check_attempts": "3",
            "current_check_attempt": "3",
            "state_type": "1",
            "problem_has_been_acknowledged": "0",
            "is_flapping": "0",
            "scheduled_downtime_depth": "0",
        },
        {
            "host_object_id": "125",
            "host_name": "mail-server-01",
            "service_object_id": "459",
            "service_description": "SMTP",
            "description": "SMTP",
            "current_state": "3",
            "output": "UNKNOWN - SMTP check not available",
            "long_output": "",
            "perf_data": "",
            "check_command": "check_smtp",
            "last_check": "1747353720",
            "max_check_attempts": "3",
            "current_check_attempt": "1",
            "state_type": "0",
            "problem_has_been_acknowledged": "0",
            "is_flapping": "0",
            "scheduled_downtime_depth": "0",
        },
    ]
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNagiosxiProviderHostStatus:
    """Tests for __get_host_status (via _get_alerts)."""

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_host_status_ok(self, mock_get):
        """Host with state 0 (UP) should map to RESOLVED/LOW."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = SAMPLE_HOST_STATUS_RESPONSE
        mock_get.return_value = mock_response

        # Mock service status to return empty
        mock_svc_response = MagicMock()
        mock_svc_response.ok = True
        mock_svc_response.json.return_value = {"servicestatus": []}
        mock_get.side_effect = [mock_response, mock_svc_response]

        provider = _make_provider()
        alerts = provider._get_alerts()

        host_alert = next(a for a in alerts if a.name == "web-server-01")
        assert host_alert.status == AlertStatus.RESOLVED
        assert host_alert.severity == AlertSeverity.LOW
        assert host_alert.source == ["nagiosxi"]
        assert host_alert.acknowledged is False
        assert host_alert.is_flapping is False

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_host_status_down(self, mock_get):
        """Host with state 1 (DOWN) should map to FIRING/CRITICAL."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = SAMPLE_HOST_STATUS_RESPONSE
        mock_get.return_value = mock_response

        mock_svc_response = MagicMock()
        mock_svc_response.ok = True
        mock_svc_response.json.return_value = {"servicestatus": []}
        mock_get.side_effect = [mock_response, mock_svc_response]

        provider = _make_provider()
        alerts = provider._get_alerts()

        host_alert = next(a for a in alerts if a.name == "db-server-01")
        assert host_alert.status == AlertStatus.FIRING
        assert host_alert.severity == AlertSeverity.CRITICAL
        assert host_alert.acknowledged is True

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_host_status_unreachable(self, mock_get):
        """Host with state 2 (UNREACHABLE) should map to FIRING/WARNING."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = SAMPLE_HOST_STATUS_RESPONSE
        mock_get.return_value = mock_response

        mock_svc_response = MagicMock()
        mock_svc_response.ok = True
        mock_svc_response.json.return_value = {"servicestatus": []}
        mock_get.side_effect = [mock_response, mock_svc_response]

        provider = _make_provider()
        alerts = provider._get_alerts()

        host_alert = next(a for a in alerts if a.name == "mail-server-01")
        assert host_alert.status == AlertStatus.FIRING
        assert host_alert.severity == AlertSeverity.WARNING
        assert host_alert.is_flapping is True
        assert host_alert.scheduled_downtime_depth == "1"


class TestNagiosxiProviderServiceStatus:
    """Tests for __get_service_status (via _get_alerts)."""

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_service_status_ok(self, mock_get):
        """Service with state 0 (OK) should map to RESOLVED/LOW."""
        mock_host_response = MagicMock()
        mock_host_response.ok = True
        mock_host_response.json.return_value = {"hoststatus": []}

        mock_svc_response = MagicMock()
        mock_svc_response.ok = True
        mock_svc_response.json.return_value = SAMPLE_SERVICE_STATUS_RESPONSE

        mock_get.side_effect = [mock_host_response, mock_svc_response]

        provider = _make_provider()
        alerts = provider._get_alerts()

        svc_alert = next(
            a for a in alerts if a.name == "HTTP" and a.host == "web-server-01"
        )
        assert svc_alert.status == AlertStatus.RESOLVED
        assert svc_alert.severity == AlertSeverity.LOW

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_service_status_warning(self, mock_get):
        """Service with state 1 (WARNING) should map to FIRING/WARNING."""
        mock_host_response = MagicMock()
        mock_host_response.ok = True
        mock_host_response.json.return_value = {"hoststatus": []}

        mock_svc_response = MagicMock()
        mock_svc_response.ok = True
        mock_svc_response.json.return_value = SAMPLE_SERVICE_STATUS_RESPONSE

        mock_get.side_effect = [mock_host_response, mock_svc_response]

        provider = _make_provider()
        alerts = provider._get_alerts()

        svc_alert = next(
            a for a in alerts if a.name == "Disk /" and a.host == "web-server-01"
        )
        assert svc_alert.status == AlertStatus.FIRING
        assert svc_alert.severity == AlertSeverity.WARNING

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_service_status_critical(self, mock_get):
        """Service with state 2 (CRITICAL) should map to FIRING/CRITICAL."""
        mock_host_response = MagicMock()
        mock_host_response.ok = True
        mock_host_response.json.return_value = {"hoststatus": []}

        mock_svc_response = MagicMock()
        mock_svc_response.ok = True
        mock_svc_response.json.return_value = SAMPLE_SERVICE_STATUS_RESPONSE

        mock_get.side_effect = [mock_host_response, mock_svc_response]

        provider = _make_provider()
        alerts = provider._get_alerts()

        svc_alert = next(
            a for a in alerts if a.name == "MySQL" and a.host == "db-server-01"
        )
        assert svc_alert.status == AlertStatus.FIRING
        assert svc_alert.severity == AlertSeverity.CRITICAL

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_service_status_unknown(self, mock_get):
        """Service with state 3 (UNKNOWN) should map to FIRING/INFO."""
        mock_host_response = MagicMock()
        mock_host_response.ok = True
        mock_host_response.json.return_value = {"hoststatus": []}

        mock_svc_response = MagicMock()
        mock_svc_response.ok = True
        mock_svc_response.json.return_value = SAMPLE_SERVICE_STATUS_RESPONSE

        mock_get.side_effect = [mock_host_response, mock_svc_response]

        provider = _make_provider()
        alerts = provider._get_alerts()

        svc_alert = next(
            a for a in alerts if a.name == "SMTP" and a.host == "mail-server-01"
        )
        assert svc_alert.status == AlertStatus.FIRING
        assert svc_alert.severity == AlertSeverity.INFO


class TestNagiosxiProviderCombined:
    """Tests for _get_alerts combining host and service results."""

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_combined_alerts(self, mock_get):
        """_get_alerts should return both host and service alerts."""
        mock_host_response = MagicMock()
        mock_host_response.ok = True
        mock_host_response.json.return_value = SAMPLE_HOST_STATUS_RESPONSE

        mock_svc_response = MagicMock()
        mock_svc_response.ok = True
        mock_svc_response.json.return_value = SAMPLE_SERVICE_STATUS_RESPONSE

        mock_get.side_effect = [mock_host_response, mock_svc_response]

        provider = _make_provider()
        alerts = provider._get_alerts()

        # 3 hosts + 4 services = 7 total alerts
        assert len(alerts) == 7

        # Verify all have source=nagiosxi
        for alert in alerts:
            assert alert.source == ["nagiosxi"]

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_host_failure_does_not_block_service(self, mock_get):
        """If host status API fails, service alerts should still be returned."""
        mock_host_response = MagicMock()
        mock_host_response.ok = False
        mock_host_response.status_code = 500
        mock_host_response.text = "Internal Server Error"

        mock_svc_response = MagicMock()
        mock_svc_response.ok = True
        mock_svc_response.json.return_value = SAMPLE_SERVICE_STATUS_RESPONSE

        mock_get.side_effect = [mock_host_response, mock_svc_response]

        provider = _make_provider()
        alerts = provider._get_alerts()

        # Only service alerts should be returned (4 services)
        assert len(alerts) == 4

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_service_failure_does_not_block_host(self, mock_get):
        """If service status API fails, host alerts should still be returned."""
        mock_host_response = MagicMock()
        mock_host_response.ok = True
        mock_host_response.json.return_value = SAMPLE_HOST_STATUS_RESPONSE

        mock_svc_response = MagicMock()
        mock_svc_response.ok = False
        mock_svc_response.status_code = 500
        mock_svc_response.text = "Internal Server Error"

        mock_get.side_effect = [mock_host_response, mock_svc_response]

        provider = _make_provider()
        alerts = provider._get_alerts()

        # Only host alerts should be returned (3 hosts)
        assert len(alerts) == 3

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_single_host_response(self, mock_get):
        """API may return a single dict instead of a list when there's one host."""
        single_host_response = {
            "hoststatus": {
                "host_object_id": "123",
                "host_name": "single-host",
                "alias": "Single Host",
                "address": "10.0.0.1",
                "current_state": "0",
                "output": "PING OK",
                "long_output": "",
                "perf_data": "",
                "check_command": "check_ping",
                "status": "up",
                "last_check": "1747353600",
                "max_check_attempts": "3",
                "current_check_attempt": "1",
                "state_type": "1",
                "problem_has_been_acknowledged": "0",
                "is_flapping": "0",
                "scheduled_downtime_depth": "0",
            }
        }

        mock_host_response = MagicMock()
        mock_host_response.ok = True
        mock_host_response.json.return_value = single_host_response

        mock_svc_response = MagicMock()
        mock_svc_response.ok = True
        mock_svc_response.json.return_value = {"servicestatus": []}

        mock_get.side_effect = [mock_host_response, mock_svc_response]

        provider = _make_provider()
        alerts = provider._get_alerts()

        assert len(alerts) == 1
        assert alerts[0].name == "single-host"
        assert alerts[0].status == AlertStatus.RESOLVED

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_empty_response(self, mock_get):
        """API returns empty results."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"hoststatus": [], "servicestatus": []}
        mock_get.return_value = mock_response

        provider = _make_provider()
        alerts = provider._get_alerts()

        assert len(alerts) == 0


class TestNagiosxiProviderConfig:
    """Tests for configuration validation."""

    def test_valid_config(self):
        """Valid config should not raise."""
        provider = _make_provider()
        assert provider.authentication_config.host_url == "https://nagios.example.com/nagios"
        assert provider.authentication_config.api_key == "test-api-key-123"

    def test_provider_metadata(self):
        """Provider metadata should be correctly set."""
        from keep.providers.nagiosxi_provider.nagiosxi_provider import NagiosxiProvider

        assert NagiosxiProvider.PROVIDER_DISPLAY_NAME == "Nagios XI"
        assert NagiosxiProvider.PROVIDER_CATEGORY == ["Monitoring"]
        assert NagiosxiProvider.PROVIDER_TAGS == ["alert"]
        assert len(NagiosxiProvider.PROVIDER_SCOPES) == 1
        assert NagiosxiProvider.PROVIDER_SCOPES[0].name == "authenticated"

    def test_state_maps_complete(self):
        """All Nagios states (0-3 for services, 0-2 for hosts) should be mapped."""
        from keep.providers.nagiosxi_provider.nagiosxi_provider import NagiosxiProvider

        # Service maps should cover all 4 states
        assert 0 in NagiosxiProvider.SERVICE_STATUS_MAP
        assert 1 in NagiosxiProvider.SERVICE_STATUS_MAP
        assert 2 in NagiosxiProvider.SERVICE_STATUS_MAP
        assert 3 in NagiosxiProvider.SERVICE_STATUS_MAP
        assert 0 in NagiosxiProvider.SERVICE_SEVERITY_MAP
        assert 1 in NagiosxiProvider.SERVICE_SEVERITY_MAP
        assert 2 in NagiosxiProvider.SERVICE_SEVERITY_MAP
        assert 3 in NagiosxiProvider.SERVICE_SEVERITY_MAP

        # Host maps should cover states 0-2
        assert 0 in NagiosxiProvider.HOST_STATUS_MAP
        assert 1 in NagiosxiProvider.HOST_STATUS_MAP
        assert 2 in NagiosxiProvider.HOST_STATUS_MAP
        assert 0 in NagiosxiProvider.HOST_SEVERITY_MAP
        assert 1 in NagiosxiProvider.HOST_SEVERITY_MAP
        assert 2 in NagiosxiProvider.HOST_SEVERITY_MAP


class TestNagiosxiProviderScopes:
    """Tests for scope validation."""

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_validate_scopes_success(self, mock_get):
        """Successful API call should return authenticated=True."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_get.return_value = mock_response

        provider = _make_provider()
        scopes = provider.validate_scopes()

        assert scopes["authenticated"] is True

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_validate_scopes_failure(self, mock_get):
        """Failed API call should return error message."""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response

        provider = _make_provider()
        scopes = provider.validate_scopes()

        assert isinstance(scopes["authenticated"], str)
        assert "401" in scopes["authenticated"]

    @patch("keep.providers.nagiosxi_provider.nagiosxi_provider.requests.get")
    def test_validate_scopes_exception(self, mock_get):
        """Network exception should return error message."""
        mock_get.side_effect = Exception("Connection refused")

        provider = _make_provider()
        scopes = provider.validate_scopes()

        assert isinstance(scopes["authenticated"], str)
        assert "Connection refused" in scopes["authenticated"]
