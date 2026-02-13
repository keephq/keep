"""
Tests for Nagios Provider
"""

import pytest
from unittest.mock import MagicMock, patch

from keep.providers.nagios_provider.nagios_provider import NagiosProvider


class TestNagiosProvider:
    """Test cases for the Nagios provider."""

    @pytest.fixture
    def provider_config(self):
        return {
            "authentication": {
                "nagios_url": "https://nagios.example.com/nagiosxi",
                "api_key": "test-api-key",
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
        provider = NagiosProvider(
            context_manager=mock_context_manager,
            provider_id="test-nagios",
            config=config,
        )
        provider.validate_config()
        assert provider.authentication_config.nagios_url == "https://nagios.example.com/nagiosxi"
        assert provider.authentication_config.api_key == "test-api-key"

    def test_format_host_alert(self, provider_config, mock_context_manager):
        """Test host alert formatting."""
        from keep.providers.models.provider_config import ProviderConfig
        from keep.api.models.alert import AlertSeverity, AlertStatus
        
        config = ProviderConfig(**provider_config)
        provider = NagiosProvider(
            context_manager=mock_context_manager,
            provider_id="test-nagios",
            config=config,
        )
        provider.validate_config()
        
        host_status = {
            "host_object_id": "123",
            "name": "web-server-01",
            "current_state": 1,  # DOWN
            "output": "PING CRITICAL - Packet loss = 100%",
        }
        
        alert = provider._format_host_alert(host_status)
        
        assert "web-server-01" in alert.name
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING
        assert alert.host == "web-server-01"

    def test_format_service_alert(self, provider_config, mock_context_manager):
        """Test service alert formatting."""
        from keep.providers.models.provider_config import ProviderConfig
        from keep.api.models.alert import AlertSeverity, AlertStatus
        
        config = ProviderConfig(**provider_config)
        provider = NagiosProvider(
            context_manager=mock_context_manager,
            provider_id="test-nagios",
            config=config,
        )
        provider.validate_config()
        
        service_status = {
            "service_object_id": "456",
            "host_name": "db-server-01",
            "name": "MySQL",
            "current_state": 2,  # CRITICAL
            "output": "Connection refused",
        }
        
        alert = provider._format_service_alert(service_status)
        
        assert "MySQL" in alert.name
        assert "db-server-01" in alert.name
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING

    def test_format_webhook_alert(self):
        """Test webhook payload formatting."""
        from keep.api.models.alert import AlertSeverity, AlertStatus
        
        # Simulating Nagios webhook payload
        webhook_event = {
            "HOSTNAME": "app-server-01",
            "SERVICEDESC": "HTTP",
            "SERVICESTATE": "WARNING",
            "SERVICEOUTPUT": "HTTP WARNING: HTTP/1.1 503 Service Unavailable",
            "LONGDATETIME": "2026-02-04 22:00:00",
        }
        
        alert = NagiosProvider._format_alert(webhook_event)
        
        assert alert.host == "app-server-01"
        assert alert.service == "HTTP"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING

    def test_severities_mapping(self):
        """Test that all Nagios states are mapped correctly."""
        from keep.api.models.alert import AlertSeverity
        
        assert NagiosProvider.SEVERITIES_MAP["CRITICAL"] == AlertSeverity.CRITICAL
        assert NagiosProvider.SEVERITIES_MAP["WARNING"] == AlertSeverity.WARNING
        assert NagiosProvider.SEVERITIES_MAP["OK"] == AlertSeverity.LOW
        assert NagiosProvider.SEVERITIES_MAP["DOWN"] == AlertSeverity.CRITICAL
        assert NagiosProvider.SEVERITIES_MAP["UP"] == AlertSeverity.LOW
