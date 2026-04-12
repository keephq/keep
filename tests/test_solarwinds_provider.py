"""Tests for SolarWinds Provider.

Tests the SolarWinds Orion provider for both pull-based (SWIS API)
and push-based (webhook) alert ingestion.
"""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.solarwinds_provider.solarwinds_provider import SolarwindsProvider


class TestSolarwindsProviderWebhook:
    """Test webhook-based alert formatting."""

    def test_format_alert_down(self):
        """Test formatting a node DOWN alert from webhook."""
        event = {
            "NodeName": "server1",
            "AlertName": "Node Down",
            "Status": "Down",
            "Severity": "Critical",
            "Message": "Node server1 is not responding",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert isinstance(alert, AlertDto)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.name == "Node Down"
        assert alert.hostname == "server1"
        assert alert.source == ["solarwinds"]
        assert alert.pushed is True

    def test_format_alert_up(self):
        """Test formatting a node UP (recovery) alert."""
        event = {
            "NodeName": "server1",
            "AlertName": "Node Recovery",
            "Status": "Up",
            "Severity": "Info",
            "Message": "Node server1 is back online",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO

    def test_format_alert_warning(self):
        """Test formatting a WARNING alert."""
        event = {
            "NodeName": "db-server",
            "AlertName": "High CPU Usage",
            "Status": "Warning",
            "Message": "CPU usage above 85% for 5 minutes",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.WARNING
        assert alert.hostname == "db-server"

    def test_format_alert_critical(self):
        """Test formatting a CRITICAL alert."""
        event = {
            "node": "app-server-02",
            "alert": "Memory Exhaustion",
            "status": "Critical",
            "message": "Memory usage at 98%",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.name == "Memory Exhaustion"
        assert alert.hostname == "app-server-02"

    def test_format_alert_case_insensitive_keys(self):
        """Test that field matching works case-insensitively."""
        event = {
            "nodename": "switch-01",
            "alertname": "Port Down",
            "status": "DOWN",
            "severity": "CRITICAL",
            "message": "Port Gi0/1 is down",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.hostname == "switch-01"
        assert alert.name == "Port Down"
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL

    def test_format_alert_with_timestamp(self):
        """Test formatting an alert with a timestamp."""
        event = {
            "NodeName": "server1",
            "AlertName": "Disk Space",
            "Status": "Warning",
            "Message": "Disk usage at 90%",
            "timestamp": "2025-01-15T10:30:00Z",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.lastReceived == "2025-01-15T10:30:00+00:00"

    def test_format_alert_with_unix_timestamp(self):
        """Test formatting an alert with a Unix timestamp."""
        event = {
            "NodeName": "server1",
            "AlertName": "High Latency",
            "Status": "Critical",
            "Message": "Latency exceeds 500ms",
            "timestamp": 1736899200,  # Unix timestamp (seconds) = Jan 15, 2025
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.lastReceived is not None
        assert "2024" in alert.lastReceived

    def test_format_alert_with_url_and_ip(self):
        """Test formatting an alert with URL and IP address."""
        event = {
            "NodeName": "router-01",
            "AlertName": "BGP Session Down",
            "Status": "Down",
            "Severity": "Critical",
            "Message": "BGP peer 10.0.0.1 session down",
            "url": "https://solarwinds.example.com/Orion/NetPerfMon/NodeDetails.aspx?NetObject=N:100",
            "IPAddress": "192.168.1.1",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.url == "https://solarwinds.example.com/Orion/NetPerfMon/NodeDetails.aspx?NetObject=N:100"
        assert alert.ip_address == "192.168.1.1"

    def test_format_alert_minimal_payload(self):
        """Test formatting with minimal payload (only status)."""
        event = {"status": "down"}
        alert = SolarwindsProvider._format_alert(event)
        assert isinstance(alert, AlertDto)
        assert alert.status == AlertStatus.FIRING
        assert alert.name == "SolarWinds Alert"

    def test_format_alert_with_entity(self):
        """Test formatting an alert with entity/component information."""
        event = {
            "NodeName": "app-server",
            "AlertName": "Service Unhealthy",
            "Status": "Critical",
            "Message": "Health check failed",
            "EntityCaption": "Web Application Pool",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.service == "Web Application Pool"

    def test_format_alert_shutdown_status(self):
        """Test formatting an alert with shutdown status."""
        event = {
            "NodeName": "dev-server",
            "AlertName": "Node Shutdown",
            "Status": "Shutdown",
            "Message": "Node was shut down gracefully",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO

    def test_format_alert_stable_id_generation(self):
        """Test that alerts without explicit IDs get stable generated IDs."""
        event = {
            "NodeName": "web-01",
            "AlertName": "SSL Certificate",
            "Status": "Warning",
            "Message": "Certificate expiring in 7 days",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.id == "solarwinds:web-01:SSL Certificate"

    def test_format_alert_explicit_id(self):
        """Test that explicit alert IDs are preserved."""
        event = {
            "id": "alert-12345",
            "NodeName": "server1",
            "AlertName": "Test Alert",
            "Status": "Warning",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.id == "alert-12345"


class TestSolarwindsProviderPull:
    """Test pull-based (SWIS API) alert fetching."""

    @pytest.fixture
    def provider_config(self):
        return ProviderConfig(
            description="Test SolarWinds",
            authentication={
                "host_url": "https://solarwinds.example.com:17778/SolarWinds/InformationService/v3/Json",
                "username": "admin",
                "password": "test_password",
            },
        )

    @pytest.fixture
    def provider(self, provider_config):
        cm = ContextManager(tenant_id="test", workflow_id="test")
        return SolarwindsProvider(cm, "test-solarwinds", provider_config)

    def test_validate_config_basic_auth(self, provider_config):
        """Test config validation with basic auth."""
        cm = ContextManager(tenant_id="test", workflow_id="test")
        provider = SolarwindsProvider(cm, "test-solarwinds", provider_config)
        assert provider.authentication_config.username == "admin"
        assert provider.authentication_config.password == "test_password"

    def test_validate_config_token_auth(self):
        """Test config validation with API token."""
        config = ProviderConfig(
            description="Test SolarWinds Token",
            authentication={
                "host_url": "https://solarwinds.example.com:17778/SolarWinds/InformationService/v3/Json",
                "api_token": "test_token_12345",
            },
        )
        cm = ContextManager(tenant_id="test", workflow_id="test")
        provider = SolarwindsProvider(cm, "test-solarwinds", config)
        assert provider.authentication_config.api_token == "test_token_12345"

    def test_validate_config_no_auth_fails(self):
        """Test that config validation fails without auth credentials."""
        config = ProviderConfig(
            description="Test SolarWinds No Auth",
            authentication={
                "host_url": "https://solarwinds.example.com:17778/SolarWinds/InformationService/v3/Json",
            },
        )
        cm = ContextManager(tenant_id="test", workflow_id="test")
        with pytest.raises(ValueError, match="requires either"):
            SolarwindsProvider(cm, "test-solarwinds", config)

    @patch("keep.providers.solarwinds_provider.solarwinds_provider.requests.post")
    def test_get_alerts_success(self, mock_post, provider):
        """Test successful alert fetching from SWIS API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "AlertObjectID": "alert-001",
                    "AlertDefID": 42,
                    "ObjectName": "Node",
                    "EntityCaption": "server1.example.com",
                    "EntityNetObjectID": "N:100",
                    "AlertMessage": "CPU load exceeded 90%",
                    "Severity": 4,
                    "TriggeredDateTime": "2025-06-15T14:30:00Z",
                    "LastTriggeredDateTime": "2025-06-15T14:30:00Z",
                    "Acknowledged": False,
                    "LastNote": "",
                    "AlertDefName": "High CPU Load",
                    "NodeCaption": "server1",
                    "IP_Address": "10.0.0.1",
                    "NodeIP": "10.0.0.1",
                    "NodeStatus": 2,
                    "NodeGroup": "Production",
                },
                {
                    "AlertObjectID": "alert-002",
                    "AlertDefID": 55,
                    "ObjectName": "Node",
                    "EntityCaption": "db-server.example.com",
                    "EntityNetObjectID": "N:200",
                    "AlertMessage": "Node is down",
                    "Severity": 5,
                    "TriggeredDateTime": "2025-06-15T15:00:00Z",
                    "LastTriggeredDateTime": "2025-06-15T15:00:00Z",
                    "Acknowledged": True,
                    "LastNote": "Investigating",
                    "AlertDefName": "Node Down",
                    "NodeCaption": "db-server",
                    "IP_Address": "10.0.0.2",
                    "NodeIP": "10.0.0.2",
                    "NodeStatus": 2,
                    "NodeGroup": "Database",
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        alerts = provider._get_alerts()
        assert len(alerts) == 2

        # First alert: Major severity, firing
        assert alerts[0].id == "alert-001"
        assert alerts[0].name == "High CPU Load"
        assert alerts[0].severity == AlertSeverity.HIGH
        assert alerts[0].status == AlertStatus.FIRING
        assert alerts[0].hostname == "server1"
        assert alerts[0].ip_address == "10.0.0.1"

        # Second alert: Critical severity, acknowledged
        assert alerts[1].id == "alert-002"
        assert alerts[1].name == "Node Down"
        assert alerts[1].severity == AlertSeverity.CRITICAL
        assert alerts[1].status == AlertStatus.ACKNOWLEDGED
        assert alerts[1].hostname == "db-server"

    @patch("keep.providers.solarwinds_provider.solarwinds_provider.requests.post")
    def test_get_alerts_empty(self, mock_post, provider):
        """Test alert fetching when no active alerts exist."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        alerts = provider._get_alerts()
        assert alerts == []

    @patch("keep.providers.solarwinds_provider.solarwinds_provider.requests.post")
    def test_get_alerts_connection_error(self, mock_post, provider):
        """Test alert fetching when SWIS API is unreachable."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            provider._get_alerts()

    @patch("keep.providers.solarwinds_provider.solarwinds_provider.requests.post")
    def test_validate_scopes_success(self, mock_post, provider):
        """Test scope validation succeeds with valid credentials."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"AlertObjectID": "a1"}]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        scopes = provider.validate_scopes()
        assert scopes["read_alerts"] is True

    @patch("keep.providers.solarwinds_provider.solarwinds_provider.requests.post")
    def test_validate_scopes_failure(self, mock_post, provider):
        """Test scope validation fails with invalid credentials."""
        mock_post.side_effect = requests.exceptions.HTTPError("401 Unauthorized")

        scopes = provider.validate_scopes()
        assert scopes["read_alerts"] == "401 Unauthorized"
