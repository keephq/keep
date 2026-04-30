"""
Tests for SolarWinds Provider
"""

import pytest
from unittest.mock import MagicMock, patch

from keep.providers.solarwinds_provider.solarwinds_provider import SolarwindsProvider


class TestSolarwindsProvider:
    """Test cases for the SolarWinds provider."""

    @pytest.fixture
    def provider_config(self):
        return {
            "authentication": {
                "orion_url": "https://orion.example.com:17778",
                "username": "admin",
                "password": "password123",
                "verify_ssl": False,
            }
        }

    @pytest.fixture
    def mock_context_manager(self):
        return MagicMock()

    def test_validate_config(self, provider_config, mock_context_manager):
        """Test that provider config is validated correctly."""
        from keep.providers.models.provider_config import ProviderConfig
        
        config = ProviderConfig(**provider_config)
        provider = SolarwindsProvider(
            context_manager=mock_context_manager,
            provider_id="test-solarwinds",
            config=config,
        )
        provider.validate_config()
        assert str(provider.authentication_config.orion_url) == "https://orion.example.com:17778"
        assert provider.authentication_config.username == "admin"

    def test_format_alert_from_query(self, provider_config, mock_context_manager):
        """Test query result formatting."""
        from keep.providers.models.provider_config import ProviderConfig
        from keep.api.models.alert import AlertSeverity, AlertStatus
        
        config = ProviderConfig(**provider_config)
        provider = SolarwindsProvider(
            context_manager=mock_context_manager,
            provider_id="test-solarwinds",
            config=config,
        )
        provider.validate_config()
        
        alert_data = {
            "AlertActiveID": "12345",
            "AlertObjectID": "67890",
            "AlertName": "Node Down",
            "EntityCaption": "web-server-01",
            "AlertMessage": "Node is not responding to ICMP",
            "Severity": 2,  # Critical
            "Acknowledged": False,
            "TriggeredDateTime": "2026-02-05T02:00:00Z",
        }
        
        alert = provider._format_alert_from_query(alert_data)
        
        assert "Node Down" in alert.name
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING
        assert alert.host == "web-server-01"

    def test_format_acknowledged_alert(self, provider_config, mock_context_manager):
        """Test acknowledged alert formatting."""
        from keep.providers.models.provider_config import ProviderConfig
        from keep.api.models.alert import AlertStatus
        
        config = ProviderConfig(**provider_config)
        provider = SolarwindsProvider(
            context_manager=mock_context_manager,
            provider_id="test-solarwinds",
            config=config,
        )
        provider.validate_config()
        
        alert_data = {
            "AlertActiveID": "12345",
            "AlertName": "High CPU",
            "EntityCaption": "db-server-01",
            "Severity": 1,
            "Acknowledged": True,
            "AcknowledgedBy": "admin",
        }
        
        alert = provider._format_alert_from_query(alert_data)
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledgedBy == "admin"

    def test_format_webhook_alert(self):
        """Test webhook payload formatting."""
        from keep.api.models.alert import AlertSeverity, AlertStatus
        
        webhook_event = {
            "AlertName": "Interface Down",
            "ObjectName": "eth0 on router-01",
            "AlertMessage": "Interface eth0 is down",
            "Severity": "Critical",
            "Acknowledged": False,
            "AlertActiveID": "99999",
            "TriggeredDateTime": "2026-02-05T02:30:00Z",
        }
        
        alert = SolarwindsProvider._format_alert(webhook_event)
        
        assert "Interface Down" in alert.name
        assert "router-01" in alert.name
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING

    def test_format_reset_alert(self):
        """Test reset/resolved alert formatting."""
        from keep.api.models.alert import AlertStatus
        
        webhook_event = {
            "AlertName": "Node Down",
            "ObjectName": "web-server-01",
            "AlertStatus": "Reset",
            "Severity": "Warning",
        }
        
        alert = SolarwindsProvider._format_alert(webhook_event)
        assert alert.status == AlertStatus.RESOLVED

    def test_severities_mapping(self):
        """Test that all SolarWinds severity levels are mapped correctly."""
        from keep.api.models.alert import AlertSeverity
        
        assert SolarwindsProvider.SEVERITIES_MAP[2] == AlertSeverity.CRITICAL
        assert SolarwindsProvider.SEVERITIES_MAP[1] == AlertSeverity.WARNING
        assert SolarwindsProvider.SEVERITIES_MAP[0] == AlertSeverity.INFO
        assert SolarwindsProvider.SEVERITIES_MAP["Critical"] == AlertSeverity.CRITICAL
        assert SolarwindsProvider.SEVERITIES_MAP["Down"] == AlertSeverity.CRITICAL
