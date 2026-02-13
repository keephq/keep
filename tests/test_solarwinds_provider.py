"""Tests for SolarWinds Provider.

Tests the SolarWinds Orion webhook provider for receiving alerts.
"""
import pytest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.solarwinds_provider.solarwinds_provider import SolarwindsProvider
from keep.providers.models.provider_config import ProviderConfig


class TestSolarwindsProvider:
    """Test suite for SolarWinds Provider."""

    @pytest.fixture
    def solarwinds_config(self):
        return ProviderConfig(
            description="Test SolarWinds",
            authentication={
                "webhook_url": "https://solarwinds.example.com/webhook",
                "api_key": "test-api-key",
            },
        )

    @pytest.fixture
    def solarwinds_provider(self, solarwinds_config):
        cm = ContextManager(tenant_id="test", workflow_id="test")
        return SolarwindsProvider(cm, "test-solarwinds", solarwinds_config)

    def test_format_alert_up(self):
        """Test formatting a SolarWinds UP alert."""
        event = {
            "node": "server1",
            "alert": "Node Status",
            "status": "Up",
            "message": "Node is responding",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO
        assert alert.name == "Node Status"

    def test_format_alert_down(self):
        """Test formatting a SolarWinds DOWN alert."""
        event = {
            "node": "server1",
            "alert": "Node Status",
            "status": "Down",
            "message": "Node is not responding",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL

    def test_format_alert_warning(self):
        """Test formatting a SolarWinds WARNING alert."""
        event = {
            "node": "server1",
            "alert": "CPU Usage",
            "status": "Warning",
            "message": "CPU usage above 80%",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.WARNING

    def test_format_alert_critical(self):
        """Test formatting a SolarWinds CRITICAL alert."""
        event = {
            "node": "server2",
            "alert": "Memory",
            "status": "Critical",
            "message": "Memory usage critical",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL

    def test_format_alert_unknown(self):
        """Test formatting a SolarWinds UNKNOWN status."""
        event = {
            "node": "server1",
            "alert": "Service Check",
            "status": "Unknown",
            "message": "Unable to determine status",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING

    def test_format_alert_with_node_only(self):
        """Test formatting alert with only node (no alert name)."""
        event = {
            "node": "router1",
            "status": "Down",
            "message": "Router unreachable",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.name == "router1"
        assert alert.hostname == "router1"

    def test_format_alert_with_timestamp(self):
        """Test formatting alert with timestamp."""
        event = {
            "node": "server1",
            "alert": "Disk Space",
            "status": "Warning",
            "message": "Disk 90% full",
            "timestamp": "2024-01-15T10:30:00Z",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.lastReceived is not None

    def test_format_alert_with_url(self):
        """Test formatting alert with URL."""
        event = {
            "node": "server1",
            "alert": "CPU Load",
            "status": "Critical",
            "message": "High CPU load",
            "url": "https://solarwinds.example.com/Orion/NetPerfMon/NodeDetails.aspx?NetObject=N:1",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.url is not None

    def test_validate_scopes_success(self, solarwinds_provider):
        """Test validate_scopes returns True for valid config."""
        scopes = solarwinds_provider.validate_scopes()
        assert scopes["webhook"] is True

    def test_validate_config(self, solarwinds_provider):
        """Test config validation."""
        assert solarwinds_provider.authentication_config.webhook_url == "https://solarwinds.example.com/webhook"
        assert solarwinds_provider.authentication_config.api_key == "test-api-key"
