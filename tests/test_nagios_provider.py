"""Tests for Nagios Provider.

This module tests the Nagios provider webhook functionality, state mapping,
and alert formatting.
"""
import pytest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.nagios_provider.nagios_provider import NagiosProvider
from keep.providers.models.provider_config import ProviderConfig


class TestNagiosProvider:
    """Test suite for Nagios Provider."""

    @pytest.fixture
    def nagios_config(self):
        return ProviderConfig(
            description="Test Nagios",
            authentication={
                "host_url": "http://nagios.example.com/nagios",
                "api_user": "admin",
                "api_password": "password",
            },
        )

    @pytest.fixture
    def nagios_provider(self, nagios_config):
        cm = ContextManager(tenant_id="test", workflow_id="test")
        return NagiosProvider(cm, "test-nagios", nagios_config)

    def test_format_alert_ok(self):
        """Test formatting a Nagios OK alert."""
        event = {
            "host": "server1",
            "service": "CPU Usage",
            "state_id": 0,
            "output": "CPU load is normal",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO
        assert alert.name == "CPU Usage"

    def test_format_alert_warning(self):
        """Test formatting a Nagios WARNING alert."""
        event = {
            "host": "server1",
            "service": "Disk Space",
            "state_id": 1,
            "output": "Disk space 85% full",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.WARNING

    def test_format_alert_critical(self):
        """Test formatting a Nagios CRITICAL alert."""
        event = {
            "host": "server1",
            "service": "Memory",
            "state_id": 2,
            "output": "Memory usage critical",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL

    def test_format_alert_unknown(self):
        """Test formatting a Nagios UNKNOWN alert."""
        event = {
            "host": "server1",
            "service": "Process",
            "state_id": 3,
            "output": "Process status unknown",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.INFO

    def test_format_alert_host_check(self):
        """Test formatting a host check (no service)."""
        event = {
            "host": "server1",
            "state_id": 2,
            "output": "Host is DOWN",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.name == "server1"
        assert alert.status == AlertStatus.FIRING
        assert "server1" == alert.hostname

    @patch("requests.get")
    def test_get_alerts_success(self, mock_get, nagios_provider):
        """Test getting alerts from Nagios."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "servicelist": {
                    "server1": {
                        "SSH": {"status": 2, "plugin_output": "SSH failed"},
                        "HTTP": {"status": 1, "plugin_output": "Slow response"},
                    }
                }
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        alerts = nagios_provider._get_alerts()
        assert len(alerts) == 2
        assert alerts[0].status == AlertStatus.FIRING

    @patch("requests.get")
    def test_get_alerts_empty(self, mock_get, nagios_provider):
        """Test getting alerts when all services are OK."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "servicelist": {
                    "server1": {
                        "SSH": {"status": 0, "plugin_output": "OK"},
                    }
                }
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        alerts = nagios_provider._get_alerts()
        assert len(alerts) == 0  # OK services excluded

    @patch("requests.get")
    def test_validate_scopes_success(self, mock_get, nagios_provider):
        """Test validate_scopes with successful connection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        scopes = nagios_provider.validate_scopes()
        assert scopes["read_alerts"] is True

    @patch("requests.get")
    def test_validate_scopes_failure(self, mock_get, nagios_provider):
        """Test validate_scopes with failed connection."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("Unauthorized")
        mock_get.return_value = mock_response

        scopes = nagios_provider.validate_scopes()
        assert "error" in str(scopes["read_alerts"]).lower()
